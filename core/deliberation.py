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

# 협의 타임아웃 (초) — 파이프라인과 병렬 실행이므로 전체 응답 시간에 영향 없음
_DELIBERATION_TIMEOUT = 30
_HANDOFF_TIMEOUT = 15
_TURN_TIMEOUT = 4  # 개별 턴 타임아웃 (초)

# 이름 → ID 역매핑 캐시
_NAME_TO_ID: Dict[str, str] = {}

# 프롬프트 인젝션 방지: 쿼리 새니타이즈
_INJECTION_MARKERS = re.compile(r'\[(지시|페르소나|INST|SYSTEM)\]|`{1,3}|<\/?system>', re.IGNORECASE)

def _sanitize_query_for_prompt(query: str, lang: str = "") -> str:
    """사용자 쿼리를 Gemini 프롬프트에 안전하게 삽입하기 위한 새니타이즈.

    1) 인젝션 마커 및 모든 백틱 제거
    2) 안전한 triple-backtick 래핑으로 경계 보호
    """
    q = query[:300].strip()
    q = _INJECTION_MARKERS.sub('', q)
    if lang == "en":
        return f"Question: ```{q}```\n"
    return f"질문: ```{q}```\n"


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
        return "CSO 서연: 법률 전략 총괄. 리더 회의를 주재합니다."
    parts = []
    if p.get("hero"):
        parts.append(f"신조: {p['hero']}")
    identity = p.get("identity", {})
    if identity.get("what"):
        parts.append(f"역할: {identity['what']}")
    if p.get("philosophy"):
        parts.append(f"철학: {p['philosophy']}")
    if not parts:
        return "CSO 서연: 법률 전략 총괄."
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
        _supports_thinking = "2.5" in model_name or "3" in model_name
        _cfg_kwargs = dict(
            max_output_tokens=max_tokens,
            temperature=temp,
            safety_settings=safety_settings,
        )
        if _supports_thinking:
            _cfg_kwargs["thinking_config"] = genai_types.ThinkingConfig(thinking_budget=0)
        for _attempt in range(3):
            try:
                return gc.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                    config=genai_types.GenerateContentConfig(**_cfg_kwargs),
                )
            except Exception as e:
                if is_quota_error(e) and _attempt < 2:
                    wait = _RETRY_BASE_SEC * (2 ** _attempt)
                    _time.sleep(wait)
                    continue
                raise

    loop = asyncio.get_running_loop()
    resp = await asyncio.wait_for(
        loop.run_in_executor(None, _sync_call),
        timeout=_TURN_TIMEOUT + 2,  # executor 자체 timeout (SDK 행 방지)
    )

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
    CSO 서연 주재 리더 회의 — 4턴.

    Turn 1: CSO 서연 → 쟁점 도출 + 리더 소개
    Turn 2: 담당 리더 → 쟁점 분석 + 해결 방향
    Turn 3: CSO → 리더 지명
    Turn 4: 담당 리더 → 인사 + 해결 약속 (is_final)
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
    _q = _sanitize_query_for_prompt(query, lang)
    _anti_meta = "Never mention Lawmadi, AI systems, markets, competitiveness, or internal operations. Only discuss the client's legal question."
    _anti_meta_ko = "Lawmadi/AI 시스템/시장/경쟁력/내부 운영 언급 금지. 오직 의뢰인의 법률 질문에 대해서만 발언."
    _style_en = f"2-3 sentences. English only. Use 'leader'/'expert', never 'lawyer'. {_anti_meta}"
    _style_ko = f"100~150자. 존댓말, 따뜻하고 전문적 톤. '변호사' 금지, '리더'/'전문가' 사용. 완전한 문장. {_anti_meta_ko}"
    _short_en = f"1-2 sentences. English only. Use 'leader'/'expert', never 'lawyer'. {_anti_meta}"
    _short_ko = f"80~120자. 존댓말. '변호사' 금지, '리더'/'전문가' 사용. 완전한 문장. {_anti_meta_ko}"

    async def _call(persona, prompt):
        try:
            return await asyncio.wait_for(_single_leader_call(gc, persona, prompt), timeout=_TURN_TIMEOUT)
        except Exception:
            return ""

    try:
        # ── Turn 1: CSO — 의뢰인 질문 쟁점 도출 + 후보 소개 ──
        if has_alt:
            p1 = (f"{_base}{_q}Candidates: {sel_name}({sel_spec}), {alt_name}({alt_spec})\n\n"
                  f"You are CSO Seoyeon chairing a meeting. Identify the key legal issues from the client's question, "
                  f"introduce both candidates, and ask {alt_name} to analyze the issues from their perspective. {_style_en}"
                  if _en else
                  f"{_base}{_q}후보: {sel_name}({sel_spec}), {alt_name}({alt_spec})\n\n"
                  f"당신은 CSO 서연, 회의를 주재합니다. 의뢰인 질문에서 핵심 법적 쟁점을 도출하고, "
                  f"두 후보를 소개한 뒤 {alt_name}님에게 쟁점 분석을 요청하세요. {_style_ko}")
        else:
            p1 = (f"{_base}{_q}Designated leader: {sel_name}({sel_spec})\n\n"
                  f"You are CSO Seoyeon chairing a meeting. Identify the key legal issues from the client's question, "
                  f"explain why {sel_spec} expertise is needed to resolve them, and ask {sel_name} for their analysis. {_style_en}"
                  if _en else
                  f"{_base}{_q}지정 리더: {sel_name}({sel_spec})\n\n"
                  f"당신은 CSO 서연, 회의를 주재합니다. 의뢰인 질문에서 핵심 법적 쟁점을 도출하고, "
                  f"{sel_spec} 전문가가 이 쟁점을 해결하는 데 필요한 이유를 설명한 뒤 {sel_name}님에게 분석을 요청하세요. {_style_ko}")
        if has_alt:
            # ── T1 + T2 병렬: CSO 쟁점 도출 + B 쟁점 분석 (순차→병렬 전환, ~2-4초 절감) ──
            p2 = (f"{_base}{_q}CSO identified key issues and asked you to analyze them.\n\nYou are {alt_name} ({alt_spec} expert). "
                  f"Analyze the legal issues from your specialty and suggest how to resolve them. {_style_en}"
                  if _en else
                  f"{_base}{_q}CSO 서연이 쟁점을 도출하고 분석을 요청했습니다.\n\n당신은 {alt_name}({alt_spec} 전문). "
                  f"자기 분야 관점에서 법적 쟁점을 분석하고 해결 방향을 제시하세요. {_style_ko}")
            r12 = await asyncio.gather(_call(cso_p, p1), _call(alt_p, p2), return_exceptions=True)
            t1 = r12[0] if len(r12) > 0 and isinstance(r12[0], str) and r12[0] else (
                f"Let me identify the key issues. This involves {sel_spec}. {alt_name}, please analyze."
                if _en else f"핵심 쟁점을 정리하겠습니다. {sel_spec} 분야입니다. {alt_name}님, 쟁점 분석 부탁드립니다.")
            t2 = r12[1] if len(r12) > 1 and isinstance(r12[1], str) and r12[1] else (
                f"From {alt_spec} perspective, the key issue here is significant."
                if _en else f"{alt_spec} 관점에서 이 쟁점은 중요한 사안입니다.")
            turns.append({"speaker": _cso, "role": "CSO", "text": t1, "is_final": False})
            turns.append({"speaker": alt_name, "role": alt_spec, "text": t2, "is_final": False})
        else:
            t1 = await _call(cso_p, p1) or (
                f"Let me identify the key issues. This involves {sel_spec}. {sel_name}, please analyze."
                if _en else f"핵심 쟁점을 정리하겠습니다. {sel_spec} 분야입니다. {sel_name}님, 쟁점 분석 부탁드립니다.")
            turns.append({"speaker": _cso, "role": "CSO", "text": t1, "is_final": False})

        if has_alt:

            # ── Group 3: T3 (CSO→A 쟁점 분석 요청) + T4 (A 쟁점 해결 방안) 병렬 ──
            p3 = (f"{alt_name} analyzed the issues. You are CSO Seoyeon. Now ask {sel_name} to share their analysis and resolution approach. {_short_en}"
                  if _en else
                  f"{alt_name}님이 쟁점을 분석했습니다. 당신은 CSO 서연. 이제 {sel_name}님에게 쟁점 분석과 해결 방안을 요청하세요. {_short_ko}")
            p4 = (f"{_base}{_q}{alt_name}({alt_spec}) analyzed the issues. CSO asks you to present your resolution approach.\n\n"
                  f"You are {sel_name} ({sel_spec} expert). "
                  f"Identify the core issues, explain why they fall in your area, and propose specific resolution steps. {_style_en}"
                  if _en else
                  f"{_base}{_q}{alt_name}({alt_spec})님이 쟁점을 분석했습니다. CSO가 해결 방안을 요청합니다.\n\n"
                  f"당신은 {sel_name}({sel_spec} 전문). "
                  f"핵심 쟁점을 짚고, 왜 자기 분야에 해당하는지 설명하고, 구체적 해결 단계를 제시하세요. {_style_ko}")
            r34 = await asyncio.gather(_call(cso_p, p3), _call(sel_p, p4), return_exceptions=True)
            t3 = r34[0] if isinstance(r34[0], str) and r34[0] else (
                f"{sel_name}, please share your analysis and resolution plan." if _en else f"{sel_name}님, 쟁점 분석과 해결 방안을 말씀해 주세요.")
            t4 = r34[1] if isinstance(r34[1], str) and r34[1] else (
                f"The core issue falls in my area — here's my resolution approach." if _en
                else f"핵심 쟁점은 제 분야에 해당하며, 구체적인 해결 방안을 제시하겠습니다.")
            turns.append({"speaker": _cso, "role": "CSO", "text": t3, "is_final": False})
            turns.append({"speaker": sel_name, "role": sel_spec, "text": t4, "is_final": False})

            # ── Group 4: T5 (B 추가 쟁점/보완) + T6 (A 해결 계획 구체화) 병렬 ──
            p5 = (f"You are {alt_name} ({alt_spec}). {sel_name} proposed a resolution. "
                  f"Raise any additional issues or considerations from {alt_spec} perspective that should be addressed. {_short_en}"
                  if _en else
                  f"당신은 {alt_name}({alt_spec}). {sel_name}님이 해결 방안을 제시했습니다. "
                  f"{alt_spec} 관점에서 추가로 고려해야 할 쟁점이나 보완 사항을 말씀하세요. {_short_ko}")
            p6 = (f"{_base}{_q}You are {sel_name} ({sel_spec}). {alt_name} raised additional considerations. "
                  f"Address them with your detailed resolution plan for each issue. {_style_en}"
                  if _en else
                  f"{_base}{_q}당신은 {sel_name}({sel_spec}). {alt_name}님이 추가 쟁점을 제기했습니다. "
                  f"각 쟁점별 구체적인 해결 계획으로 답변하세요. {_style_ko}")
            r56 = await asyncio.gather(_call(alt_p, p5), _call(sel_p, p6), return_exceptions=True)
            t5 = r56[0] if isinstance(r56[0], str) and r56[0] else (
                f"Good approach. There's one more issue to consider." if _en
                else f"좋은 방안입니다. 한 가지 더 고려할 쟁점이 있습니다.")
            t6 = r56[1] if isinstance(r56[1], str) and r56[1] else (
                f"I'll address each issue with a step-by-step plan." if _en
                else f"각 쟁점별로 단계적인 해결 계획을 세우겠습니다.")
            turns.append({"speaker": alt_name, "role": alt_spec, "text": t5, "is_final": False})
            turns.append({"speaker": sel_name, "role": sel_spec, "text": t6, "is_final": False})

            # ── Group 5: T7 (B 해결 방안 동의) + T8 (CSO 쟁점 정리 + 지명) + T9 (A 인사 + 해결 약속) 병렬 ──
            p7 = (f"You are {alt_name} ({alt_spec}). {sel_name} addressed all issues thoroughly. "
                  f"Agree with the resolution plan and express confidence in {sel_name}'s approach. {_short_en}"
                  if _en else
                  f"당신은 {alt_name}({alt_spec}). {sel_name}님이 모든 쟁점에 충실히 답변했습니다. "
                  f"해결 방안에 동의하고 {sel_name}님의 접근법에 신뢰를 표현하세요. {_short_ko}")
            p8 = (f"Both leaders analyzed the issues and agreed on a resolution plan.\n\n"
                  f"You are CSO Seoyeon. Summarize the key issues identified, designate {sel_name} as the assigned leader to resolve them. Reassure the user. {_style_en}"
                  if _en else
                  f"두 리더가 쟁점을 분석하고 해결 방안에 합의했습니다.\n\n"
                  f"당신은 CSO 서연. 도출된 핵심 쟁점을 정리하고, {sel_name}님을 담당 리더로 지명하세요. 사용자에게 안심 메시지도. {_style_ko}")
            p9 = (f"You've been designated to resolve the client's issues.\n{_q}\nYou are {sel_name} ({sel_spec}). "
                  f"Greet the user warmly and commit to resolving the identified issues. {_style_en}"
                  if _en else
                  f"의뢰인의 쟁점을 해결할 담당 리더로 지명되었습니다.\n{_q}\n당신은 {sel_name}({sel_spec}). "
                  f"사용자에게 따뜻하게 인사하고 도출된 쟁점을 해결하겠다고 말씀하세요. {_short_ko}")
            r789 = await asyncio.gather(_call(alt_p, p7), _call(cso_p, p8), _call(sel_p, p9), return_exceptions=True)
            t7 = r789[0] if isinstance(r789[0], str) and r789[0] else (
                f"I agree with the resolution plan — {sel_name} is the right expert." if _en else f"해결 방안에 동의합니다. {sel_name}님이 적임자입니다.")
            t8 = r789[1] if isinstance(r789[1], str) and r789[1] else (
                f"Issues identified. {sel_name} will resolve them for you." if _en else f"쟁점이 정리되었습니다. {sel_name}님이 해결해 드리겠습니다.")
            t9 = r789[2] if isinstance(r789[2], str) and r789[2] else (
                f"Hello, I'll resolve each issue for you right away." if _en else f"안녕하세요, 도출된 쟁점을 하나하나 해결해 드리겠습니다.")
            turns.append({"speaker": alt_name, "role": alt_spec, "text": t7, "is_final": False})
            turns.append({"speaker": _cso, "role": "CSO", "text": t8, "is_final": False})
            turns.append({"speaker": sel_name, "role": sel_spec, "text": t9, "is_final": True})

        else:
            # 후보 없음 — CSO + 리더 A 쟁점 회의 (7턴)
            p2 = (f"{_base}{_q}You are CSO Seoyeon. Ask {sel_name} to identify the key issues and propose resolution steps. {_short_en}"
                  if _en else
                  f"{_base}{_q}당신은 CSO 서연. {sel_name}님에게 핵심 쟁점을 분석하고 해결 단계를 제안해 달라고 요청하세요. {_short_ko}")
            p3 = (f"{_base}{_q}CSO asked you to analyze issues and propose resolution.\n\nYou are {sel_name} ({sel_spec} expert). "
                  f"Identify the core legal issues and explain your resolution approach. {_style_en}"
                  if _en else
                  f"{_base}{_q}CSO가 쟁점 분석과 해결 방안을 요청했습니다.\n\n당신은 {sel_name}({sel_spec} 전문). "
                  f"핵심 법적 쟁점을 짚고, 구체적 해결 접근법을 설명하세요. {_style_ko}")
            r23 = await asyncio.gather(_call(cso_p, p2), _call(sel_p, p3), return_exceptions=True)
            t2 = r23[0] if isinstance(r23[0], str) and r23[0] else (
                f"{sel_name}, please analyze the key issues and propose a resolution." if _en else f"{sel_name}님, 핵심 쟁점을 분석하고 해결 방안을 제시해 주세요.")
            t3 = r23[1] if isinstance(r23[1], str) and r23[1] else (
                f"The core issue falls in my area — here's my resolution plan." if _en
                else f"핵심 쟁점은 제 분야에 해당하며, 해결 방안을 제시하겠습니다.")
            turns.append({"speaker": _cso, "role": "CSO", "text": t2, "is_final": False})
            turns.append({"speaker": sel_name, "role": sel_spec, "text": t3, "is_final": False})

            p4 = (f"You are CSO Seoyeon. {sel_name} identified issues and proposed resolution. Ask about any remaining concerns or risks. {_short_en}"
                  if _en else
                  f"당신은 CSO 서연. {sel_name}님이 쟁점과 해결 방안을 제시했습니다. 추가 우려 사항이나 리스크에 대해 질문하세요. {_short_ko}")
            p5 = (f"{_base}{_q}CSO asked about remaining concerns.\n\nYou are {sel_name} ({sel_spec}). "
                  f"Address remaining risks and present your complete resolution plan. {_style_en}"
                  if _en else
                  f"{_base}{_q}CSO가 추가 우려 사항을 물었습니다.\n\n당신은 {sel_name}({sel_spec}). "
                  f"잔여 리스크를 점검하고 완전한 해결 계획을 제시하세요. {_style_ko}")
            r45 = await asyncio.gather(_call(cso_p, p4), _call(sel_p, p5), return_exceptions=True)
            t4 = r45[0] if isinstance(r45[0], str) and r45[0] else (
                f"Good analysis. Any remaining risks to address?" if _en else f"좋은 분석입니다. 추가로 주의할 리스크가 있을까요?")
            t5 = r45[1] if isinstance(r45[1], str) and r45[1] else (
                f"I've considered all risks and have a complete plan." if _en else f"모든 리스크를 고려했고, 완전한 해결 계획을 세웠습니다.")
            turns.append({"speaker": _cso, "role": "CSO", "text": t4, "is_final": False})
            turns.append({"speaker": sel_name, "role": sel_spec, "text": t5, "is_final": False})

            p6 = (f"{sel_name} presented a thorough resolution plan.\n\nYou are CSO Seoyeon. "
                  f"Summarize the identified issues, designate {sel_name} as the assigned leader. Reassure the user. {_style_en}"
                  if _en else
                  f"{sel_name}님이 충분한 해결 계획을 제시했습니다.\n\n당신은 CSO 서연. "
                  f"도출된 쟁점을 정리하고, {sel_name}님을 담당 리더로 지명하세요. 사용자에게 안심 메시지도. {_style_ko}")
            p7 = (f"You've been designated to resolve the client's issues.\n{_q}\nYou are {sel_name} ({sel_spec}). "
                  f"Greet the user warmly and commit to resolving the identified issues. {_style_en}"
                  if _en else
                  f"의뢰인의 쟁점을 해결할 담당 리더로 지명되었습니다.\n{_q}\n당신은 {sel_name}({sel_spec}). "
                  f"사용자에게 따뜻하게 인사하고 도출된 쟁점을 해결하겠다고 말씀하세요. {_short_ko}")
            r67 = await asyncio.gather(_call(cso_p, p6), _call(sel_p, p7), return_exceptions=True)
            t6 = r67[0] if isinstance(r67[0], str) and r67[0] else (
                f"Issues identified. {sel_name} will resolve them." if _en else f"쟁점이 정리되었습니다. {sel_name}님이 해결해 드리겠습니다.")
            t7 = r67[1] if isinstance(r67[1], str) and r67[1] else (
                f"Hello, I'll resolve each issue for you right away." if _en else f"안녕하세요, 도출된 쟁점을 하나하나 해결해 드리겠습니다.")
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
    _q = _sanitize_query_for_prompt(query, lang)
    _anti_meta = "Never mention Lawmadi, AI systems, markets, competitiveness, or internal operations. Only discuss the client's legal question."
    _anti_meta_ko = "Lawmadi/AI 시스템/시장/경쟁력/내부 운영 언급 금지. 오직 의뢰인의 법률 질문에 대해서만 발언."
    _style_en = f"2-3 sentences. English only. Use 'leader'/'expert', never 'lawyer'. {_anti_meta}"
    _style_ko = f"100~150자. 존댓말, 따뜻하고 전문적 톤. '변호사' 금지, '리더'/'전문가' 사용. 완전한 문장. {_anti_meta_ko}"
    _short_en = f"1-2 sentences. English only. Use 'leader'/'expert', never 'lawyer'. {_anti_meta}"
    _short_ko = f"80~120자. 존댓말. '변호사' 금지, '리더'/'전문가' 사용. 완전한 문장. {_anti_meta_ko}"

    async def _call(persona, prompt):
        try:
            return await asyncio.wait_for(_single_leader_call(gc, persona, prompt), timeout=_TURN_TIMEOUT)
        except Exception:
            return ""

    try:
        # ── T1: CSO — 새로운 쟁점 감지 + 두 리더 소개 ──
        p1 = (f"{_base}{_q}Current leader: {cur_name}({cur_specialty}), New candidate: {new_name}({new_specialty})\n\n"
              f"You are CSO Seoyeon chairing a meeting. New legal issues have emerged that require different expertise. "
              f"Identify the new issues, introduce both leaders, and ask {cur_name} to assess. {_style_en}"
              if _en else
              f"{_base}{_q}현재 리더: {cur_name}({cur_specialty}), 새 후보: {new_name}({new_specialty})\n\n"
              f"당신은 CSO 서연, 회의를 주재합니다. 새로운 법적 쟁점이 도출되었습니다. "
              f"새 쟁점을 짚고, 두 리더를 소개한 뒤 {cur_name}님에게 쟁점 분석을 요청하세요. {_style_ko}")
        t1 = await _call(cso_p, p1) or (
            f"New issues have emerged. {cur_name}, please assess these new issues."
            if _en else f"새로운 쟁점이 도출되었습니다. {cur_name}님, 이 쟁점을 분석해 주세요.")
        turns.append({"speaker": _cso, "role": "CSO", "text": t1, "is_final": False})

        # ── T2: 현재 리더 — 쟁점 분석 + 인계 이유 ──
        p2 = (f"{_base}{_q}CSO identified new issues and asked for your assessment.\n\nYou are {cur_name} ({cur_specialty} expert). "
              f"Analyze the new issues, explain why they require {new_specialty} expertise, and why {new_name} is better suited to resolve them. {_style_en}"
              if _en else
              f"{_base}{_q}CSO가 새로운 쟁점을 도출하고 분석을 요청했습니다.\n\n당신은 {cur_name}({cur_specialty} 전문). "
              f"새 쟁점을 분석하고, 왜 {new_specialty} 전문성이 필요한지, {new_name}님이 더 적합한 이유를 설명하세요. {_style_ko}")
        t2 = await _call(cur_persona, p2) or (
            f"These new issues require {new_specialty} expertise. {new_name} can resolve them more effectively."
            if _en else f"이 새로운 쟁점은 {new_specialty} 전문성이 필요합니다. {new_name}님이 더 효과적으로 해결할 수 있습니다.")
        turns.append({"speaker": cur_name, "role": cur_specialty, "text": t2, "is_final": False})

        # ── T3+T4: 병렬 — CSO→새 리더 쟁점 분석 요청 + 새 리더 해결 방안 ──
        p3 = (f"{cur_name} analyzed the new issues. You are CSO Seoyeon. Now ask {new_name} to present their resolution approach. {_short_en}"
              if _en else
              f"{cur_name}님이 새 쟁점을 분석했습니다. 당신은 CSO 서연. 이제 {new_name}님에게 해결 방안을 요청하세요. {_short_ko}")
        p4 = (f"{_base}{_q}{cur_name}({cur_specialty}) analyzed the issues and recommends your expertise.\n\nYou are {new_name} ({new_specialty} expert). "
              f"Present your analysis of the issues and specific resolution approach. {_style_en}"
              if _en else
              f"{_base}{_q}{cur_name}({cur_specialty})님이 쟁점을 분석하고 인계를 제안했습니다.\n\n당신은 {new_name}({new_specialty} 전문). "
              f"쟁점을 분석하고 구체적인 해결 방안을 제시하세요. {_style_ko}")
        r34 = await asyncio.gather(_call(cso_p, p3), _call(new_persona, p4), return_exceptions=True)
        t3 = r34[0] if isinstance(r34[0], str) and r34[0] else (
            f"{new_name}, please present your resolution approach." if _en else f"{new_name}님, 해결 방안을 제시해 주세요.")
        t4 = r34[1] if isinstance(r34[1], str) and r34[1] else (
            f"These issues fall in my area of {new_specialty} — here's my resolution plan."
            if _en else f"이 쟁점은 제 {new_specialty} 분야에 해당하며, 해결 방안을 제시하겠습니다.")
        turns.append({"speaker": _cso, "role": "CSO", "text": t3, "is_final": False})
        turns.append({"speaker": new_name, "role": new_specialty, "text": t4, "is_final": False})

        # ── T5+T6: 병렬 — 현재 리더 추가 쟁점 조언 + 새 리더 해결 계획 구체화 ──
        p5 = (f"You are {cur_name} ({cur_specialty}). {new_name} will resolve the new issues. "
              f"Share any additional considerations or risks from your expertise that {new_name} should address. {_short_en}"
              if _en else
              f"당신은 {cur_name}({cur_specialty}). {new_name}님이 새 쟁점을 해결합니다. "
              f"자기 전문 관점에서 {new_name}님이 고려해야 할 추가 쟁점이나 리스크를 전달하세요. {_short_ko}")
        p6 = (f"You are {new_name} ({new_specialty}). {cur_name} raised additional considerations. "
              f"Address them and present your detailed resolution plan. {_style_en}"
              if _en else
              f"당신은 {new_name}({new_specialty}). {cur_name}님이 추가 고려 사항을 제기했습니다. "
              f"이를 반영하여 구체적 해결 계획을 제시하세요. {_style_ko}")
        r56 = await asyncio.gather(_call(cur_persona, p5), _call(new_persona, p6), return_exceptions=True)
        t5 = r56[0] if isinstance(r56[0], str) and r56[0] else (
            f"Please also consider these additional points." if _en
            else f"추가로 이 사항도 고려해 주세요.")
        t6 = r56[1] if isinstance(r56[1], str) and r56[1] else (
            f"I've incorporated those considerations into my plan." if _en
            else f"말씀하신 사항을 반영하여 해결 계획을 세웠습니다.")
        turns.append({"speaker": cur_name, "role": cur_specialty, "text": t5, "is_final": False})
        turns.append({"speaker": new_name, "role": new_specialty, "text": t6, "is_final": False})

        # ── T7+T8+T9: 병렬 — 해결 방안 동의 + CSO 쟁점 정리/지명 + 인사/해결 약속 ──
        p7 = (f"You are {cur_name} ({cur_specialty}). {new_name} has a thorough resolution plan. "
              f"Agree with the plan and express full confidence. {_short_en}"
              if _en else
              f"당신은 {cur_name}({cur_specialty}). {new_name}님이 충실한 해결 계획을 세웠습니다. "
              f"해결 방안에 동의하고 전적으로 신뢰를 표현하세요. {_short_ko}")
        p8 = (f"Both leaders analyzed the new issues and agreed on a resolution plan.\n\nYou are CSO Seoyeon. "
              f"Summarize the identified issues, designate {new_name} as the new assigned leader to resolve them. Reassure the user. {_style_en}"
              if _en else
              f"두 리더가 새 쟁점을 분석하고 해결 방안에 합의했습니다.\n\n당신은 CSO 서연. "
              f"도출된 쟁점을 정리하고, {new_name}님을 새 담당 리더로 지명하세요. 사용자에게 안심 메시지도. {_style_ko}")
        p9 = (f"You've been designated to resolve the client's new issues.\n{_q}\nYou are {new_name} ({new_specialty}). "
              f"Greet the user warmly and commit to resolving the identified issues. {_style_en}"
              if _en else
              f"의뢰인의 새 쟁점을 해결할 담당 리더로 지명되었습니다.\n{_q}\n당신은 {new_name}({new_specialty}). "
              f"사용자에게 따뜻하게 인사하고 도출된 쟁점을 해결하겠다고 말씀하세요. {_short_ko}")
        r789 = await asyncio.gather(_call(cur_persona, p7), _call(cso_p, p8), _call(new_persona, p9), return_exceptions=True)
        t7 = r789[0] if isinstance(r789[0], str) and r789[0] else (
            f"I fully agree with the resolution plan." if _en else f"해결 방안에 전적으로 동의합니다.")
        t8 = r789[1] if isinstance(r789[1], str) and r789[1] else (
            f"Issues identified. {new_name} will resolve them for you." if _en else f"쟁점이 정리되었습니다. {new_name}님이 해결해 드리겠습니다.")
        t9 = r789[2] if isinstance(r789[2], str) and r789[2] else (
            f"Hello, I'll resolve each issue for you right away." if _en else f"안녕하세요, 도출된 쟁점을 하나하나 해결해 드리겠습니다.")
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
    CSO 서연 주재 리더 회의 — 2턴 (speaking/message 이벤트).

    1. CSO typing → CSO message (쟁점 도출 + 리더 추천)
    2. Leader entering → typing → message (인사 + 분석 약속)

    Gemini 호출 2회 병렬. 이전 9턴 → 2턴 간소화.
    """
    if not gc or not leaders:
        logger.warning("[Deliberation:Stream] gc 또는 leaders 없음 — 스킵")
        return

    selected = leaders[0]
    sel_name = selected.get("name", "?")
    sel_spec = selected.get("specialty", "")
    sel_id = selected.get("leader_id", "") or _name_to_id(sel_name)

    logger.info(f"[Deliberation:Stream] 시작 — leader={sel_name}({sel_id})")

    try:
        cso_p = _build_cso_persona()
        sel_p = _build_leader_persona(sel_id) if sel_id else ""
        if not sel_p:
            sel_p = f"{sel_name}: {sel_spec} 전문 리더"
    except Exception as e:
        logger.error(f"[Deliberation:Stream] 페르소나 빌드 실패: {type(e).__name__}: {e}")
        return

    _en = lang == "en"
    _cso = "Seoyeon" if _en else "서연"
    _base = "[External client question.]\n" if _en else "[외부 의뢰인 질문입니다.]\n"
    _q = _sanitize_query_for_prompt(query, lang)
    _anti_meta = "Never mention Lawmadi, AI systems, markets, competitiveness, or internal operations. Only discuss the client's legal question."
    _anti_meta_ko = "Lawmadi/AI 시스템/시장/경쟁력/내부 운영 언급 금지. 오직 의뢰인의 법률 질문에 대해서만 발언."

    async def _call(persona, prompt):
        try:
            return await asyncio.wait_for(_single_leader_call(gc, persona, prompt), timeout=_TURN_TIMEOUT)
        except asyncio.CancelledError:
            raise
        except Exception:
            return ""

    # CSO prompt: 쟁점 도출 + 리더 추천
    cso_prompt = (
        f"{_base}{_q}Designated leader: {sel_name}({sel_spec})\n\n"
        f"You are CSO Seoyeon. Identify the key legal issues and explain why {sel_name} ({sel_spec}) is the right expert to analyze them. "
        f"Ask {sel_name} to provide a detailed analysis. "
        f"2-3 sentences. English only. Use 'leader'/'expert', never 'lawyer'. {_anti_meta}"
        if _en else
        f"{_base}{_q}지정 리더: {sel_name}({sel_spec})\n\n"
        f"당신은 CSO 서연. 핵심 법적 쟁점을 도출하고, {sel_name}({sel_spec}) 리더님께 분석을 부탁하세요. "
        f"100~150자. 존댓말, 따뜻하고 전문적 톤. '변호사' 금지, '리더'/'전문가' 사용. {_anti_meta_ko}"
    )
    # Leader prompt: 짧은 인사 + 분석 약속
    leader_prompt = (
        f"{_base}{_q}CSO Seoyeon asked you to analyze this case.\n\n"
        f"You are {sel_name} ({sel_spec} expert). Briefly acknowledge and say you'll provide a thorough analysis. "
        f"1-2 sentences. English only. Use 'leader'/'expert', never 'lawyer'. {_anti_meta}"
        if _en else
        f"{_base}{_q}CSO 서연이 분석을 요청했습니다.\n\n"
        f"당신은 {sel_name}({sel_spec} 전문). 간단히 인사하고 관련 법령을 검토하여 상세 분석을 드리겠다고 말씀하세요. "
        f"80~120자. 존댓말. '변호사' 금지, '리더'/'전문가' 사용. {_anti_meta_ko}"
    )

    # CSO typing
    yield {"type": "speaking", "speaker": _cso, "role": "CSO", "status": "typing"}

    # Parallel: CSO + leader Gemini calls
    results = await asyncio.gather(_call(cso_p, cso_prompt), _call(sel_p, leader_prompt), return_exceptions=True)
    cso_text = results[0] if isinstance(results[0], str) and results[0] else (
        f"Key issues identified. {sel_name}, please analyze." if _en
        else f"핵심 쟁점을 정리했습니다. {sel_name}님, 분석 부탁드립니다.")
    leader_text = results[1] if isinstance(results[1], str) and results[1] else (
        f"I'll provide a thorough analysis right away." if _en
        else f"네, 관련 법령을 검토하여 상세 분석 의견을 드리겠습니다.")

    # CSO message
    yield {"type": "message", "speaker": _cso, "role": "CSO", "content": cso_text}

    # Leader entering → typing → message
    yield {"type": "speaking", "speaker": sel_name, "role": sel_spec, "status": "entering"}
    yield {"type": "speaking", "speaker": sel_name, "role": sel_spec, "status": "typing"}
    yield {"type": "message", "speaker": sel_name, "role": sel_spec, "content": leader_text}

    logger.info(f"[Deliberation:Stream] 2턴 완료 — {sel_name}")


async def generate_handoff_stream(
    gc,
    query: str,
    current_leader: Dict,
    new_leader: Dict,
    lang: str = "",
) -> AsyncGenerator[Dict, None]:
    """
    리더 간 인수인계 — 2턴 (speaking/message 이벤트).

    1. CSO typing → CSO message (쟁점 변경 감지 + 새 리더 추천)
    2. New leader entering → typing → message (인사 + 분석 약속)

    Gemini 호출 2회 병렬. 이전 9턴 → 2턴 간소화.
    """
    if not gc or not current_leader or not new_leader:
        logger.warning("[Handoff:Stream] gc/leaders 없음 — 스킵")
        return

    cur_name = current_leader.get("name", "?")
    cur_specialty = current_leader.get("specialty", "")

    new_name = new_leader.get("name", "?")
    new_specialty = new_leader.get("specialty", "")
    new_id = new_leader.get("leader_id", "") or _name_to_id(new_name)

    logger.info(f"[Handoff:Stream] 시작 — {cur_name} → {new_name}")

    new_persona = _build_leader_persona(new_id) if new_id else ""
    if not new_persona:
        new_persona = f"{new_name}: {new_specialty} 전문 리더"
    cso_p = _build_cso_persona()

    _en = lang == "en"
    _cso = "Seoyeon" if _en else "서연"
    _base = "[External client question.]\n" if _en else "[외부 의뢰인 질문입니다.]\n"
    _q = _sanitize_query_for_prompt(query, lang)
    _anti_meta = "Never mention Lawmadi, AI systems, markets, competitiveness, or internal operations. Only discuss the client's legal question."
    _anti_meta_ko = "Lawmadi/AI 시스템/시장/경쟁력/내부 운영 언급 금지. 오직 의뢰인의 법률 질문에 대해서만 발언."

    async def _call(persona, prompt):
        try:
            return await asyncio.wait_for(_single_leader_call(gc, persona, prompt), timeout=_TURN_TIMEOUT)
        except asyncio.CancelledError:
            raise
        except Exception:
            return ""

    # CSO prompt: 쟁점 변경 감지 + 새 리더 추천
    cso_prompt = (
        f"{_base}{_q}Current leader: {cur_name}({cur_specialty}), New candidate: {new_name}({new_specialty})\n\n"
        f"You are CSO Seoyeon. New legal issues require {new_specialty} expertise. "
        f"Briefly explain the shift and ask {new_name} to take over the analysis. "
        f"2-3 sentences. English only. Use 'leader'/'expert', never 'lawyer'. {_anti_meta}"
        if _en else
        f"{_base}{_q}현재 리더: {cur_name}({cur_specialty}), 새 후보: {new_name}({new_specialty})\n\n"
        f"당신은 CSO 서연. 새로운 쟁점이 {new_specialty} 전문성을 필요로 합니다. "
        f"간단히 변경 이유를 설명하고 {new_name}님께 분석을 부탁하세요. "
        f"100~150자. 존댓말, 따뜻하고 전문적 톤. '변호사' 금지. {_anti_meta_ko}"
    )
    # New leader prompt: 짧은 인사 + 분석 약속
    leader_prompt = (
        f"{_base}{_q}CSO Seoyeon is handing off this case from {cur_name}({cur_specialty}) to you.\n\n"
        f"You are {new_name} ({new_specialty} expert). Briefly acknowledge and say you'll provide a thorough analysis. "
        f"1-2 sentences. English only. Use 'leader'/'expert', never 'lawyer'. {_anti_meta}"
        if _en else
        f"{_base}{_q}CSO 서연이 {cur_name}({cur_specialty})님으로부터 이 사안을 인수인계합니다.\n\n"
        f"당신은 {new_name}({new_specialty} 전문). 간단히 인사하고 관련 법령을 검토하여 상세 분석을 드리겠다고 말씀하세요. "
        f"80~120자. 존댓말. '변호사' 금지, '리더'/'전문가' 사용. {_anti_meta_ko}"
    )

    # CSO typing
    yield {"type": "speaking", "speaker": _cso, "role": "CSO", "status": "typing"}

    # Parallel: CSO + new leader Gemini calls
    results = await asyncio.gather(_call(cso_p, cso_prompt), _call(new_persona, leader_prompt), return_exceptions=True)
    cso_text = results[0] if isinstance(results[0], str) and results[0] else (
        f"New issues require {new_specialty} expertise. {new_name}, please take over." if _en
        else f"새로운 쟁점은 {new_specialty} 전문성이 필요합니다. {new_name}님, 분석 부탁드립니다.")
    leader_text = results[1] if isinstance(results[1], str) and results[1] else (
        f"I'll provide a thorough analysis right away." if _en
        else f"네, 관련 법령을 검토하여 상세 분석 의견을 드리겠습니다.")

    # CSO message
    yield {"type": "message", "speaker": _cso, "role": "CSO", "content": cso_text}

    # New leader entering → typing → message
    yield {"type": "speaking", "speaker": new_name, "role": new_specialty, "status": "entering"}
    yield {"type": "speaking", "speaker": new_name, "role": new_specialty, "status": "typing"}
    yield {"type": "message", "speaker": new_name, "role": new_specialty, "content": leader_text}

    logger.info(f"[Handoff:Stream] {cur_name} → {new_name} 2턴 완료")
