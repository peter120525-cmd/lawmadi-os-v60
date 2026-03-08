"""
Lawmadi OS v60 — 리더 협의(Deliberation) & 인수인계(Handoff) 시스템.

CSO 서연이 주재하는 리더 회의 과정을 사용자에게 채팅 형식으로 보여주고,
이후 질문에서는 리더 간 인수인계 과정도 표시.

v2: 턴별 개별 Gemini 호출 + 실제 리더 페르소나 주입.
    JSON 모드 완전 제거 → plain text → Python dict 조립.
"""
import json
import logging
import asyncio
import os
import re
from typing import AsyncGenerator, Dict, List, Optional

from core.model_fallback import get_model, on_quota_error, is_quota_error, _RETRY_BASE_SEC
from core.pipeline import _build_leader_persona, _load_leader_profiles
from utils.helpers import _safe_extract_gemini_text, _remove_think_blocks

logger = logging.getLogger("LawmadiOS.Deliberation")

# 협의 타임아웃 (초)
_DELIBERATION_TIMEOUT = 8
_HANDOFF_TIMEOUT = 8
_TURN_TIMEOUT = 5  # 개별 턴 타임아웃 (초)

# 이름 → ID 역매핑 캐시
_NAME_TO_ID: Dict[str, str] = {}


def _build_name_to_id_map() -> Dict[str, str]:
    """leader-profiles.json + leaders.json 기반 이름→ID 역매핑 구축."""
    global _NAME_TO_ID
    if _NAME_TO_ID:
        return _NAME_TO_ID

    mapping: Dict[str, str] = {}
    # leaders.json에서 이름 로드
    try:
        base = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(base, "leaders.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # core_registry (CSO/CTO/CCO)
        for lid, info in data.get("core_registry", {}).items():
            name = info.get("name", "")
            if name:
                mapping[name] = lid
        # swarm_engine_config.leader_registry (L01-L60)
        registry = data.get("swarm_engine_config", {}).get("leader_registry", {})
        for lid, info in registry.items():
            name = info.get("name", "")
            if name:
                mapping[name] = lid
    except Exception as e:
        logger.warning(f"[Deliberation] leaders.json 로드 실패: {e}")

    _NAME_TO_ID = mapping
    return _NAME_TO_ID


def _name_to_id(name: str) -> str:
    """리더 이름 → ID 변환 (없으면 빈 문자열)."""
    mapping = _build_name_to_id_map()
    return mapping.get(name, "")


def _build_cso_persona() -> str:
    """CSO 서연의 페르소나 텍스트 (회의 진행자 역할)."""
    profiles = _load_leader_profiles()
    p = profiles.get("CSO")
    if not p:
        return "CSO 서연: Lawmadi OS 전략 총괄. 리더 회의를 주재합니다."
    parts = []
    if p.get("hero"):
        parts.append(f"신조: {p['hero']}")
    identity = p.get("identity", {})
    if identity.get("what"):
        parts.append(f"역할: {identity['what']}")
    if p.get("philosophy"):
        parts.append(f"철학: {p['philosophy']}")
    if not parts:
        return "CSO 서연: Lawmadi OS 전략 총괄."
    return "CSO 서연\n" + "\n".join(parts)


async def _single_leader_call(
    gc,
    persona: str,
    prompt: str,
    max_tokens: int = 300,
    temp: float = 0.5,
) -> str:
    """
    단일 리더 plain text Gemini 호출.
    JSON 모드 없음. 200자 truncate.
    thinking 비활성화 — 협의 대사는 간단한 대화문이므로 추론 불필요.
    """
    from google.genai import types as genai_types

    from core.constants import USE_VERTEX_AI

    full_prompt = f"[페르소나]\n{persona}\n\n[지시]\n{prompt}"
    model_name = get_model()

    # Safety settings: 법률 상담 주제 차단 방지 (Vertex AI 모드)
    safety_settings = None
    if USE_VERTEX_AI:
        safety_settings = [
            genai_types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="BLOCK_ONLY_HIGH",
            ),
            genai_types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="BLOCK_ONLY_HIGH",
            ),
            genai_types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_ONLY_HIGH",
            ),
            genai_types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="BLOCK_MEDIUM_AND_ABOVE",
            ),
        ]

    def _sync_call():
        import time as _time
        for _attempt in range(3):
            try:
                return gc.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                    config=genai_types.GenerateContentConfig(
                        max_output_tokens=max_tokens,
                        temperature=temp,
                        thinking_config=genai_types.ThinkingConfig(
                            thinking_budget=0,
                        ),
                        safety_settings=safety_settings,
                    ),
                )
            except Exception as e:
                if is_quota_error(e) and _attempt < 2:
                    wait = _RETRY_BASE_SEC * (2 ** _attempt)
                    _time.sleep(wait)
                    continue
                raise

    loop = asyncio.get_running_loop()
    resp = await loop.run_in_executor(None, _sync_call)

    text = _safe_extract_gemini_text(resp).strip()
    text = _remove_think_blocks(text).strip()
    # "변호사" 명칭 사용 금지 — 후처리 안전장치
    text = re.sub(r'변호사', '전문가', text)
    return text


def should_deliberate(
    query: str,
    is_legal: bool,
    is_first_question: bool,
    current_leader: Optional[str],
    new_leader_name: str,
    is_name_call: bool,
) -> str:
    """
    협의/인수인계 필요 여부 판단.

    Returns:
        "full"    — 첫 질문, CSO 주재 리더 회의
        "handoff" — 기존 리더 → 새 리더 인수인계
        "none"    — 회의 없이 바로 진행
    """
    # 비법률 질문 → 회의 없음
    if not is_legal:
        return "none"

    # 이름 직접 호출 → 회의 없음
    if is_name_call:
        return "none"

    # 첫 질문 (current_leader 없음) → 풀 회의
    if is_first_question or not current_leader:
        return "full"

    # 같은 리더가 계속 → 회의 없음
    if current_leader == new_leader_name:
        return "none"

    # 다른 리더로 변경 → 인수인계
    return "handoff"


