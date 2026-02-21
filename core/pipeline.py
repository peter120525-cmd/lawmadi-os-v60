"""
Lawmadi OS v60 -- 5-Stage Legal Pipeline.
main.py에서 분리됨.

사용법:
    from core.pipeline import set_runtime, set_law_cache, run_legal_pipeline
    set_runtime(RUNTIME)
    set_law_cache(LAW_CACHE, build_cache_context)
"""
import os
import re
import json
import logging
import asyncio
from typing import Any, Dict, List, Optional

import httpx
from google.genai import types as genai_types

from core.constants import DEFAULT_GEMINI_MODEL, LAWMADILM_API_URL
from utils.helpers import _safe_extract_gemini_text, _remove_think_blocks, _safe_extract_json
from prompts.system_instructions import build_system_instruction

logger = logging.getLogger("LawmadiOS.Pipeline")

# ---------------------------------------------------------------------------
# Module-level state (set via setters from main.py)
# ---------------------------------------------------------------------------
_RUNTIME: Dict[str, Any] = {}
_LAW_CACHE: Dict[str, Any] = {}
_build_cache_context_fn = None


# ---------------------------------------------------------------------------
# Setters
# ---------------------------------------------------------------------------

def set_runtime(runtime: Dict[str, Any]) -> None:
    """main.py의 RUNTIME 딕셔너리를 파이프라인 모듈에 주입."""
    global _RUNTIME
    _RUNTIME = runtime


def set_law_cache(law_cache: Dict[str, Any], build_cache_context_fn=None) -> None:
    """main.py의 LAW_CACHE 딕셔너리와 build_cache_context 함수를 주입."""
    global _LAW_CACHE, _build_cache_context_fn
    _LAW_CACHE = law_cache
    _build_cache_context_fn = build_cache_context_fn


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_genai_client(runtime: dict) -> object:
    """Gemini 클라이언트가 초기화되어 있는지 확인 후 반환."""
    gc = runtime.get("genai_client")
    if gc is None:
        raise RuntimeError("Gemini 클라이언트가 초기화되지 않았습니다 (GEMINI_KEY 확인 필요)")
    return gc


# =============================================================
# 응답 모드 프롬프트 상수 (일반 모드 / 전문가 모드)
# =============================================================

GENERAL_MODE_PROMPT = """당신은 법률 문제로 불안해하는 일반인에게 답변하는 Lawmadi OS의 {leader_name} 리더({leader_specialty} 전문)입니다.

[답변 원칙]
1. 결론을 가장 먼저, 3줄 이내로 제시하세요.
2. 법률 용어를 쓸 때는 즉시 괄호 안에 쉽게 풀어 설명하세요.
   예: "임차권등기명령(이사를 가도 보증금을 지켜주는 제도)"
3. 오늘 당장 할 수 있는 구체적 행동을 알려주세요.
   비용, 소요시간, 어디서 하는지까지 포함.
4. 감정에 공감하되 과장하지 마세요. 차분하고 따뜻한 톤.
5. "변호사에게 상담받으세요"로 끝내지 마세요. 무료 지원 기관을 구체적으로 안내.

[가독성 규칙 - 반드시 지킬 것]
- 한 문장은 최대 20~25자. 짧게 끊으세요.
- 문단은 3줄을 절대 넘기지 마세요.
- 긴 설명 대신 소제목, 번호 목록, 체크리스트를 사용하세요.
- 강조가 필요한 부분만 **굵게** 처리하세요.
- 법 조문을 그대로 인용하지 마세요. 쉬운 말로 풀어주세요.
- 모바일 화면에서 읽기 편하게 작성하세요.
- 마지막에 반드시 "지금 해야 할 행동 3가지"를 정리하세요.

[답변 구조 - 반드시 이 순서와 목차 제목을 ## 마크다운 헤더로 사용]

{{사용자 상황에 맞는 한 줄 공감}}
예: "보증금을 못 돌려받고 계신 상황이시군요."

## 결론부터 말씀드리면

핵심 결론 1~2문장 + 근거 법률명.

## 왜 그런가요?

근거 법률을 쉽게 풀어서 설명.
법률 용어는 괄호 안에 쉬운 말 병기.

## 지금 바로 하실 수 있는 일

첫째, (가장 쉬운 행동)
  무엇을, 어디서, 비용, 시간.

둘째, (핵심 법적 조치)
  무엇을, 어디서, 비용, 효과.

셋째, (그래도 해결 안 될 때)
  다음 단계와 예상 소요기간.

## 그래도 해결이 안 되면

최종 수단을 간략히 안내.
예상 비용과 기간 포함.

## 혼자 하기 어려우시면

무료 법률 지원 기관 2곳 이상.
기관명, 전화번호, 이용 조건 포함.

## 지금 해야 할 행동 3가지

1. (가장 급한 행동)
2. (다음으로 할 일)
3. (마지막 준비 사항)

## 법률 근거

인용된 법률명 + 조문번호를 1~2줄로 정리.

담당: {leader_name} 리더 ({leader_specialty} 전문)

[절대 하지 말 것]
- 법률 용어만 나열하고 설명 없이 넘어가기
- "~할 수 있습니다" 반복. 구체적 방법을 말하세요
- 3줄 이상의 긴 문단 작성
- 법 조문 원문 그대로 인용
- "AI", "상담" 표현 사용 금지

[글자수]
2,000~3,000자. 읽는 데 3분 이내.

[톤]
차분하고 따뜻하되 법률 근거는 정확하게.
"~하세요", "~입니다" 존댓말 사용.
"""

