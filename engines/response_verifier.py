#!/usr/bin/env python3
"""
Response Verification Engine
Claude API를 사용하여 Gemini 응답의 SSOT 준수 여부를 검증
"""
import os
import logging
import anthropic
from typing import Dict, Any, List, Optional
import json

logger = logging.getLogger(__name__)

class ResponseVerifier:
    """
    Gemini 응답 검증기
    - DRF API 데이터 사용 여부 확인
    - 환각(hallucination) 감지
    - SSOT 원칙 준수 검증
    """

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.enabled = bool(self.api_key)

        if self.enabled:
            self.client = anthropic.Anthropic(api_key=self.api_key)
            logger.info("✅ [Verifier] Claude API 초기화 완료")
        else:
            logger.warning("⚠️ [Verifier] ANTHROPIC_API_KEY 미설정 - 검증 비활성화")

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
                "feedback": "검증기 비활성화됨 (ANTHROPIC_API_KEY 미설정)",
                "ssot_compliance_score": 0
            }

        try:
            # Claude에게 검증 요청
            verification_prompt = self._build_verification_prompt(
                user_query, gemini_response, tools_used, tool_results
            )

            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2000,
                temperature=0,  # 일관된 검증을 위해 temperature=0
                messages=[{
                    "role": "user",
                    "content": verification_prompt
                }]
            )

            # Claude의 응답 파싱
            verification_text = response.content[0].text
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
            results_summary.append(f"{i}. 상태: {result_status}, 출처: {result_source}")

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
        """Claude의 검증 응답 파싱"""
        try:
            # JSON 추출 (```json ``` 마크다운 제거)
            if "```json" in text:
                json_start = text.find("```json") + 7
                json_end = text.find("```", json_start)
                json_text = text[json_start:json_end].strip()
            elif "```" in text:
                json_start = text.find("```") + 3
                json_end = text.find("```", json_start)
                json_text = text[json_start:json_end].strip()
            else:
                json_text = text.strip()

            result = json.loads(json_text)

            # 기본값 설정
            if "result" not in result:
                result["result"] = "WARNING"
            if "ssot_compliance_score" not in result:
                result["ssot_compliance_score"] = 50
            if "issues" not in result:
                result["issues"] = []
            if "feedback" not in result:
                result["feedback"] = "검증 완료"

            return result

        except Exception as e:
            logger.error(f"⚠️ [Verifier] 응답 파싱 실패: {e}")
            return {
                "result": "ERROR",
                "issues": [f"파싱 오류: {str(e)}"],
                "feedback": text[:500],  # 원본 텍스트 일부 저장
                "ssot_compliance_score": 0
            }


# 싱글톤 인스턴스
_verifier_instance = None

def get_verifier() -> ResponseVerifier:
    """검증기 싱글톤 인스턴스 반환"""
    global _verifier_instance
    if _verifier_instance is None:
        _verifier_instance = ResponseVerifier()
    return _verifier_instance