async def generate_deliberation(
    gc,
    query: str,
    leaders: List[Dict],
    lang: str = "",
) -> Optional[List[Dict]]:
    """
    CSO 서연 주재 리더 회의 — 9턴 (후보 간 협의 전 과정 표시, 10턴 이내).

    Turn 1: CSO 서연 → 질문 요약 + 후보 소개 + B에게 의견 요청
    Turn 2: 후보 B → 자기 분야 관점 의견
    Turn 3: CSO → A에게도 의견 요청
    Turn 4: 담당 A → 본인이 적합한 이유
    Turn 5: 후보 B → A에게 보충 질문/의견
    Turn 6: 담당 A → B에게 답변 + 구체적 접근법
    Turn 7: 후보 B → 동의/양보
    Turn 8: CSO 서연 → 담당 리더 공식 지명
    Turn 9: 담당 A → 사용자 인사 + 접근법 (is_final)
    """
    if not gc or not leaders:
        return None

    selected = leaders[0]
    sel_name = selected.get("name", "?")
    sel_spec = selected.get("specialty", "")
    sel_id = selected.get("leader_id", "") or _name_to_id(sel_name)

    has_alt = len(leaders) >= 2
    if has_alt:
        alt = leaders[1]
        alt_name = alt.get("name", "?")
        alt_spec = alt.get("specialty", "")
        alt_id = alt.get("leader_id", "") or _name_to_id(alt_name)
    else:
        alt_name = alt_spec = alt_id = ""

    cso_p = _build_cso_persona()
    sel_p = _build_leader_persona(sel_id) if sel_id else f"{sel_name}: {sel_spec} 전문 리더"
    alt_p = (_build_leader_persona(alt_id) if alt_id else f"{alt_name}: {alt_spec} 전문 리더") if has_alt else ""

    turns: List[Dict] = []
    _en = lang == "en"
    _cso = "Seoyeon" if _en else "서연"
    _base = "[External client question.]\n" if _en else "[외부 의뢰인 질문입니다.]\n"
    _q = f"Question: {query[:300]}\n" if _en else f"질문: {query[:300]}\n"
    _style_en = "2-3 sentences. English only. Use 'leader'/'expert', never 'lawyer'."
    _style_ko = "100~150자. 존댓말, 따뜻하고 전문적 톤. '변호사' 금지, '리더'/'전문가' 사용. 완전한 문장."
    _short_en = "1-2 sentences. English only. Use 'leader'/'expert', never 'lawyer'."
    _short_ko = "80~120자. 존댓말. '변호사' 금지, '리더'/'전문가' 사용. 완전한 문장."

    async def _call(persona, prompt):
        try:
            return await asyncio.wait_for(_single_leader_call(gc, persona, prompt), timeout=_TURN_TIMEOUT)
        except Exception:
            return ""

    try:
        # ── Turn 1: CSO — 질문 요약 + 후보 소개 ──
        if has_alt:
            p1 = (f"{_base}{_q}Candidates: {sel_name}({sel_spec}), {alt_name}({alt_spec})\n\n"
                  f"You are CSO Seoyeon. Summarize the question, introduce both candidates, ask {alt_name} for their view first. {_style_en}"
                  if _en else
                  f"{_base}{_q}후보: {sel_name}({sel_spec}), {alt_name}({alt_spec})\n\n"
                  f"당신은 CSO 서연. 질문 핵심을 요약하고, 두 후보를 소개한 뒤 {alt_name}님에게 먼저 의견을 요청하세요. {_style_ko}")
        else:
            p1 = (f"{_base}{_q}Designated leader: {sel_name}({sel_spec})\n\n"
                  f"You are CSO Seoyeon. Summarize the question, explain why {sel_spec} expertise is needed, ask {sel_name} for input. {_style_en}"
                  if _en else
                  f"{_base}{_q}지정 리더: {sel_name}({sel_spec})\n\n"
                  f"당신은 CSO 서연. 질문 핵심을 요약하고, {sel_spec} 전문가가 필요한 이유를 설명한 뒤 {sel_name}님에게 의견 요청. {_style_ko}")
        t1 = await _call(cso_p, p1) or (
            f"This question involves {sel_spec}. {alt_name if has_alt else sel_name}, please share your view."
            if _en else f"이 질문은 {sel_spec} 분야입니다. {alt_name if has_alt else sel_name}님, 의견 부탁드립니다.")
        turns.append({"speaker": _cso, "role": "CSO", "text": t1, "is_final": False})

        if has_alt:
            # ── Group 2: T2 (B 의견) ──
            p2 = (f"{_base}{_q}CSO asked for your perspective.\n\nYou are {alt_name} ({alt_spec} expert). "
                  f"Share your view on this question from your specialty. {_style_en}"
                  if _en else
                  f"{_base}{_q}CSO 서연이 의견을 요청했습니다.\n\n당신은 {alt_name}({alt_spec} 전문). "
                  f"자기 분야 관점에서 이 질문에 대한 의견을 말씀하세요. {_style_ko}")
            t2 = await _call(alt_p, p2) or (
                f"From {alt_spec} perspective, this is an important question."
                if _en else f"{alt_spec} 관점에서 중요한 질문입니다.")
            turns.append({"speaker": alt_name, "role": alt_spec, "text": t2, "is_final": False})

            # ── Group 3: T3 (CSO→A 요청) + T4 (A 의견) 병렬 ──
            p3 = (f"{alt_name} shared their view. You are CSO Seoyeon. Now ask {sel_name} for their perspective too. {_short_en}"
                  if _en else
                  f"{alt_name}님이 의견을 말했습니다. 당신은 CSO 서연. 이제 {sel_name}님에게도 의견을 요청하세요. {_short_ko}")
            p4 = (f"{_base}{_q}{alt_name}({alt_spec}) shared their view. CSO asked you too.\n\nYou are {sel_name} ({sel_spec} expert). "
                  f"Explain why this question falls in your area and how you can specifically help. {_style_en}"
                  if _en else
                  f"{_base}{_q}{alt_name}({alt_spec})님이 의견을 말했습니다. CSO가 당신에게도 의견을 요청합니다.\n\n당신은 {sel_name}({sel_spec} 전문). "
                  f"왜 이 질문이 자기 분야에 해당하는지, 어떻게 구체적으로 도울 수 있는지 설명하세요. {_style_ko}")
            r34 = await asyncio.gather(_call(cso_p, p3), _call(sel_p, p4), return_exceptions=True)
            t3 = r34[0] if isinstance(r34[0], str) and r34[0] else (
                f"{sel_name}, could you share your perspective?" if _en else f"{sel_name}님도 의견 부탁드립니다.")
            t4 = r34[1] if isinstance(r34[1], str) and r34[1] else (
                f"This falls right in my area — I can help specifically." if _en
                else f"이 질문은 제 분야에 해당하며, 구체적으로 도와드릴 수 있습니다.")
            turns.append({"speaker": _cso, "role": "CSO", "text": t3, "is_final": False})
            turns.append({"speaker": sel_name, "role": sel_spec, "text": t4, "is_final": False})

            # ── Group 4: T5 (B 보충 질문) + T6 (A 답변) 병렬 ──
            p5 = (f"You are {alt_name} ({alt_spec}). {sel_name} explained their view. "
                  f"Ask a follow-up question or share additional insight from {alt_spec} that may help. {_short_en}"
                  if _en else
                  f"당신은 {alt_name}({alt_spec}). {sel_name}님이 의견을 설명했습니다. "
                  f"{alt_spec} 관점에서 보충 질문이나 추가 의견을 말씀하세요. {_short_ko}")
            p6 = (f"{_base}{_q}You are {sel_name} ({sel_spec}). {alt_name} asked a follow-up. "
                  f"Respond with your specific approach and concrete plan. {_style_en}"
                  if _en else
                  f"{_base}{_q}당신은 {sel_name}({sel_spec}). {alt_name}님이 보충 질문을 했습니다. "
                  f"구체적인 접근법과 계획으로 답변하세요. {_style_ko}")
            r56 = await asyncio.gather(_call(alt_p, p5), _call(sel_p, p6), return_exceptions=True)
            t5 = r56[0] if isinstance(r56[0], str) and r56[0] else (
                f"That's a solid approach. How would you handle the specific details?" if _en
                else f"좋은 접근이네요. 구체적인 세부 사항은 어떻게 처리하실 건가요?")
            t6 = r56[1] if isinstance(r56[1], str) and r56[1] else (
                f"I'll address each point systematically." if _en
                else f"각 사안을 체계적으로 검토하겠습니다.")
            turns.append({"speaker": alt_name, "role": alt_spec, "text": t5, "is_final": False})
            turns.append({"speaker": sel_name, "role": sel_spec, "text": t6, "is_final": False})

            # ── Group 5: T7 (B 양보) + T8 (CSO 지명) + T9 (A 인사) 병렬 ──
            p7 = (f"You are {alt_name} ({alt_spec}). {sel_name} gave a thorough response. "
                  f"Agree that {sel_name} is the right leader and express confidence. {_short_en}"
                  if _en else
                  f"당신은 {alt_name}({alt_spec}). {sel_name}님이 충실히 답변했습니다. "
                  f"{sel_name}님이 적임자라는 데 동의하고 신뢰를 표현하세요. {_short_ko}")
            p8 = (f"Both leaders discussed thoroughly. {alt_name} agreed {sel_name} is best.\n\n"
                  f"You are CSO Seoyeon. Officially designate {sel_name} as the assigned leader. Reassure the user. {_style_en}"
                  if _en else
                  f"두 리더가 충분히 논의했고, {alt_name}님이 {sel_name}님에게 양보했습니다.\n\n"
                  f"당신은 CSO 서연. {sel_name}님을 담당 리더로 공식 지명하세요. 사용자에게 안심 메시지도. {_style_ko}")
            p9 = (f"You've been designated as leader.\n{_q}\nYou are {sel_name} ({sel_spec}). "
                  f"Greet the user warmly and briefly explain how you'll help. {_style_en}"
                  if _en else
                  f"당신이 담당 리더로 지명되었습니다.\n{_q}\n당신은 {sel_name}({sel_spec}). "
                  f"사용자에게 따뜻하게 인사하고 어떻게 도와드릴지 간략히 말씀하세요. {_short_ko}")
            r789 = await asyncio.gather(_call(alt_p, p7), _call(cso_p, p8), _call(sel_p, p9), return_exceptions=True)
            t7 = r789[0] if isinstance(r789[0], str) and r789[0] else (
                f"I agree — {sel_name} is the perfect fit." if _en else f"저도 동의합니다. {sel_name}님이 적임자입니다.")
            t8 = r789[1] if isinstance(r789[1], str) and r789[1] else (
                f"{sel_name} will be your assigned leader." if _en else f"{sel_name}님이 담당하시겠습니다.")
            t9 = r789[2] if isinstance(r789[2], str) and r789[2] else (
                f"Hello, I'll take care of this for you right away." if _en else f"안녕하세요, 바로 도와드리겠습니다.")
            turns.append({"speaker": alt_name, "role": alt_spec, "text": t7, "is_final": False})
            turns.append({"speaker": _cso, "role": "CSO", "text": t8, "is_final": False})
            turns.append({"speaker": sel_name, "role": sel_spec, "text": t9, "is_final": True})

        else:
            # 후보 없음 — CSO + 리더 A 대화 (7턴)
            p2 = (f"{_base}{_q}You are CSO Seoyeon. Ask {sel_name} what specific approach they'd take. {_short_en}"
                  if _en else
                  f"{_base}{_q}당신은 CSO 서연. {sel_name}님에게 어떤 접근법을 취할 것인지 구체적으로 물어보세요. {_short_ko}")
            p3 = (f"{_base}{_q}CSO asked about your approach.\n\nYou are {sel_name} ({sel_spec} expert). "
                  f"Explain your specific approach and why your expertise fits. {_style_en}"
                  if _en else
                  f"{_base}{_q}CSO가 접근법을 물었습니다.\n\n당신은 {sel_name}({sel_spec} 전문). "
                  f"구체적 접근법과 자기 전문성이 적합한 이유를 설명하세요. {_style_ko}")
            r23 = await asyncio.gather(_call(cso_p, p2), _call(sel_p, p3), return_exceptions=True)
            t2 = r23[0] if isinstance(r23[0], str) and r23[0] else (
                f"{sel_name}, what approach would you take?" if _en else f"{sel_name}님, 어떤 접근법을 취하실 건가요?")
            t3 = r23[1] if isinstance(r23[1], str) and r23[1] else (
                f"This falls right in my area — I can help specifically." if _en
                else f"이 질문은 제 분야에 해당하며, 구체적으로 도와드릴 수 있습니다.")
            turns.append({"speaker": _cso, "role": "CSO", "text": t2, "is_final": False})
            turns.append({"speaker": sel_name, "role": sel_spec, "text": t3, "is_final": False})

            p4 = (f"You are CSO Seoyeon. {sel_name} explained their approach. Ask a follow-up about any specific concerns. {_short_en}"
                  if _en else
                  f"당신은 CSO 서연. {sel_name}님이 접근법을 설명했습니다. 구체적 우려 사항에 대해 추가 질문하세요. {_short_ko}")
            p5 = (f"{_base}{_q}CSO asked a follow-up.\n\nYou are {sel_name} ({sel_spec}). "
                  f"Address the concern with your specific plan. {_style_en}"
                  if _en else
                  f"{_base}{_q}CSO가 추가 질문을 했습니다.\n\n당신은 {sel_name}({sel_spec}). "
                  f"구체적 계획으로 답변하세요. {_style_ko}")
            r45 = await asyncio.gather(_call(cso_p, p4), _call(sel_p, p5), return_exceptions=True)
            t4 = r45[0] if isinstance(r45[0], str) and r45[0] else (
                f"That sounds good. Any specific concerns to address?" if _en else f"좋습니다. 특별히 주의할 점이 있을까요?")
            t5 = r45[1] if isinstance(r45[1], str) and r45[1] else (
                f"I'll handle each point carefully." if _en else f"각 사안을 꼼꼼히 검토하겠습니다.")
            turns.append({"speaker": _cso, "role": "CSO", "text": t4, "is_final": False})
            turns.append({"speaker": sel_name, "role": sel_spec, "text": t5, "is_final": False})

            p6 = (f"{sel_name} explained their approach thoroughly.\n\nYou are CSO Seoyeon. "
                  f"Officially designate {sel_name} as the assigned leader. Reassure the user. {_style_en}"
                  if _en else
                  f"{sel_name}님이 접근법을 충분히 설명했습니다.\n\n당신은 CSO 서연. "
                  f"{sel_name}님을 담당 리더로 공식 지명하세요. 사용자에게 안심 메시지도. {_style_ko}")
            p7 = (f"You've been designated as leader.\n{_q}\nYou are {sel_name} ({sel_spec}). "
                  f"Greet the user warmly and briefly explain how you'll help. {_style_en}"
                  if _en else
                  f"당신이 담당 리더로 지명되었습니다.\n{_q}\n당신은 {sel_name}({sel_spec}). "
                  f"사용자에게 따뜻하게 인사하고 어떻게 도와드릴지 간략히 말씀하세요. {_short_ko}")
            r67 = await asyncio.gather(_call(cso_p, p6), _call(sel_p, p7), return_exceptions=True)
            t6 = r67[0] if isinstance(r67[0], str) and r67[0] else (
                f"{sel_name} will be your assigned leader." if _en else f"{sel_name}님이 담당하시겠습니다.")
            t7 = r67[1] if isinstance(r67[1], str) and r67[1] else (
                f"Hello, I'll take care of this for you right away." if _en else f"안녕하세요, 바로 도와드리겠습니다.")
            turns.append({"speaker": _cso, "role": "CSO", "text": t6, "is_final": False})
            turns.append({"speaker": sel_name, "role": sel_spec, "text": t7, "is_final": True})

        logger.info(f"[Deliberation] {len(turns)}턴 생성 완료")
        return turns

    except asyncio.TimeoutError:
        logger.warning("[Deliberation] 타임아웃 — 스킵")
        return None
    except Exception as e:
        logger.warning(f"[Deliberation] 생성 실패: {type(e).__name__}: {e}")
        return None