EXPERT_MODE_PROMPT = """당신은 법률 전문가에게 분석 보고서를 작성하는 Lawmadi OS의 {leader_name} 리더({leader_specialty} 전문)입니다.

[답변 원칙]
1. 법률 용어를 정확하게 사용하세요. 쉬운 설명은 붙이지 마세요.
2. 모든 주장에 법률 근거(법률명+조문번호)를 명시하세요.
3. 관련 판례가 있으면 반드시 포함하세요 (판례번호+선고일+요지).
4. 반대 견해나 예외 사항도 검토하세요.
5. 실무 절차는 단계별로 구비서류, 비용, 관할, 소요기간까지 포함하세요.

[답변 구조 - 반드시 ## 마크다운 헤더를 사용하세요]

## 사안의 쟁점

본 사안의 핵심 쟁점을 3~5개로 정리.
각 쟁점을 번호와 함께 한 줄로 명시.

## 관련 법령

관련 법률+조문을 중요도 순으로 나열.
각 조문의 핵심 내용을 인용 또는 요약.
조문번호 + 조문 제목 + 내용 형식.

## 판례 검토

관련 판례를 중요도 순으로 나열.
형식: 법원명 + 날짜 + 사건번호 + "판결 요지"
-> 본 사안에의 적용 설명
판례가 SSOT에 없으면 "(※ 법령정보센터에서 확인 필요)" 표기.

## 실무 대응 절차

단계별로 구체적 절차 안내.
각 단계마다: 관할, 구비서류, 비용, 소요기간, 효과

## 쟁점별 검토 의견

각 쟁점에 대한 법률적 분석.
찬반 논거가 있으면 양쪽 모두 검토.

## 결론 및 권고

최종 의견을 2~3문장으로 요약.
권고하는 실무 대응 순서를 명시.
비용·시간 효율 관점의 우선순위 제시.

## 법률 근거

인용된 모든 법률+조문 목록
참조 판례 목록
담당: {leader_name} 리더 ({leader_specialty} 전문)

[절대 하지 말 것]
- 쉬운 말 풀이 (전문가는 알고 있음)
- 감정적 공감 표현 ("걱정되시겠지만" 등)
- 근거 없는 주장
- 존재하지 않는 판례번호나 조문 생성
- "AI", "상담" 표현 사용 금지

[글자수]
4,000~5,000자. 법률 검토서 수준.

[톤]
객관적, 분석적, 정확한. "~이다", "~한다" 또는 "~입니다" 혼용 가능.
법률 의견서/검토서 스타일.
"""


