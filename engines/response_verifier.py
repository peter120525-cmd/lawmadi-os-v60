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

        prompt = f"""당신은 법률 AI 시스템의 품질 검증 담당자입니다.
아래 Gemini의 응답이 **SSOT (Single Source of Truth) 원칙**을 준수했는지 검증하십시오.

# SSOT 원칙 (claude.md 기준)
1. **실수는 허용되지 않는다**: 부정확한 정보는 사용자의 인생을 잘못된 방향으로 이끈다
2. **확인되지 않은 정보는 절대 확정적으로 제공하지 않는다** (Fail-Closed)
3. **모든 법률 정보는 DRF API를 통해 검증된 데이터만 사용**
4. **환각(hallucination) 금지**: 임의로 법령명, 조문, 판례를 만들어내면 안 됨

---

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

## Tool 실행 결과
{results_text}

---

# 검증 항목

1. **DRF API 사용 여부**
   - Tool 함수를 호출했는가?
   - Tool 결과가 "FOUND"인가?
   - Tool을 호출하지 않고 답변했다면 → FAIL

2. **환각 감지**
   - 응답에 나온 법령명/조문/판례가 Tool 결과에 실제로 있는가?
   - Tool 결과에 없는 정보를 임의로 추가했는가?
   - 예시: Tool에서 "민법 제650조"를 찾았는데, 응답에서 "제651조"를 언급 → FAIL
   - ⚠️ 항/호/목 검증: Tool 결과에 "조문 본문"이 포함된 경우, 응답이 인용한 항·호·목이 본문에 실제로 존재하는지 대조하라. 본문에 "①", "②", "1.", "제1항" 등이 있으면 해당 항 인용은 정당. 본문에 없는 항/호를 인용하면 → FAIL.
   - 조문 본문이 없는 경우: 상위 조문이 FOUND이면 항/호/목 참조는 WARNING (FAIL이 아님).
   - ⚠️ **판례/헌재결정례 내용 검증**: Tool 결과에 "판시사항/판결요지"가 포함된 경우:
     a. 응답이 해당 판례의 내용을 설명할 때, 판시사항/판결요지와 실질적으로 일치하는지 대조
     b. 판시사항에 없는 내용을 판례 해석으로 제시하면 → FAIL
     c. 판례번호가 FOUND이지만 판시사항/판결요지와 내용이 다르면 → FAIL (번호만 맞고 내용 불일치)
     d. 헌법재판소 결정(헌재)도 동일 기준 적용: 결정요지와 응답 내용 대조

3. **출처 명확성**
   - 응답이 Tool 결과의 출처를 정확히 반영하는가?
   - "국가법령정보센터"와 같은 출처 표기가 있는가?

4. **Fail-Closed 준수**
   - Tool 결과가 "NO_DATA"일 때 확정적으로 답변하지 않았는가?
   - "해당 법령이 없습니다" vs "제XX조에 따르면..." (후자는 FAIL)

---

# 응답 형식 (JSON)

아래 JSON 형식으로만 답변하십시오:

{{
  "result": "PASS" | "WARNING" | "FAIL",
  "ssot_compliance_score": 0-100,
  "issues": [
    "발견된 문제점 1",
    "발견된 문제점 2"
  ],
  "feedback": "검증 피드백 (1-2문장)"
}}

**판단 기준:**
- PASS (90-100점): DRF API 사용, 환각 없음, 출처 명확
- WARNING (60-89점): DRF API 사용했으나 일부 불명확한 표현 존재
- FAIL (0-59점): DRF API 미사용 또는 환각 감지

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