async def generate_handoff(
    gc,
    query: str,
    current_leader: Dict,
    new_leader: Dict,
    lang: str = "",
) -> Optional[List[Dict]]:
    """
    리더 간 인수인계 대화 — 9턴 (CSO 주재, 협의 전 과정, 10턴 이내).

    Turn 1: CSO → 주제 변경 감지 + 두 리더 소개
    Turn 2: 현재 리더 → 인계 이유
    Turn 3: CSO → 새 리더에게 의견 요청
    Turn 4: 새 리더 → 자기 관점
    Turn 5: 현재 리더 → 조언/당부
    Turn 6: 새 리더 → 감사 + 구체적 접근법
    Turn 7: 현재 리더 → 동의/양보
    Turn 8: CSO → 새 리더 공식 지명
    Turn 9: 새 리더 → 인사 (is_final)
    """
    if not gc or not current_leader or not new_leader:
        return None

    cur_name = current_leader.get("name", "?")
    cur_specialty = current_leader.get("specialty", "")
    cur_id = current_leader.get("leader_id", "") or _name_to_id(cur_name)

    new_name = new_leader.get("name", "?")
    new_specialty = new_leader.get("specialty", "")
    new_id = new_leader.get("leader_id", "") or _name_to_id(new_name)

    cur_persona = _build_leader_persona(cur_id) if cur_id else ""
    if not cur_persona:
        cur_persona = f"{cur_name}: {cur_specialty} 전문 리더"
    new_persona = _build_leader_persona(new_id) if new_id else ""
    if not new_persona:
        new_persona = f"{new_name}: {new_specialty} 전문 리더"
    cso_p = _build_cso_persona()

    turns: List[Dict] = []
    _en = lang == "en"
    _cso = "Seoyeon" if _en else "서연"
    _base = "[External client question.]\n" if _en else "[외부 의뢰인 질문입니다.]\n"
    _q = f"Question: {query[:300]}\n" if _en else f"질문: {query[:300]}\n"
    _style_en = "2-3 sentences. English only. Use 'leader'/'expert', never 'lawyer'."
    _style_ko = "100~150자. 존댓말, 따뜻하고 전문적 톤. '변호사' 금지, '리더'/'전문가' 사용. 완전한 문장."
    _short_en = "1-2 sentences. English only. Use 'leader'/'expert', never 'lawyer'."
    _short_ko = "80~120자. 존댓말. '변호사' 금지, '리더'/'전문가' 사용. 완전한 문장."

    async def _call(persona, prompt):
        try:
            return await asyncio.wait_for(_single_leader_call(gc, persona, prompt), timeout=_TURN_TIMEOUT)
        except Exception:
            return ""

    try:
        # ── T1: CSO — 주제 변경 감지 + 두 리더 소개 ──
        p1 = (f"{_base}{_q}Current leader: {cur_name}({cur_specialty}), New candidate: {new_name}({new_specialty})\n\n"
              f"You are CSO Seoyeon. The topic has shifted. Explain the change, introduce both leaders, "
              f"and ask {cur_name} to share their thoughts on handoff. {_style_en}"
              if _en else
              f"{_base}{_q}현재 리더: {cur_name}({cur_specialty}), 새 후보: {new_name}({new_specialty})\n\n"
              f"당신은 CSO 서연. 질문 주제가 바뀌었음을 설명하고, 두 리더를 소개한 뒤 "
              f"{cur_name}님에게 인계 의견을 요청하세요. {_style_ko}")
        t1 = await _call(cso_p, p1) or (
            f"The topic has changed. {cur_name}, what do you think about handing this to {new_name}?"
            if _en else f"질문 주제가 바뀌었습니다. {cur_name}님, {new_name}님에게 인계하는 것에 대해 어떻게 생각하시나요?")
        turns.append({"speaker": _cso, "role": "CSO", "text": t1, "is_final": False})

        # ── T2: 현재 리더 — 인계 이유 ──
        p2 = (f"{_base}{_q}CSO asked about handoff to {new_name}({new_specialty}).\n\nYou are {cur_name} ({cur_specialty} expert). "
              f"Explain why this question is closer to {new_specialty} and why {new_name} is better suited. "
              f"Be gracious about the handoff. {_style_en}"
              if _en else
              f"{_base}{_q}CSO가 {new_name}({new_specialty})님에게 인계에 대해 물었습니다.\n\n당신은 {cur_name}({cur_specialty} 전문). "
              f"왜 이 질문이 {new_specialty} 분야에 더 가까운지, {new_name}님이 더 적합한 이유를 설명하세요. {_style_ko}")
        t2 = await _call(cur_persona, p2) or (
            f"This question is better suited for {new_specialty}. {new_name} can help more effectively."
            if _en else f"이 질문은 {new_specialty} 분야에 더 가깝습니다. {new_name}님이 더 잘 도와드릴 수 있습니다.")
        turns.append({"speaker": cur_name, "role": cur_specialty, "text": t2, "is_final": False})

        # ── T3+T4: 병렬 — CSO→새 리더 요청 + 새 리더 관점 ──
        p3 = (f"{cur_name} explained the handoff reason. You are CSO Seoyeon. Now ask {new_name} for their perspective. {_short_en}"
              if _en else
              f"{cur_name}님이 인계 이유를 설명했습니다. 당신은 CSO 서연. 이제 {new_name}님에게도 의견을 요청하세요. {_short_ko}")
        p4 = (f"{_base}{_q}{cur_name}({cur_specialty}) is handing off to you.\n\nYou are {new_name} ({new_specialty} expert). "
              f"Share how this question fits your specialty and how you can specifically help. {_style_en}"
              if _en else
              f"{_base}{_q}{cur_name}({cur_specialty})님이 인계를 제안했습니다.\n\n당신은 {new_name}({new_specialty} 전문). "
              f"이 질문이 자기 분야에 어떻게 해당하는지, 구체적으로 어떻게 도울 수 있는지 설명하세요. {_style_ko}")
        r34 = await asyncio.gather(_call(cso_p, p3), _call(new_persona, p4), return_exceptions=True)
        t3 = r34[0] if isinstance(r34[0], str) and r34[0] else (
            f"{new_name}, could you share your perspective?" if _en else f"{new_name}님도 의견 부탁드립니다.")
        t4 = r34[1] if isinstance(r34[1], str) and r34[1] else (
            f"This falls right in my area of {new_specialty} — I can help specifically."
            if _en else f"이 질문은 제 {new_specialty} 분야에 해당하며, 구체적으로 도와드릴 수 있습니다.")
        turns.append({"speaker": _cso, "role": "CSO", "text": t3, "is_final": False})
        turns.append({"speaker": new_name, "role": new_specialty, "text": t4, "is_final": False})

        # ── T5+T6: 병렬 — 현재 리더 조언 + 새 리더 감사/접근법 ──
        p5 = (f"You are {cur_name} ({cur_specialty}). {new_name} will take over. "
              f"Share any advice or important context for {new_name} to consider. {_short_en}"
              if _en else
              f"당신은 {cur_name}({cur_specialty}). {new_name}님이 인수합니다. "
              f"{new_name}님이 참고할 조언이나 중요 맥락을 전달하세요. {_short_ko}")
        p6 = (f"You are {new_name} ({new_specialty}). {cur_name} shared advice. "
              f"Thank them and explain your specific approach plan. {_style_en}"
              if _en else
              f"당신은 {new_name}({new_specialty}). {cur_name}님이 조언을 해주었습니다. "
              f"감사를 표하고 구체적 접근 계획을 설명하세요. {_style_ko}")
        r56 = await asyncio.gather(_call(cur_persona, p5), _call(new_persona, p6), return_exceptions=True)
        t5 = r56[0] if isinstance(r56[0], str) and r56[0] else (
            f"Please keep in mind the key details of this case." if _en
            else f"이 사안의 핵심 사항을 잘 참고해 주세요.")
        t6 = r56[1] if isinstance(r56[1], str) and r56[1] else (
            f"Thank you for the context. I'll handle this carefully." if _en
            else f"조언 감사합니다. 꼼꼼히 검토하겠습니다.")
        turns.append({"speaker": cur_name, "role": cur_specialty, "text": t5, "is_final": False})
        turns.append({"speaker": new_name, "role": new_specialty, "text": t6, "is_final": False})

        # ── T7+T8+T9: 병렬 — 동의 + CSO 지명 + 인사 ──
        p7 = (f"You are {cur_name} ({cur_specialty}). {new_name} has a solid plan. "
              f"Express full confidence and officially agree to the handoff. {_short_en}"
              if _en else
              f"당신은 {cur_name}({cur_specialty}). {new_name}님이 충실한 계획을 세웠습니다. "
              f"전적으로 신뢰하며 인계에 동의하세요. {_short_ko}")
        p8 = (f"{cur_name} agreed to hand off. Both leaders discussed thoroughly.\n\nYou are CSO Seoyeon. "
              f"Officially designate {new_name} as the new assigned leader. Reassure the user. {_style_en}"
              if _en else
              f"{cur_name}님이 인계에 동의했습니다. 두 리더가 충분히 논의했습니다.\n\n당신은 CSO 서연. "
              f"{new_name}님을 새 담당 리더로 공식 지명하세요. 사용자에게 안심 메시지도. {_style_ko}")
        p9 = (f"You've been designated as the new leader.\n{_q}\nYou are {new_name} ({new_specialty}). "
              f"Greet the user warmly and briefly explain how you'll help. {_style_en}"
              if _en else
              f"당신이 새 담당 리더로 지명되었습니다.\n{_q}\n당신은 {new_name}({new_specialty}). "
              f"사용자에게 따뜻하게 인사하고 어떻게 도와드릴지 간략히 말씀하세요. {_short_ko}")
        r789 = await asyncio.gather(_call(cur_persona, p7), _call(cso_p, p8), _call(new_persona, p9), return_exceptions=True)
        t7 = r789[0] if isinstance(r789[0], str) and r789[0] else (
            f"I fully trust {new_name} with this." if _en else f"{new_name}님을 전적으로 신뢰합니다.")
        t8 = r789[1] if isinstance(r789[1], str) and r789[1] else (
            f"{new_name} will be your new assigned leader." if _en else f"{new_name}님이 새로 담당하시겠습니다.")
        t9 = r789[2] if isinstance(r789[2], str) and r789[2] else (
            f"Hello, I'll take care of this for you right away." if _en else f"안녕하세요, 바로 도와드리겠습니다.")
        turns.append({"speaker": cur_name, "role": cur_specialty, "text": t7, "is_final": False})
        turns.append({"speaker": _cso, "role": "CSO", "text": t8, "is_final": False})
        turns.append({"speaker": new_name, "role": new_specialty, "text": t9, "is_final": True})

        logger.info(f"[Handoff] {cur_name} → {new_name} ({len(turns)}턴)")
        return turns

    except asyncio.TimeoutError:
        logger.warning("[Handoff] 타임아웃 — 스킵")
        return None
    except Exception as e:
        logger.warning(f"[Handoff] 생성 실패: {type(e).__name__}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════
# Streaming (async generator) 버전 — /ask-stream 전용
# 턴별 즉시 yield → SSE 전송 → 실시간 채팅 UX
# ═══════════════════════════════════════════════════════════════════



async def generate_deliberation_stream(
    gc,
    query: str,
    leaders: List[Dict],
    lang: str = "",
) -> AsyncGenerator[Dict, None]:
    """
    CSO 서연 주재 리더 회의 — 최대 9턴 순차 yield (10턴 이내, 협의 전 과정).

    후보 있을 때 (9턴):
    T1: CSO → 질문 요약 + 후보 소개 + B에게 의견 요청
    T2: 후보 B → 자기 분야 관점 의견
    T3: CSO → A에게도 의견 요청
    T4: 담당 A → 본인 적합 이유
    T5: 후보 B → A에게 보충 질문/의견
    T6: 담당 A → 답변 + 구체적 접근법
    T7: 후보 B → 동의/양보
    T8: CSO → 담당 리더 공식 지명
    T9: 담당 A → 인사 (is_final)

    후보 없을 때 (7턴): CSO + 리더 대화
    """
    if not gc or not leaders:
        logger.warning("[Deliberation:Stream] gc 또는 leaders 없음 — 스킵")
        return

    selected = leaders[0]
    sel_name = selected.get("name", "?")
    sel_spec = selected.get("specialty", "")
    sel_id = selected.get("leader_id", "") or _name_to_id(sel_name)

    has_alt = len(leaders) >= 2
    if has_alt:
        alt = leaders[1]
        alt_name = alt.get("name", "?")
        alt_spec = alt.get("specialty", "")
        alt_id = alt.get("leader_id", "") or _name_to_id(alt_name)
    else:
        alt_name = alt_spec = alt_id = ""

    logger.info(f"[Deliberation:Stream] 시작 — leader={sel_name}({sel_id}), alt={alt_name}")

    try:
        cso_p = _build_cso_persona()
        sel_p = _build_leader_persona(sel_id) if sel_id else ""
        if not sel_p:
            sel_p = f"{sel_name}: {sel_spec} 전문 리더"
        alt_p = ""
        if has_alt:
            alt_p = _build_leader_persona(alt_id) if alt_id else ""
            if not alt_p:
                alt_p = f"{alt_name}: {alt_spec} 전문 리더"
    except Exception as e:
        logger.error(f"[Deliberation:Stream] 페르소나 빌드 실패: {type(e).__name__}: {e}")
        return

    _en = lang == "en"
    _cso = "Seoyeon" if _en else "서연"
    _base = "[External client question.]\n" if _en else "[외부 의뢰인 질문입니다.]\n"
    _q = f"Question: {query[:300]}\n" if _en else f"질문: {query[:300]}\n"
    _style_en = "2-3 sentences. English only. Use 'leader'/'expert', never 'lawyer'."
    _style_ko = "100~150자. 존댓말, 따뜻하고 전문적 톤. '변호사' 금지, '리더'/'전문가' 사용. 완전한 문장."
    _short_en = "1-2 sentences. English only. Use 'leader'/'expert', never 'lawyer'."
    _short_ko = "80~120자. 존댓말. '변호사' 금지, '리더'/'전문가' 사용. 완전한 문장."

    async def _call(persona, prompt):
        try:
            return await asyncio.wait_for(_single_leader_call(gc, persona, prompt), timeout=_TURN_TIMEOUT)
        except asyncio.CancelledError:
            raise
        except Exception:
            return ""

    # ── T1: CSO — 질문 요약 + 후보 소개 ──
    if has_alt:
        p1 = (f"{_base}{_q}Candidates: {sel_name}({sel_spec}), {alt_name}({alt_spec})\n\n"
              f"You are CSO Seoyeon. Summarize the question, introduce both candidates, ask {alt_name} for their view first. {_style_en}"
              if _en else
              f"{_base}{_q}후보: {sel_name}({sel_spec}), {alt_name}({alt_spec})\n\n"
              f"당신은 CSO 서연. 질문 핵심을 요약하고, 두 후보를 소개한 뒤 {alt_name}님에게 먼저 의견을 요청하세요. {_style_ko}")
    else:
        p1 = (f"{_base}{_q}Designated leader: {sel_name}({sel_spec})\n\n"
              f"You are CSO Seoyeon. Summarize the question, explain why {sel_spec} expertise is needed, ask {sel_name} for input. {_style_en}"
              if _en else
              f"{_base}{_q}지정 리더: {sel_name}({sel_spec})\n\n"
              f"당신은 CSO 서연. 질문 핵심을 요약하고, {sel_spec} 전문가가 필요한 이유를 설명한 뒤 {sel_name}님에게 의견 요청. {_style_ko}")
    t1 = await _call(cso_p, p1) or (
        f"This question involves {sel_spec}. {alt_name if has_alt else sel_name}, please share your view."
        if _en else f"이 질문은 {sel_spec} 분야입니다. {alt_name if has_alt else sel_name}님, 의견 부탁드립니다.")
    yield {"speaker": _cso, "role": "CSO", "text": t1, "is_final": False}

    if has_alt:
        # ── T2: 후보 B 의견 ──
        p2 = (f"{_base}{_q}CSO asked for your perspective.\n\nYou are {alt_name} ({alt_spec} expert). "
              f"Share your view on this question from your specialty. {_style_en}"
              if _en else
              f"{_base}{_q}CSO 서연이 의견을 요청했습니다.\n\n당신은 {alt_name}({alt_spec} 전문). "
              f"자기 분야 관점에서 이 질문에 대한 의견을 말씀하세요. {_style_ko}")
        t2 = await _call(alt_p, p2) or (
            f"From {alt_spec} perspective, this is an important question." if _en
            else f"{alt_spec} 관점에서 중요한 질문입니다.")
        yield {"speaker": alt_name, "role": alt_spec, "text": t2, "is_final": False}

        # ── T3: CSO → A에게 의견 요청 ──
        p3 = (f"{alt_name} shared their view. You are CSO Seoyeon. Now ask {sel_name} for their perspective too. {_short_en}"
              if _en else
              f"{alt_name}님이 의견을 말했습니다. 당신은 CSO 서연. 이제 {sel_name}님에게도 의견을 요청하세요. {_short_ko}")
        t3 = await _call(cso_p, p3) or (
            f"{sel_name}, could you share your perspective?" if _en else f"{sel_name}님도 의견 부탁드립니다.")
        yield {"speaker": _cso, "role": "CSO", "text": t3, "is_final": False}

        # ── T4: 담당 A 의견 ──
        p4 = (f"{_base}{_q}{alt_name}({alt_spec}) shared their view. CSO asked you too.\n\nYou are {sel_name} ({sel_spec} expert). "
              f"Explain why this question falls in your area and how you can specifically help. {_style_en}"
              if _en else
              f"{_base}{_q}{alt_name}({alt_spec})님이 의견을 말했습니다. CSO가 당신에게도 의견을 요청합니다.\n\n당신은 {sel_name}({sel_spec} 전문). "
              f"왜 이 질문이 자기 분야에 해당하는지, 어떻게 구체적으로 도울 수 있는지 설명하세요. {_style_ko}")
        t4 = await _call(sel_p, p4) or (
            f"This falls right in my area — I can help specifically." if _en
            else f"이 질문은 제 분야에 해당하며, 구체적으로 도와드릴 수 있습니다.")
        yield {"speaker": sel_name, "role": sel_spec, "text": t4, "is_final": False}

        # ── T5: 후보 B 보충 질문 ──
        p5 = (f"You are {alt_name} ({alt_spec}). {sel_name} explained their view. "
              f"Ask a follow-up question or share additional insight from {alt_spec} that may help. {_short_en}"
              if _en else
              f"당신은 {alt_name}({alt_spec}). {sel_name}님이 의견을 설명했습니다. "
              f"{alt_spec} 관점에서 보충 질문이나 추가 의견을 말씀하세요. {_short_ko}")
        t5 = await _call(alt_p, p5) or (
            f"That's a solid approach. How would you handle the specific details?" if _en
            else f"좋은 접근이네요. 구체적인 세부 사항은 어떻게 처리하실 건가요?")
        yield {"speaker": alt_name, "role": alt_spec, "text": t5, "is_final": False}

        # ── T6: 담당 A 답변 + 접근법 ──
        p6 = (f"{_base}{_q}You are {sel_name} ({sel_spec}). {alt_name} asked a follow-up. "
              f"Respond with your specific approach and concrete plan. {_style_en}"
              if _en else
              f"{_base}{_q}당신은 {sel_name}({sel_spec}). {alt_name}님이 보충 질문을 했습니다. "
              f"구체적인 접근법과 계획으로 답변하세요. {_style_ko}")
        t6 = await _call(sel_p, p6) or (
            f"I'll address each point systematically." if _en
            else f"각 사안을 체계적으로 검토하겠습니다.")
        yield {"speaker": sel_name, "role": sel_spec, "text": t6, "is_final": False}

        # ── T7: 후보 B 동의/양보 ──
        p7 = (f"You are {alt_name} ({alt_spec}). {sel_name} gave a thorough response. "
              f"Agree that {sel_name} is the right leader and express confidence. {_short_en}"
              if _en else
              f"당신은 {alt_name}({alt_spec}). {sel_name}님이 충실히 답변했습니다. "
              f"{sel_name}님이 적임자라는 데 동의하고 신뢰를 표현하세요. {_short_ko}")
        t7 = await _call(alt_p, p7) or (
            f"I agree — {sel_name} is the perfect fit." if _en
            else f"저도 동의합니다. {sel_name}님이 적임자입니다.")
        yield {"speaker": alt_name, "role": alt_spec, "text": t7, "is_final": False}

        # ── T8: CSO 공식 지명 ──
        p8 = (f"Both leaders discussed thoroughly. {alt_name} agreed {sel_name} is best.\n\n"
              f"You are CSO Seoyeon. Officially designate {sel_name} as the assigned leader. Reassure the user. {_style_en}"
              if _en else
              f"두 리더가 충분히 논의했고, {alt_name}님이 {sel_name}님에게 양보했습니다.\n\n"
              f"당신은 CSO 서연. {sel_name}님을 담당 리더로 공식 지명하세요. 사용자에게 안심 메시지도. {_style_ko}")
        t8 = await _call(cso_p, p8) or (
            f"{sel_name} will be your assigned leader." if _en else f"{sel_name}님이 담당하시겠습니다.")
        yield {"speaker": _cso, "role": "CSO", "text": t8, "is_final": False}

        # ── T9: 담당 A 인사 (is_final) ──
        p9 = (f"You've been designated as leader.\n{_q}\nYou are {sel_name} ({sel_spec}). "
              f"Greet the user warmly and briefly explain how you'll help. {_style_en}"
              if _en else
              f"당신이 담당 리더로 지명되었습니다.\n{_q}\n당신은 {sel_name}({sel_spec}). "
              f"사용자에게 따뜻하게 인사하고 어떻게 도와드릴지 간략히 말씀하세요. {_short_ko}")
        t9 = await _call(sel_p, p9) or (
            f"Hello, I'll take care of this for you right away." if _en
            else f"안녕하세요, 바로 도와드리겠습니다.")
        yield {"speaker": sel_name, "role": sel_spec, "text": t9, "is_final": True}
        logger.info("[Deliberation:Stream] 9턴 스트리밍 완료")

    else:
        # 후보 없음 — CSO + 리더 대화 (7턴)
        # T2: CSO 추가 질문
        p2 = (f"{_base}{_q}You are CSO Seoyeon. Ask {sel_name} what specific approach they'd take. {_short_en}"
              if _en else
              f"{_base}{_q}당신은 CSO 서연. {sel_name}님에게 어떤 접근법을 취할 것인지 구체적으로 물어보세요. {_short_ko}")
        t2 = await _call(cso_p, p2) or (
            f"{sel_name}, what approach would you take?" if _en else f"{sel_name}님, 어떤 접근법을 취하실 건가요?")
        yield {"speaker": _cso, "role": "CSO", "text": t2, "is_final": False}

        # T3: 리더 접근법
        p3 = (f"{_base}{_q}CSO asked about your approach.\n\nYou are {sel_name} ({sel_spec} expert). "
              f"Explain your specific approach and why your expertise fits. {_style_en}"
              if _en else
              f"{_base}{_q}CSO가 접근법을 물었습니다.\n\n당신은 {sel_name}({sel_spec} 전문). "
              f"구체적 접근법과 자기 전문성이 적합한 이유를 설명하세요. {_style_ko}")
        t3 = await _call(sel_p, p3) or (
            f"This falls right in my area — I can help specifically." if _en
            else f"이 질문은 제 분야에 해당하며, 구체적으로 도와드릴 수 있습니다.")
        yield {"speaker": sel_name, "role": sel_spec, "text": t3, "is_final": False}

        # T4: CSO 추가 질문
        p4 = (f"You are CSO Seoyeon. {sel_name} explained their approach. Ask a follow-up about any specific concerns. {_short_en}"
              if _en else
              f"당신은 CSO 서연. {sel_name}님이 접근법을 설명했습니다. 구체적 우려 사항에 대해 추가 질문하세요. {_short_ko}")
        t4 = await _call(cso_p, p4) or (
            f"That sounds good. Any specific concerns to address?" if _en else f"좋습니다. 특별히 주의할 점이 있을까요?")
        yield {"speaker": _cso, "role": "CSO", "text": t4, "is_final": False}

        # T5: 리더 답변
        p5 = (f"{_base}{_q}CSO asked a follow-up.\n\nYou are {sel_name} ({sel_spec}). "
              f"Address the concern with your specific plan. {_style_en}"
              if _en else
              f"{_base}{_q}CSO가 추가 질문을 했습니다.\n\n당신은 {sel_name}({sel_spec}). "
              f"구체적 계획으로 답변하세요. {_style_ko}")
        t5 = await _call(sel_p, p5) or (
            f"I'll handle each point carefully." if _en else f"각 사안을 꼼꼼히 검토하겠습니다.")
        yield {"speaker": sel_name, "role": sel_spec, "text": t5, "is_final": False}

        # T6: CSO 지명
        p6 = (f"{sel_name} explained their approach thoroughly.\n\nYou are CSO Seoyeon. "
              f"Officially designate {sel_name} as the assigned leader. Reassure the user. {_style_en}"
              if _en else
              f"{sel_name}님이 접근법을 충분히 설명했습니다.\n\n당신은 CSO 서연. "
              f"{sel_name}님을 담당 리더로 공식 지명하세요. 사용자에게 안심 메시지도. {_style_ko}")
        t6 = await _call(cso_p, p6) or (
            f"{sel_name} will be your assigned leader." if _en else f"{sel_name}님이 담당하시겠습니다.")
        yield {"speaker": _cso, "role": "CSO", "text": t6, "is_final": False}

        # T7: 리더 인사
        p7 = (f"You've been designated as leader.\n{_q}\nYou are {sel_name} ({sel_spec}). "
              f"Greet the user warmly and briefly explain how you'll help. {_style_en}"
              if _en else
              f"당신이 담당 리더로 지명되었습니다.\n{_q}\n당신은 {sel_name}({sel_spec}). "
              f"사용자에게 따뜻하게 인사하고 어떻게 도와드릴지 간략히 말씀하세요. {_short_ko}")
        t7 = await _call(sel_p, p7) or (
            f"Hello, I'll take care of this for you right away." if _en
            else f"안녕하세요, 바로 도와드리겠습니다.")
        yield {"speaker": sel_name, "role": sel_spec, "text": t7, "is_final": True}
        logger.info("[Deliberation:Stream] 7턴 스트리밍 완료")


async def generate_handoff_stream(
    gc,
    query: str,
    current_leader: Dict,
    new_leader: Dict,
    lang: str = "",
) -> AsyncGenerator[Dict, None]:
    """
    리더 간 인수인계 대화 — 9턴 순차 yield (CSO 주재, 협의 전 과정, 10턴 이내).

    T1: CSO → 주제 변경 감지 + 두 리더 소개
    T2: 현재 리더 → 인계 이유
    T3: CSO → 새 리더에게 의견 요청
    T4: 새 리더 → 자기 관점
    T5: 현재 리더 → 조언/당부
    T6: 새 리더 → 감사 + 구체적 접근법
    T7: 현재 리더 → 동의/양보
    T8: CSO → 새 리더 공식 지명
    T9: 새 리더 → 인사 (is_final)
    """
    if not gc or not current_leader or not new_leader:
        logger.warning("[Handoff:Stream] gc/leaders 없음 — 스킵")
        return

    cur_name = current_leader.get("name", "?")
    cur_specialty = current_leader.get("specialty", "")
    cur_id = current_leader.get("leader_id", "") or _name_to_id(cur_name)

    new_name = new_leader.get("name", "?")
    new_specialty = new_leader.get("specialty", "")
    new_id = new_leader.get("leader_id", "") or _name_to_id(new_name)

    logger.info(f"[Handoff:Stream] 시작 — {cur_name} → {new_name}")

    cur_persona = _build_leader_persona(cur_id) if cur_id else ""
    if not cur_persona:
        cur_persona = f"{cur_name}: {cur_specialty} 전문 리더"
    new_persona = _build_leader_persona(new_id) if new_id else ""
    if not new_persona:
        new_persona = f"{new_name}: {new_specialty} 전문 리더"
    cso_p = _build_cso_persona()

    _en = lang == "en"
    _cso = "Seoyeon" if _en else "서연"
    _base = "[External client question.]\n" if _en else "[외부 의뢰인 질문입니다.]\n"
    _q = f"Question: {query[:300]}\n" if _en else f"질문: {query[:300]}\n"
    _style_en = "2-3 sentences. English only. Use 'leader'/'expert', never 'lawyer'."
    _style_ko = "100~150자. 존댓말, 따뜻하고 전문적 톤. '변호사' 금지, '리더'/'전문가' 사용. 완전한 문장."
    _short_en = "1-2 sentences. English only. Use 'leader'/'expert', never 'lawyer'."
    _short_ko = "80~120자. 존댓말. '변호사' 금지, '리더'/'전문가' 사용. 완전한 문장."

    async def _call(persona, prompt):
        try:
            return await asyncio.wait_for(_single_leader_call(gc, persona, prompt), timeout=_TURN_TIMEOUT)
        except asyncio.CancelledError:
            raise
        except Exception:
            return ""

    # ── T1: CSO — 주제 변경 감지 + 두 리더 소개 ──
    p1 = (f"{_base}{_q}Current leader: {cur_name}({cur_specialty}), New candidate: {new_name}({new_specialty})\n\n"
          f"You are CSO Seoyeon. The topic has shifted. Explain the change, introduce both leaders, "
          f"and ask {cur_name} to share their thoughts on handoff. {_style_en}"
          if _en else
          f"{_base}{_q}현재 리더: {cur_name}({cur_specialty}), 새 후보: {new_name}({new_specialty})\n\n"
          f"당신은 CSO 서연. 질문 주제가 바뀌었음을 설명하고, 두 리더를 소개한 뒤 "
          f"{cur_name}님에게 인계 의견을 요청하세요. {_style_ko}")
    t1 = await _call(cso_p, p1) or (
        f"The topic has changed. {cur_name}, what do you think about handing this to {new_name}?"
        if _en else f"질문 주제가 바뀌었습니다. {cur_name}님, {new_name}님에게 인계하는 것에 대해 어떻게 생각하시나요?")
    yield {"speaker": _cso, "role": "CSO", "text": t1, "is_final": False}

    # ── T2: 현재 리더 — 인계 이유 ──
    p2 = (f"{_base}{_q}CSO asked about handoff to {new_name}({new_specialty}).\n\nYou are {cur_name} ({cur_specialty} expert). "
          f"Explain why this question is closer to {new_specialty} and why {new_name} is better suited. {_style_en}"
          if _en else
          f"{_base}{_q}CSO가 {new_name}({new_specialty})님에게 인계에 대해 물었습니다.\n\n당신은 {cur_name}({cur_specialty} 전문). "
          f"왜 이 질문이 {new_specialty} 분야에 더 가까운지, {new_name}님이 더 적합한 이유를 설명하세요. {_style_ko}")
    t2 = await _call(cur_persona, p2) or (
        f"This question is better suited for {new_specialty}. {new_name} can help more effectively."
        if _en else f"이 질문은 {new_specialty} 분야에 더 가깝습니다. {new_name}님이 더 잘 도와드릴 수 있습니다.")
    yield {"speaker": cur_name, "role": cur_specialty, "text": t2, "is_final": False}

    # ── T3: CSO → 새 리더에게 의견 요청 ──
    p3 = (f"{cur_name} explained the handoff reason. You are CSO Seoyeon. Now ask {new_name} for their perspective. {_short_en}"
          if _en else
          f"{cur_name}님이 인계 이유를 설명했습니다. 당신은 CSO 서연. 이제 {new_name}님에게도 의견을 요청하세요. {_short_ko}")
    t3 = await _call(cso_p, p3) or (
        f"{new_name}, could you share your perspective?" if _en else f"{new_name}님도 의견 부탁드립니다.")
    yield {"speaker": _cso, "role": "CSO", "text": t3, "is_final": False}

    # ── T4: 새 리더 — 자기 관점 ──
    p4 = (f"{_base}{_q}{cur_name}({cur_specialty}) is handing off to you.\n\nYou are {new_name} ({new_specialty} expert). "
          f"Share how this question fits your specialty and how you can specifically help. {_style_en}"
          if _en else
          f"{_base}{_q}{cur_name}({cur_specialty})님이 인계를 제안했습니다.\n\n당신은 {new_name}({new_specialty} 전문). "
          f"이 질문이 자기 분야에 어떻게 해당하는지, 구체적으로 어떻게 도울 수 있는지 설명하세요. {_style_ko}")
    t4 = await _call(new_persona, p4) or (
        f"This falls right in my area of {new_specialty} — I can help specifically."
        if _en else f"이 질문은 제 {new_specialty} 분야에 해당하며, 구체적으로 도와드릴 수 있습니다.")
    yield {"speaker": new_name, "role": new_specialty, "text": t4, "is_final": False}

    # ── T5: 현재 리더 — 조언/당부 ──
    p5 = (f"You are {cur_name} ({cur_specialty}). {new_name} will take over. "
          f"Share any advice or important context for {new_name} to consider. {_short_en}"
          if _en else
          f"당신은 {cur_name}({cur_specialty}). {new_name}님이 인수합니다. "
          f"{new_name}님이 참고할 조언이나 중요 맥락을 전달하세요. {_short_ko}")
    t5 = await _call(cur_persona, p5) or (
        f"Please keep in mind the key details of this case." if _en
        else f"이 사안의 핵심 사항을 잘 참고해 주세요.")
    yield {"speaker": cur_name, "role": cur_specialty, "text": t5, "is_final": False}

    # ── T6: 새 리더 — 감사 + 접근법 ──
    p6 = (f"You are {new_name} ({new_specialty}). {cur_name} shared advice. "
          f"Thank them and explain your specific approach plan. {_style_en}"
          if _en else
          f"당신은 {new_name}({new_specialty}). {cur_name}님이 조언을 해주었습니다. "
          f"감사를 표하고 구체적 접근 계획을 설명하세요. {_style_ko}")
    t6 = await _call(new_persona, p6) or (
        f"Thank you for the context. I'll handle this carefully." if _en
        else f"조언 감사합니다. 꼼꼼히 검토하겠습니다.")
    yield {"speaker": new_name, "role": new_specialty, "text": t6, "is_final": False}

    # ── T7: 현재 리더 — 동의/양보 ──
    p7 = (f"You are {cur_name} ({cur_specialty}). {new_name} has a solid plan. "
          f"Express full confidence and officially agree to the handoff. {_short_en}"
          if _en else
          f"당신은 {cur_name}({cur_specialty}). {new_name}님이 충실한 계획을 세웠습니다. "
          f"전적으로 신뢰하며 인계에 동의하세요. {_short_ko}")
    t7 = await _call(cur_persona, p7) or (
        f"I fully trust {new_name} with this." if _en else f"{new_name}님을 전적으로 신뢰합니다.")
    yield {"speaker": cur_name, "role": cur_specialty, "text": t7, "is_final": False}

    # ── T8: CSO — 공식 지명 ──
    p8 = (f"{cur_name} agreed to hand off. Both leaders discussed thoroughly.\n\nYou are CSO Seoyeon. "
          f"Officially designate {new_name} as the new assigned leader. Reassure the user. {_style_en}"
          if _en else
          f"{cur_name}님이 인계에 동의했습니다. 두 리더가 충분히 논의했습니다.\n\n당신은 CSO 서연. "
          f"{new_name}님을 새 담당 리더로 공식 지명하세요. 사용자에게 안심 메시지도. {_style_ko}")
    t8 = await _call(cso_p, p8) or (
        f"{new_name} will be your new assigned leader." if _en else f"{new_name}님이 새로 담당하시겠습니다.")
    yield {"speaker": _cso, "role": "CSO", "text": t8, "is_final": False}

    # ── T9: 새 리더 — 인사 (is_final) ──
    p9 = (f"You've been designated as the new leader.\n{_q}\nYou are {new_name} ({new_specialty}). "
          f"Greet the user warmly and briefly explain how you'll help. {_style_en}"
          if _en else
          f"당신이 새 담당 리더로 지명되었습니다.\n{_q}\n당신은 {new_name}({new_specialty}). "
          f"사용자에게 따뜻하게 인사하고 어떻게 도와드릴지 간략히 말씀하세요. {_short_ko}")
    t9 = await _call(new_persona, p9) or (
        f"Hello, I'll take care of this for you right away." if _en
        else f"안녕하세요, 바로 도와드리겠습니다.")
    yield {"speaker": new_name, "role": new_specialty, "text": t9, "is_final": True}
    logger.info(f"[Handoff:Stream] {cur_name} → {new_name} 9턴 스트리밍 완료")