# =============================================================
# 모드별 응답 형식 (Gemini 시스템 지시에 추가)
# =============================================================

GENERAL_RESPONSE_FORMAT = """

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 응답 형식 (일반인 모드)

[답변 원칙]
1. 결론을 가장 먼저, 3줄 이내로 제시하세요.
2. 법률 용어는 사용 즉시 괄호 안에 쉽게 풀어 설명하세요.
3. 오늘 당장 할 수 있는 구체적 행동을 알려주세요.
4. 감정에 공감하되 과장하지 마세요. 차분한 톤.
5. **핵심 키워드만 굵게** 처리하세요.

[가독성 규칙 - 반드시 지킬 것]
- 한 문장은 최대 20~25자. 짧게 끊으세요.
- 문단은 3줄을 절대 넘기지 마세요.
- 긴 설명 대신 소제목/번호 목록/체크리스트를 사용하세요.
- 법 조문 원문을 그대로 인용하지 마세요.
- 모바일 화면 기준으로 작성하세요.

[답변 구조 - 반드시 이 순서와 제목을 ## 마크다운 헤더로 사용]

{{사용자 상황에 맞는 한 줄 공감}}

## 결론부터 말씀드리면
핵심 결론 1~2문장 + 근거 법률명

## 왜 그런가요?
법률 근거를 쉽게 풀어서 설명

## 지금 바로 하실 수 있는 일
첫째/둘째/셋째 -- 구체적 행동 + 비용 + 시간

## 그래도 해결이 안 되면
최종 수단 + 예상 비용/기간

## 혼자 하기 어려우시면
무료 법률 지원 기관 2곳 이상

## 지금 해야 할 행동 3가지
1. (가장 급한 행동)
2. (다음으로 할 일)
3. (마지막 준비 사항)

## 법률 근거
인용된 법률명 + 조문번호 정리

[절대 하지 말 것]
- 3줄 이상의 긴 문단 작성
- 법 조문 원문 그대로 인용
- "AI", "상담" 표현 사용 금지

[글자수] 2,000~3,000자
[톤] 차분하고 따뜻하되 법률 근거는 정확하게
"""

EXPERT_RESPONSE_FORMAT = """

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 응답 형식 (전문가 모드)

[답변 원칙]
1. 법률 용어를 정확하게 사용. 쉬운 설명 불필요.
2. 모든 주장에 법률 근거(법률명+조문번호) 명시.
3. 관련 판례 반드시 포함 (판례번호+선고일+요지).
4. 반대 견해나 예외 사항도 검토.
5. **핵심 쟁점, 법률명, 판례번호, 중요 키워드는 반드시 **굵은 글씨(bold)**로 표시하세요.** 전문가가 빠르게 스캔할 수 있도록 합니다.

[답변 구조 - 반드시 ## 마크다운 헤더를 사용]

## 사안의 쟁점
핵심 쟁점 3~5개 정리

## 관련 법령
법률+조문을 중요도 순으로 나열

## 판례 검토
관련 판례 (법원명+날짜+사건번호+요지)

## 실무 대응 절차
단계별 절차 (관할, 구비서류, 비용, 소요기간, 효과)

## 쟁점별 검토 의견
각 쟁점에 대한 법률적 분석 + 찬반 논거

## 결론 및 권고
최종 의견 요약 + 실무 대응 순서

## 법률 근거
인용된 모든 법률+조문+판례 목록

[글자수] 4,000~5,000자
[톤] 객관적, 분석적, 법률 검토서 스타일
"""


# =============================================================
# Stage 2: LawmadiLM 법률 초안
# =============================================================

