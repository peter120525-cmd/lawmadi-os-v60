#!/usr/bin/env python3
"""
Response Verification Engine
Gemini API를 사용하여 응답의 SSOT 준수 여부를 검증
"""
import os
import re
import logging
from google import genai
from google.genai import types as genai_types
from typing import Dict, Any, List, Optional
import json
from core.constants import GEMINI_MODEL
from core.model_fallback import generate_with_fallback, get_model

logger = logging.getLogger(__name__)

class ResponseVerifier:
    """
    Gemini 응답 검증기
    - DRF API 데이터 사용 여부 확인
    - 환각(hallucination) 감지
    - SSOT 원칙 준수 검증
    """

    def __init__(self):
        from core.constants import USE_VERTEX_AI, VERTEX_PROJECT, VERTEX_LOCATION

        self.model_name = GEMINI_MODEL
        self.client = None
        self.enabled = False

        if USE_VERTEX_AI:
            try:
                self.client = genai.Client(
                    vertexai=True,
                    project=VERTEX_PROJECT,
                    location=VERTEX_LOCATION,
                )
                self.enabled = True
                logger.info(f"✅ [Verifier] Vertex AI 초기화 완료 ({VERTEX_PROJECT}/{VERTEX_LOCATION})")
            except Exception as e:
                logger.error(f"❌ [Verifier] Vertex AI init 실패: {e}")

        if not self.enabled:
            api_key = os.getenv("GEMINI_KEY", "")
            if api_key:
                self.client = genai.Client(api_key=api_key)
                self.enabled = True
                logger.info("✅ [Verifier] Gemini API 초기화 완료 (API key)")
            else:
                logger.warning("⚠️ [Verifier] GEMINI_KEY 미설정 - 검증 비활성화")

    def verify_response(
        self,
        user_query: str,
        gemini_response: str,
        tools_used: List[Dict[str, Any]],
        tool_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Gemini 응답 검증

        Args:
            user_query: 사용자 질문
            gemini_response: Gemini의 최종 응답
            tools_used: 호출된 tool 함수 목록
            tool_results: tool 함수 실행 결과

        Returns:
            {
                "result": "PASS" | "FAIL" | "WARNING",
                "issues": [...],
                "feedback": "검증 피드백",
                "ssot_compliance_score": 0-100
            }
        """
        if not self.enabled:
            return {
                "result": "SKIP",
                "issues": [],
                "feedback": "검증기 비활성화됨 (GEMINI_KEY 미설정)",
                "ssot_compliance_score": 0
            }

        try:
            # Gemini에게 검증 요청
            verification_prompt = self._build_verification_prompt(
                user_query, gemini_response, tools_used, tool_results
            )

            response = generate_with_fallback(
                self.client,
                contents=verification_prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                    max_output_tokens=2000,
                    thinking_config=genai_types.ThinkingConfig(
                        thinking_budget=0,
                    ),
                ),
            )

            # Gemini의 응답 파싱 (thinking 파트 제외, 안전 추출)
            try:
                verification_text = response.text or ""
            except ValueError:
                # thinking 파트만 있을 때 .text가 ValueError 발생
                verification_text = ""
                for part in (response.candidates[0].content.parts or []):
                    if part.text and not getattr(part, "thought", False):
                        verification_text += part.text
            result = self._parse_verification_result(verification_text)

            logger.info(f"✅ [Verifier] 검증 완료: {result['result']} (점수: {result['ssot_compliance_score']})")
            return result

        except Exception as e:
            logger.error(f"❌ [Verifier] 검증 실패: {e}")
            return {
                "result": "ERROR",
                "issues": [f"검증 중 오류 발생: {str(e)}"],
                "feedback": "검증 시스템 오류",
                "ssot_compliance_score": 0
            }

    def _build_verification_prompt(
        self,
        user_query: str,
        gemini_response: str,
        tools_used: List[Dict[str, Any]],
        tool_results: List[Dict[str, Any]]
    ) -> str:
        """검증을 위한 프롬프트 생성"""

        tools_summary = []
        for tool in tools_used:
            tool_name = tool.get("name", "unknown")
            tool_args = tool.get("args", {})
            tools_summary.append(f"- {tool_name}({json.dumps(tool_args, ensure_ascii=False)})")

        tools_text = "\n".join(tools_summary) if tools_summary else "없음 (⚠️ DRF API 미사용)"

        results_summary = []
        for i, result in enumerate(tool_results, 1):
            result_status = result.get("result", "UNKNOWN")
            result_source = result.get("source", "N/A")
            ref_name = result.get("ref", "")
            line = f"{i}. [{result_status}] {ref_name} (출처: {result_source})"
            article_text = result.get("article_text", "")
            if article_text:
                line += f"\n   조문 본문: {article_text}"
            drf_summary = result.get("drf_summary", "")
            if drf_summary:
                line += f"\n   판시사항/판결요지: {drf_summary}"
            results_summary.append(line)

        results_text = "\n".join(results_summary) if results_summary else "없음"

        # DRF Stage 4 통과/실패 카운트 계산
        found_count = sum(1 for r in tool_results if r.get("result") == "FOUND")
        nodata_count = sum(1 for r in tool_results if r.get("result") == "NO_DATA")
        total_count = len(tool_results)

        # DRF Stage 4 요약 헤더 (Verifier Gemini가 무시하지 못하도록 명시)
        drf_header = ""
        if total_count > 0:
            drf_header = f"""
⚠️ **중요: DRF Stage 4 전수 검증이 이미 완료되었습니다.**
- 총 {total_count}건 검증: {found_count}건 FOUND (통과), {nodata_count}건 NO_DATA
- 아래 Tool 실행 결과에서 [FOUND]로 표시된 조문은 DRF API로 **실제 확인 완료**된 것입니다.
- [FOUND] 조문을 "DRF API 미사용"이라고 판단하면 안 됩니다.
"""
        else:
            drf_header = "\n⚠️ DRF Stage 4 검증 결과가 없습니다 (Tool 미사용).\n"

        prompt = f"""당신은 법률 AI 시스템의 품질 검증 담당자입니다.
아래 Gemini의 응답이 **SSOT (Single Source of Truth) 원칙**을 준수했는지 검증하십시오.

# SSOT 원칙
1. **실수는 허용되지 않는다**: 부정확한 정보는 사용자의 인생을 잘못된 방향으로 이끈다
2. **확인되지 않은 정보는 절대 확정적으로 제공하지 않는다** (Fail-Closed)
3. **환각(hallucination) 금지**: 임의로 법령명, 조문, 판례를 만들어내면 안 됨

---
{drf_header}
## 사용자 질문
```
{user_query}
```

## Gemini의 응답
```
{gemini_response}
```

## 사용된 Tool 함수
{tools_text}

## Tool 실행 결과 (DRF Stage 4 검증 완료)
{results_text}

---

# 검증 항목

1. **DRF API 사용 여부**
   - Tool 실행 결과에 [FOUND] 항목이 있으면 → DRF API가 사용된 것임 (PASS 조건 충족)
   - Tool 실행 결과가 "없음"이면 → DRF API 미사용 (감점)
   - ⚠️ Tool 실행 결과에 [FOUND]가 있는데 "DRF API 미사용"이라고 판단하지 마라

2. **환각 감지**
   - 응답에서 인용한 법령/조문이 Tool 결과의 [FOUND] 항목에 있는가?
   - Tool 결과에 없는 법령/조문을 응답이 추가로 인용했는가? → WARNING (FAIL은 아님, 해당 조문은 DRF 미검증이지만 Gemini 지식에 기반)
   - ⚠️ 항/호/목 검증: 조문 본문이 있으면 항·호·목 대조. 본문 없으면 상위 조문 FOUND 시 WARNING.
   - ⚠️ **판례/헌재결정 내용 검증**: 판시사항/판결요지가 있으면 응답 내용과 대조. 내용 불일치 → FAIL.
   - ⚠️ **조문 내용 불일치**: DRF가 제목만 반환하고 본문이 없는 경우, 응답이 조문 내용을 풀어서 설명하는 것은 환각이 아님 → WARNING으로 처리

3. **Fail-Closed 준수**
   - Tool 결과가 "NO_DATA"인 조문을 확정적으로 인용했는가? → FAIL

---

# 응답 형식 (JSON)

{{
  "result": "PASS" | "WARNING" | "FAIL",
  "ssot_compliance_score": 0-100,
  "issues": ["발견된 문제점"],
  "feedback": "검증 피드백 (1-2문장)"
}}

**판단 기준:**
- PASS (80-100점): DRF [FOUND] 결과가 있고, 응답이 해당 조문을 정확히 인용
- WARNING (60-79점): DRF 검증 조문 외 추가 인용이 있지만 대체로 정확
- FAIL (0-59점): Tool 결과 없음 + 법률 인용 존재, 또는 NO_DATA 조문을 확정 인용, 또는 판례 내용 불일치

JSON만 응답하십시오."""

        return prompt

    def _parse_verification_result(self, text: str) -> Dict[str, Any]:
        """Gemini의 검증 응답 파싱 (다단계 복구)"""
        json_text = self._extract_json_block(text)

        # 1차: 직접 파싱
        parsed = self._try_parse(json_text)
        if parsed is not None:
            return self._fill_defaults(parsed)

        # 2차: 문자열 내 이스케이프되지 않은 줄바꿈/따옴표 수정
        repaired = self._repair_json(json_text)
        parsed = self._try_parse(repaired)
        if parsed is not None:
            logger.info("[Verifier] JSON 복구 파싱 성공")
            return self._fill_defaults(parsed)

        # 3차: 정규식으로 핵심 필드 추출
        extracted = self._extract_fields_regex(text)
        if extracted:
            logger.info("[Verifier] 정규식 필드 추출 성공")
            return extracted

        # 최종 fallback: WARNING 반환 (ERROR 아님 — 실제 응답은 정상 전달됨)
        logger.warning(f"⚠️ [Verifier] 응답 파싱 실패, WARNING 처리: {text[:200]}")
        return {
            "result": "WARNING",
            "issues": ["검증 응답 파싱 실패 — 검증 불확실"],
            "feedback": text[:500],
            "ssot_compliance_score": 50
        }

    @staticmethod
    def _extract_json_block(text: str) -> str:
        """마크다운 코드블록에서 JSON 추출"""
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            return text[start:end].strip() if end > start else text[start:].strip()
        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            return text[start:end].strip() if end > start else text[start:].strip()
        return text.strip()

    @staticmethod
    def _try_parse(text: str) -> Optional[Dict]:
        """json.loads 시도, 실패 시 None"""
        try:
            result = json.loads(text)
            return result if isinstance(result, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None

    @staticmethod
    def _repair_json(text: str) -> str:
        """흔한 JSON 오류 복구: 문자열 내 줄바꿈, 미종료 문자열 등

        문자 단위로 파싱하여 JSON 문자열 내부의 줄바꿈만 이스케이프하고,
        미종료 문자열/배열/객체를 닫음.
        """
        chars = list(text)
        result = []
        in_string = False
        i = 0

        while i < len(chars):
            ch = chars[i]

            if in_string:
                if ch == '\\' and i + 1 < len(chars):
                    # 이스케이프 시퀀스 — 그대로 유지
                    result.append(ch)
                    result.append(chars[i + 1])
                    i += 2
                    continue
                elif ch == '"':
                    # 문자열 종료
                    in_string = False
                    result.append(ch)
                elif ch == '\n':
                    result.append('\\n')
                elif ch == '\r':
                    result.append('\\r')
                elif ch == '\t':
                    result.append('\\t')
                else:
                    result.append(ch)
            else:
                if ch == '"':
                    in_string = True
                result.append(ch)

            i += 1

        repaired = "".join(result)

        # 미종료 문자열 닫기
        if in_string:
            repaired += '"'

        # 미종료 배열/객체 닫기
        open_brackets = repaired.count("[") - repaired.count("]")
        open_braces = repaired.count("{") - repaired.count("}")

        # 후행 콤마 제거
        repaired = repaired.rstrip()
        if repaired.endswith(","):
            repaired = repaired[:-1]

        repaired += "]" * open_brackets
        repaired += "}" * open_braces

        return repaired

    @staticmethod
    def _extract_fields_regex(text: str) -> Optional[Dict[str, Any]]:
        """정규식으로 핵심 필드 추출 (최후 수단)"""
        result_m = re.search(r'"result"\s*:\s*"(PASS|WARNING|FAIL)"', text)
        score_m = re.search(r'"ssot_compliance_score"\s*:\s*(\d+)', text)

        if not result_m and not score_m:
            return None

        result_val = result_m.group(1) if result_m else "WARNING"
        score_val = int(score_m.group(1)) if score_m else 50

        feedback_m = re.search(r'"feedback"\s*:\s*"([^"]{1,500})', text)
        feedback_val = feedback_m.group(1) if feedback_m else "검증 완료 (파싱 복구)"

        # issues 배열에서 개별 문자열 추출
        issues = re.findall(r'"issues"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        issue_list = []
        if issues:
            issue_list = re.findall(r'"([^"]+)"', issues[0])

        return {
            "result": result_val,
            "ssot_compliance_score": score_val,
            "issues": issue_list,
            "feedback": feedback_val
        }

    @staticmethod
    def _fill_defaults(result: Dict[str, Any]) -> Dict[str, Any]:
        """필수 필드 기본값 설정"""
        result.setdefault("result", "WARNING")
        result.setdefault("ssot_compliance_score", 50)
        result.setdefault("issues", [])
        result.setdefault("feedback", "검증 완료")
        return result


# 싱글톤 인스턴스
_verifier_instance = None

def get_verifier() -> ResponseVerifier:
    """검증기 싱글톤 인스턴스 반환"""
    global _verifier_instance
    if _verifier_instance is None:
        _verifier_instance = ResponseVerifier()
    return _verifier_instance