async def _call_lawmadilm(query: str, analysis: Dict) -> str:
    """Stage 2: LawmadiLM 법률 초안 (핵심 내용 간결하게)"""
    leader_name = analysis.get("leader_name", "마디")
    leader_specialty = analysis.get("leader_specialty", "통합")

    payload = {
        "messages": [{"role": "user", "content": query}],
        "system_prompt": (
            f"당신은 대한민국 법률 전문 'LawmadiLM'입니다. "
            f"현재 당신은 '{leader_name}' 리더입니다. 전문 분야: {leader_specialty}. "
            f"아래 질문에 대해 핵심 법률 내용을 간결하게 정리하세요: "
            f"적용 법률, 관련 조문, 핵심 판례, 실무 결론을 빠짐없이 포함하되 최대한 간결하게. "
            f"/no_think"
        ),
        "max_tokens": 150,
        "temperature": 0.6,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(f"{LAWMADILM_API_URL}/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()

    content = data.get("answer", "")
    elapsed = data.get("usage", {}).get("elapsed_seconds", 0)
    tokens = data.get("usage", {}).get("completion_tokens", 0)
    logger.info(f"[Stage 2] LawmadiLM 초안 완료 ({elapsed}s, {tokens} tokens)")
    return content


# =============================================================
# Stage 2 후처리
# =============================================================

def _postprocess_lawmadilm(draft: str, query: str) -> Optional[str]:
    """LawmadiLM 초안 후처리: 품질 미달 시 None -> Gemini 전담"""
    if not draft or len(draft.strip()) < 20:
        return None

    # <think> 태그 제거
    draft = _remove_think_blocks(draft)

    # 반복 50% 이상 감지
    sentences = [s.strip() for s in re.split(r'[.\u3002\n]', draft) if s.strip()]
    if sentences:
        unique = set(sentences)
        if len(unique) / len(sentences) < 0.5:
            logger.warning(f"[Stage 2 PP] 반복 감지 ({len(unique)}/{len(sentences)}) -> None")
            return None

    # SSOT에 없는 "OO법 제X조" -> "(※확인 필요)" 태그
    law_refs = re.findall(r'([가-힣]+법)\s+제(\d+)조', draft)
    for law_name, article_num in law_refs:
        # _LAW_CACHE에서 확인
        found = False
        for stype, type_data in _LAW_CACHE.items():
            if law_name in type_data.get("entries", {}):
                found = True
                break
        if not found:
            draft = draft.replace(
                f"{law_name} 제{article_num}조",
                f"{law_name} 제{article_num}조(※확인 필요)"
            )

    return draft.strip()


# =============================================================
# Stage 3: Gemini Flash 메인 콘텐츠 작성
# =============================================================

async def _step3_gemini_compose(query: str, analysis: Dict, draft: str,
                                 tools: list, gemini_history: list,
                                 now_kst: str, ssot_available: bool,
                                 lang: str = "", mode: str = "general") -> str:
    """Stage 3: Gemini Flash 메인 콘텐츠 작성 (일반: 3000, 전문가: 4000 토큰)"""
    gc = _ensure_genai_client(_RUNTIME)
    model_name = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    leader_name = analysis.get("leader_name", "마디")
    leader_specialty = analysis.get("leader_specialty", "통합")

    # 캐시 컨텍스트: 관련 SSOT 소스 사전 매칭
    cache_ctx = _build_cache_context_fn(query) if _build_cache_context_fn else ""

    # draft가 있으면 system_instruction에 포함
    draft_section = ""
    if draft and draft.strip():
        draft_section = (
            f"\n[LawmadiLM 초안]\n{draft}\n\n"
            f"위 초안을 바탕으로 사용자에게 전달할 완성된 법률 답변을 작성하세요.\n"
            f"- 초안의 법률 근거(조문, 판례)를 검증하고 보완하세요\n"
            f"- DRF API 도구로 법령/판례를 실시간 확인하세요\n"
            f"- SSOT 조문만 인용하세요. 없는 조문 절대 금지.\n"
            f"- 구조: 상황정리->법률근거->실무가이드->주의사항\n"
            f"- [{leader_name} ({leader_specialty}) 분석]으로 시작하세요"
        )
    else:
        draft_section = (
            f"\n사용자에게 전달할 완성된 법률 답변을 직접 작성하세요.\n"
            f"- DRF API 도구로 법령/판례를 실시간 확인하세요\n"
            f"- SSOT 조문만 인용하세요. 없는 조문 절대 금지.\n"
            f"- 구조: 상황정리->법률근거->실무가이드->주의사항\n"
            f"- [{leader_name} ({leader_specialty}) 분석]으로 시작하세요"
        )

    # English language instruction
    lang_instruction = ""
    if lang == "en":
        lang_instruction = "\n\nIMPORTANT: Respond entirely in English. Translate Korean legal terms with the original Korean in parentheses."

    instruction = (
        f"{build_system_instruction(mode)}\n"
        f"현재 당신은 '{leader_name}' 리더입니다.\n"
        f"전문 분야: {leader_specialty}\n"
        f"질문 요약: {analysis.get('summary', '')}"
        f"{draft_section}"
        f"{lang_instruction}"
    )
    if cache_ctx:
        instruction += f"\n\n{cache_ctx}"
    gen_config = genai_types.GenerateContentConfig(
        tools=tools,
        system_instruction=instruction,
        max_output_tokens=4000 if mode == "expert" else 3000,
        automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=False),
    )

    chat = gc.chats.create(
        model=model_name,
        config=gen_config,
        history=gemini_history,
    )
    resp = chat.send_message(
        f"now_kst={now_kst}\nssot_available={ssot_available}\n사용자 질문: {query}"
    )
    return _safe_extract_gemini_text(resp)


# =============================================================
# Stage 4: Claude 보강
# =============================================================

async def _step4_claude_enhance(query: str, analysis: Dict,
                                 gemini_text: str, mode: str = "general") -> str:
    """Stage 4: Claude 보강 -- Gemini 메인 응답의 구조/가독성/법률 정확성을 보강 (원본 유지 기반)"""
    claude_client = _RUNTIME.get("claude_client")
    if not claude_client:
        return ""

    # Gemini 응답이 너무 짧으면 보강 불필요
    if len(gemini_text.strip()) < 100:
        return ""

    leader_name = analysis.get("leader_name", "마디")
    leader_specialty = analysis.get("leader_specialty", "통합")

    try:
        if mode == "expert":
            max_tokens = 5000
            enhance_instruction = (
                f"당신은 Lawmadi OS의 법률 품질 보강 엔진입니다.\n"
                f"아래 Gemini 메인 응답을 **원본 구조와 내용을 유지하면서** 보강하세요.\n\n"
                f"[보강 규칙]\n"
                f"1. 원본의 법률 근거(조문, 판례)를 그대로 유지하세요.\n"
                f"2. 빠진 섹션이 있으면 추가하세요: 사안의 쟁점, 관련 법령, 판례 검토, 실무 대응 절차, 쟁점별 검토 의견, 결론 및 권고, 법률 근거\n"
                f"3. 법률 용어의 정확성을 검증하고 보완하세요.\n"
                f"4. 4,000~5,000자 분량으로 보강하세요.\n"
                f"5. 담당: {leader_name} 리더 ({leader_specialty} 전문)\n"
            )
        else:
            max_tokens = 3000
            enhance_instruction = (
                f"당신은 Lawmadi OS의 법률 품질 보강 엔진입니다.\n"
                f"아래 Gemini 메인 응답을 **원본 구조와 내용을 유지하면서** 보강하세요.\n\n"
                f"[보강 규칙]\n"
                f"1. 원본의 법률 근거(조문, 판례)를 그대로 유지하세요.\n"
                f"2. 빠진 섹션이 있으면 추가하세요: 결론부터 말씀드리면, 왜 그런가요?, 지금 바로 하실 수 있는 일, 그래도 해결이 안 되면, 혼자 하기 어려우시면, 지금 해야 할 행동 3가지, 법률 근거\n"
                f"3. 한 문장은 20~25자 이내, 문단은 3줄 이내로 정리하세요.\n"
                f"4. 법률 용어는 괄호 안에 쉬운 설명을 붙이세요.\n"
                f"5. 2,000~3,000자 분량으로 보강하세요.\n"
                f"6. 담당: {leader_name} 리더 ({leader_specialty} 전문)\n"
            )

        enhance_resp = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=enhance_instruction,
            messages=[{
                "role": "user",
                "content": f"사용자 질문: {query}\n\n[Gemini 메인 응답]\n{gemini_text}\n\n위 응답을 보강하세요."
            }],
        )
        enhanced = enhance_resp.content[0].text.strip()
        if not enhanced or len(enhanced) < len(gemini_text) * 0.5:
            # 보강 결과가 원본보다 크게 짧으면 원본 유지
            return ""
        return enhanced
    except Exception as e:
        logger.warning(f"[Stage 4] Claude 보강 실패 (Gemini 원본 유지): {e}")
        return ""


# =============================================================
# DRF 검증: 법률 참조 확인
# =============================================================

def _drf_verify_law_refs(text: str) -> list:
    """응답에서 'OO법 제X조' 최대 5개 추출 -> DRF API 존재 확인"""
    refs = re.findall(r'([가-힣]+법)\s+제(\d+)조', text)
    if not refs:
        return []

    results = []
    svc = _RUNTIME.get("search_service")
    if not svc:
        return []

    seen = set()
    for law_name, article in refs[:5]:
        key = f"{law_name} 제{article}조"
        if key in seen:
            continue
        seen.add(key)
        try:
            raw = svc.search_law(law_name)
            found = bool(raw)
            results.append({"ref": key, "verified": found})
        except Exception:
            results.append({"ref": key, "verified": False})

    return results


# =============================================================
# Stage 5: 헌법 검증 + 법률 품질 검증 + 교정
# =============================================================

async def _step5_claude_verify(query: str, response_text: str, drf_results: list = None) -> Dict[str, Any]:
    """Stage 5: 헌법 검증 + 법률 품질 검증 + 교정 (max_tokens=300)"""
    claude_client = _RUNTIME.get("claude_client")
    if not claude_client:
        return {"passed": False, "warning": "Claude 검증 엔진 미초기화 (Fail-Closed)", "corrected_text": None}

    if drf_results is None:
        drf_results = []

    try:
        resp = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=(
                "당신은 헌법 준수 및 법률 품질 검증 엔진입니다. 아래 법률 응답을 검증하세요.\n"
                "검증 항목:\n"
                "1. 헌법 준수: 기본권 침해, 위헌 판례 인용 여부\n"
                "2. 법률 정확성: 조문번호 오류, 폐지/개정 법률 인용 여부\n"
                "3. 실무 유용성: 구체적 행동 가이드 포함 여부\n\n"
                f"[DRF 검증 결과]\n{json.dumps(drf_results, ensure_ascii=False)}\n\n"
                "JSON으로만 응답:\n"
                '{"passed": true/false, "constitutional": "PASS/FAIL", '
                '"accuracy": "PASS/FAIL", "usefulness": "PASS/FAIL", '
                '"warning": "경고 메시지 또는 null"}'
            ),
            messages=[{
                "role": "user",
                "content": f"질문: {query}\n\n응답:\n{response_text[:3000]}"
            }],
        )
        text = resp.content[0].text.strip()
        parsed = _safe_extract_json(text)
        result = {"passed": False, "warning": "Claude 검증 JSON 파싱 실패 (Fail-Closed)", "corrected_text": None}
        if parsed:
            result = parsed
            result.setdefault("corrected_text", None)

        # FAIL 시 교정 (차단 아님)
        if not result.get("passed", False):
            try:
                corrected = claude_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=300,
                    system="헌법 위배 사항을 수정하여 교정된 답변을 출력하세요.",
                    messages=[{
                        "role": "user",
                        "content": f"원본: {response_text}\n위반사항: {result.get('warning')}"
                    }],
                )
                result["corrected_text"] = corrected.content[0].text.strip()
                logger.info("[Stage 5] 헌법 위반 교정 완료")
            except Exception as ce:
                logger.warning(f"[Stage 5] 헌법 교정 실패: {ce}")

        return result
    except Exception as e:
        logger.warning(f"[Stage 5] 헌법 검증 실패 (Fail-Closed): {e}")

    return {"passed": False, "warning": "Claude 검증 예외 발생 (Fail-Closed)", "corrected_text": None}


# =============================================================
# Main Pipeline Orchestrator
# =============================================================

async def _run_legal_pipeline(query: str, analysis: Dict, tools: list,
                               gemini_history: list, now_kst: str,
                               ssot_available: bool, lang: str = "",
                               mode: str = "general") -> str:
    """5-Stage Legal Pipeline: LawmadiLM 초안 -> Gemini 작성 -> Claude 보강 -> Claude 검증"""
    leader_name = analysis.get("leader_name", "마디")
    leader_specialty = analysis.get("leader_specialty", "통합")

    # -- Stage 2: LawmadiLM 법률 초안 --
    draft = ""
    try:
        logger.info("[Stage 2/5] LawmadiLM 법률 초안 생성")
        draft = await _call_lawmadilm(query, analysis)
        draft = _postprocess_lawmadilm(draft, query)  # 후처리
        if not draft:
            logger.warning("[Stage 2] 후처리 -> None -> Gemini 전담")
            draft = ""
    except Exception as e:
        logger.warning(f"[Stage 2] LawmadiLM 실패 ({e}) -> Stage 3에서 Gemini 단독 처리")
        draft = ""

    # -- Stage 3: Gemini Flash 콘텐츠 작성 --
    logger.info(f"[Stage 3/5] Gemini Flash 콘텐츠 작성 (draft={'있음' if draft else '없음'})")
    gemini_text = await _step3_gemini_compose(
        query, analysis, draft, tools, gemini_history, now_kst, ssot_available, lang=lang, mode=mode
    )

    # 응답이 너무 짧으면 draft 없이 재시도
    if len(gemini_text.strip()) < 50 and draft:
        logger.warning(f"[Stage 3] 응답 너무 짧음 ({len(gemini_text)}자), draft 없이 재시도")
        gemini_text = await _step3_gemini_compose(
            query, analysis, "", tools, gemini_history, now_kst, ssot_available, lang=lang, mode=mode
        )

    # -- Stage 4: Claude 모드별 답변 생성 --
    logger.info(f"[Stage 4/5] Claude 모드별 답변 생성 (mode={mode})")
    enhanced_text = await _step4_claude_enhance(query, analysis, gemini_text, mode=mode)

    if enhanced_text:
        final_text = enhanced_text  # 대체 (append 아님)
    else:
        final_text = gemini_text    # 실패 시 원본 유지

    # -- Stage 5: DRF 검증 + 헌법 검증 + 교정 --
    logger.info("[Stage 5/5] DRF 검증 + 헌법 검증 + 교정")
    drf_results = _drf_verify_law_refs(final_text)
    verification = await _step5_claude_verify(query, final_text, drf_results)

    if not verification.get("passed", False):
        logger.warning(f"[Stage 5] 헌법 검증 경고: {verification}")
        if verification.get("corrected_text"):
            final_text = verification["corrected_text"]
            final_text += "\n\n> 이 답변은 헌법 검증 후 교정되었습니다. 전문가 확인을 권장합니다."
        else:
            final_text += "\n\n> 이 답변에는 헌법적 검토가 필요한 사항이 포함되어 있습니다. 전문가 확인을 권장합니다."
    elif verification.get("warning"):
        final_text += f"\n\n---\n**헌법 검증 참고사항:** {verification['warning']}"

    return final_text


# Public alias for external use
run_legal_pipeline = _run_legal_pipeline
