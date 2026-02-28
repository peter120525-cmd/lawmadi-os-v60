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

from core.model_fallback import get_model, on_quota_error, is_quota_error
from core.pipeline import _build_leader_persona, _load_leader_profiles
from utils.helpers import _safe_extract_gemini_text, _remove_think_blocks

logger = logging.getLogger("LawmadiOS.Deliberation")

# 협의 타임아웃 (초)
_DELIBERATION_TIMEOUT = 8
_HANDOFF_TIMEOUT = 8

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

    full_prompt = f"[페르소나]\n{persona}\n\n[지시]\n{prompt}"
    model_name = get_model()

    def _sync_call():
        for _attempt in range(2):
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
                    ),
                )
            except Exception as e:
                if is_quota_error(e) and _attempt < 1:
                    on_quota_error()
                    continue
                raise

    loop = asyncio.get_running_loop()
    resp = await loop.run_in_executor(None, _sync_call)

    text = _safe_extract_gemini_text(resp).strip()
    text = _remove_think_blocks(text).strip()
    # "변호사" 명칭 사용 금지 — 후처리 안전장치
    text = re.sub(r'변호사', '전문가', text)
    # 300자 truncate (프롬프트에서 150자 이내 지시, 여유분 확보)
    if len(text) > 300:
        text = text[:297] + "..."
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
    CSO 서연 주재 리더 회의 — 3턴 순차 개별 Gemini 호출.

    Turn 1: CSO 서연 → 질문 요약 + 의견 요청
    Turn 2: 담당 리더 → 자기 분야 관점 의견
    Turn 3: CSO 서연 → 담당 리더 지명 (is_final=True)

    Args:
        gc: Gemini client
        query: 사용자 질문
        leaders: 후보 리더 목록 [{"name": ..., "specialty": ..., "leader_id": ...}, ...]
        lang: 언어 코드

    Returns:
        대화 턴 리스트 또는 None (실패 시)
    """
    if not gc or not leaders:
        return None

    selected = leaders[0]
    selected_name = selected.get("name", "?")
    selected_specialty = selected.get("specialty", "")
    selected_id = selected.get("leader_id", "") or _name_to_id(selected_name)

    # 페르소나 빌드
    cso_persona = _build_cso_persona()
    leader_persona = _build_leader_persona(selected_id) if selected_id else ""
    if not leader_persona:
        leader_persona = f"{selected_name}: {selected_specialty} 전문 리더"

    turns: List[Dict] = []

    try:
        # ── Turn 1: CSO 서연 — 질문 요약 + 의견 요청 (순차) ──
        t1_prompt = (
            f"사용자 질문: {query[:300]}\n"
            f"참석 리더: {', '.join(l.get('name','?') + '(' + l.get('specialty','') + ')' for l in leaders[:3])}\n\n"
            f"당신은 CSO 서연입니다. 이 질문의 핵심을 요약하고, "
            f"왜 이 분야의 전문가가 필요한지 설명한 뒤, "
            f"{selected_name}님에게 의견을 요청하세요. "
            f"반드시 100자 이상 150자 이내로 작성하세요. "
            f"존댓말, 따뜻하고 전문적인 톤으로 자연스럽게 말하세요. "
            f"절대 '변호사'라는 명칭을 사용하지 마세요. '리더' 또는 '전문가'로 호칭하세요. "
            f"제목이나 키워드가 아닌, 완전한 문장으로 답변하세요."
        )
        try:
            t1_text = await asyncio.wait_for(
                _single_leader_call(gc, cso_persona, t1_prompt),
                timeout=_TURN_TIMEOUT,
            )
        except Exception:
            t1_text = ""
        if not t1_text:
            t1_text = f"이 질문은 {selected_specialty} 분야입니다. {selected_name}님, 의견 부탁드립니다."
        turns.append({
            "speaker": "서연",
            "role": "CSO",
            "text": t1_text,
            "is_final": False,
        })

        # ── Turn 2+3: 병렬 — 담당 리더 의견 + CSO 지명 ──
        t2_prompt = (
            f"사용자 질문: {query[:300]}\n"
            f"CSO 서연이 당신에게 의견을 요청했습니다.\n\n"
            f"당신은 {selected_name}({selected_specialty} 전문 리더)입니다. "
            f"자기 분야의 전문 지식을 바탕으로 이 질문에 어떻게 도움을 줄 수 있는지 "
            f"구체적으로 설명하고, 자신감 있게 돕겠다고 답하세요. "
            f"반드시 100자 이상 150자 이내로 작성하세요. "
            f"존댓말, 전문적이고 따뜻한 톤으로 자연스럽게 말하세요. "
            f"과장된 자기소개(CLO급, 유니콘 등)는 하지 마세요. 겸손하고 실질적으로 말하세요. "
            f"절대 '변호사'라는 명칭을 사용하지 마세요. '리더' 또는 '전문가'로 호칭하세요. "
            f"제목이나 키워드가 아닌, 완전한 문장으로 답변하세요."
        )
        t3_prompt = (
            f"{selected_name}님이 {selected_specialty} 분야에서 돕겠다고 했습니다.\n\n"
            f"당신은 CSO 서연입니다. {selected_name}님의 전문성을 인정하며 "
            f"이 질문의 담당 리더로 공식 지명하세요. "
            f"사용자에게 안심하라는 말도 덧붙이세요. "
            f"반드시 100자 이상 150자 이내로 작성하세요. "
            f"존댓말, 따뜻하고 신뢰감 있는 톤으로 자연스럽게 말하세요. "
            f"절대 '변호사'라는 명칭을 사용하지 마세요. '리더' 또는 '전문가'로 호칭하세요. "
            f"제목이나 키워드가 아닌, 완전한 문장으로 답변하세요."
        )
        results = await asyncio.gather(
            asyncio.wait_for(
                _single_leader_call(gc, leader_persona, t2_prompt),
                timeout=_TURN_TIMEOUT,
            ),
            asyncio.wait_for(
                _single_leader_call(gc, cso_persona, t3_prompt),
                timeout=_TURN_TIMEOUT,
            ),
            return_exceptions=True,
        )
        t2_text = results[0] if isinstance(results[0], str) and results[0] else ""
        t3_text = results[1] if isinstance(results[1], str) and results[1] else ""
        if not t2_text:
            t2_text = f"네, {selected_specialty} 관점에서 바로 도와드리겠습니다."
        if not t3_text:
            t3_text = f"{selected_name}님이 담당하시겠습니다."
        turns.append({
            "speaker": selected_name,
            "role": selected_specialty,
            "text": t2_text,
            "is_final": False,
        })
        turns.append({
            "speaker": "서연",
            "role": "CSO",
            "text": t3_text,
            "is_final": True,
        })

        logger.info(f"[Deliberation] 3턴 생성 완료 (Turn1 순차 + Turn2+3 병렬)")
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
    리더 간 인수인계 대화 — 2턴 병렬 Gemini 호출.

    Turn 1: 현재 리더 → 인계 이유
    Turn 2: 새 리더   → 인사

    Args:
        gc: Gemini client
        query: 사용자 질문
        current_leader: {"name": ..., "specialty": ..., "leader_id": ...}
        new_leader: {"name": ..., "specialty": ..., "leader_id": ...}
        lang: 언어 코드

    Returns:
        인수인계 턴 리스트 또는 None (실패 시)
    """
    if not gc or not current_leader or not new_leader:
        return None

    cur_name = current_leader.get("name", "?")
    cur_specialty = current_leader.get("specialty", "")
    cur_id = current_leader.get("leader_id", "") or _name_to_id(cur_name)

    new_name = new_leader.get("name", "?")
    new_specialty = new_leader.get("specialty", "")
    new_id = new_leader.get("leader_id", "") or _name_to_id(new_name)

    # 페르소나 빌드
    cur_persona = _build_leader_persona(cur_id) if cur_id else ""
    if not cur_persona:
        cur_persona = f"{cur_name}: {cur_specialty} 전문 리더"
    new_persona = _build_leader_persona(new_id) if new_id else ""
    if not new_persona:
        new_persona = f"{new_name}: {new_specialty} 전문 리더"

    # ── 병렬 호출 ──
    t1_prompt = (
        f"사용자 질문: {query[:300]}\n"
        f"당신은 {cur_name}({cur_specialty} 전문)입니다. "
        f"이 질문은 {new_specialty} 분야에 더 가까워서 "
        f"{new_name}님에게 인계하려 합니다. "
        f"왜 이 질문이 {new_specialty} 분야에 해당하는지, "
        f"그리고 {new_name}님이 더 잘 도와드릴 수 있는 이유를 설명하세요. "
        f"반드시 100자 이상 150자 이내로 작성하세요. "
        f"존댓말, 따뜻한 톤으로 자연스럽게 말하세요. "
        f"절대 '변호사'라는 명칭을 사용하지 마세요. '리더' 또는 '전문가'로 호칭하세요. "
        f"제목이나 키워드가 아닌, 완전한 문장으로 답변하세요."
    )
    t2_prompt = (
        f"사용자 질문: {query[:300]}\n"
        f"당신은 {new_name}({new_specialty} 전문)입니다. "
        f"{cur_name}님이 이 질문을 인계해 주었습니다. "
        f"사용자에게 따뜻하게 인사하고, 자신의 전문 분야에서 "
        f"어떻게 도움을 드릴 수 있는지 구체적으로 설명하세요. "
        f"반드시 100자 이상 150자 이내로 작성하세요. "
        f"존댓말, 전문적이고 친절한 톤으로 자연스럽게 말하세요. "
        f"과장된 자기소개(CLO급, 유니콘 등)는 하지 마세요. 겸손하고 실질적으로 말하세요. "
        f"제목이나 키워드가 아닌, 완전한 문장으로 답변하세요."
    )

    # fallback 텍스트
    t1_fallback = f"이 질문은 {new_specialty} 분야라 {new_name}님께 연결해 드리겠습니다."
    t2_fallback = f"안녕하세요, {new_specialty} 전문 {new_name}입니다. 바로 도와드리겠습니다."

    try:
        results = await asyncio.gather(
            _single_leader_call(gc, cur_persona, t1_prompt),
            _single_leader_call(gc, new_persona, t2_prompt),
            return_exceptions=True,
        )

        t1_text = results[0] if isinstance(results[0], str) and results[0] else t1_fallback
        t2_text = results[1] if isinstance(results[1], str) and results[1] else t2_fallback

        turns = [
            {
                "speaker": cur_name,
                "role": cur_specialty,
                "text": t1_text,
            },
            {
                "speaker": new_name,
                "role": new_specialty,
                "text": t2_text,
            },
        ]

        logger.info(f"[Handoff] {cur_name} → {new_name} (2턴, parallel calls)")
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

_TURN_TIMEOUT = 5  # 개별 턴 타임아웃 (초)


async def generate_deliberation_stream(
    gc,
    query: str,
    leaders: List[Dict],
    lang: str = "",
) -> AsyncGenerator[Dict, None]:
    """
    CSO 서연 주재 리더 회의 — 3턴 순차, 턴별 즉시 yield.

    Turn 1: CSO 서연 → 질문 요약 + 의견 요청
    Turn 2: 담당 리더 → 자기 분야 관점 의견
    Turn 3: CSO 서연 → 담당 리더 지명 (is_final=True)
    """
    if not gc or not leaders:
        logger.warning("[Deliberation:Stream] gc 또는 leaders 없음 — 스킵")
        return

    selected = leaders[0]
    selected_name = selected.get("name", "?")
    selected_specialty = selected.get("specialty", "")
    selected_id = selected.get("leader_id", "") or _name_to_id(selected_name)

    logger.info(f"[Deliberation:Stream] 시작 — leader={selected_name}({selected_id})")

    try:
        cso_persona = _build_cso_persona()
        leader_persona = _build_leader_persona(selected_id) if selected_id else ""
        if not leader_persona:
            leader_persona = f"{selected_name}: {selected_specialty} 전문 리더"
    except Exception as e:
        logger.error(f"[Deliberation:Stream] 페르소나 빌드 실패: {type(e).__name__}: {e}")
        return

    # ── Turn 1: CSO 서연 ──
    t1_prompt = (
        f"사용자 질문: {query[:300]}\n"
        f"참석 리더: {', '.join(l.get('name','?') + '(' + l.get('specialty','') + ')' for l in leaders[:3])}\n\n"
        f"당신은 CSO 서연입니다. 이 질문의 핵심을 요약하고, "
        f"왜 이 분야의 전문가가 필요한지 설명한 뒤, "
        f"{selected_name}님에게 의견을 요청하세요. "
        f"반드시 100자 이상 150자 이내로 작성하세요. "
        f"존댓말, 따뜻하고 전문적인 톤으로 자연스럽게 말하세요. "
        f"제목이나 키워드가 아닌, 완전한 문장으로 답변하세요."
    )
    logger.info("[Deliberation:Stream] Turn1 Gemini 호출 시작")
    try:
        t1_text = await asyncio.wait_for(
            _single_leader_call(gc, cso_persona, t1_prompt), timeout=_TURN_TIMEOUT
        )
        logger.info(f"[Deliberation:Stream] Turn1 성공 ({len(t1_text)}자)")
    except BaseException as e:
        logger.warning(f"[Deliberation:Stream] Turn1 실패: {type(e).__name__}: {e}")
        t1_text = ""
        # CancelledError는 재발생시켜야 함
        if isinstance(e, asyncio.CancelledError):
            raise
    if not t1_text:
        t1_text = f"이 질문은 {selected_specialty} 분야입니다. {selected_name}님, 의견 부탁드립니다."
    yield {
        "speaker": "서연",
        "role": "CSO",
        "text": t1_text,
        "is_final": False,
    }
    logger.info("[Deliberation:Stream] Turn1 yield 완료")

    # ── Turn 2: 담당 리더 ──
    t2_prompt = (
        f"사용자 질문: {query[:300]}\n"
        f"CSO 서연이 당신에게 의견을 요청했습니다.\n\n"
        f"당신은 {selected_name}({selected_specialty} 전문)입니다. "
        f"자기 분야의 전문 지식을 바탕으로 이 질문에 어떻게 도움을 줄 수 있는지 "
        f"구체적으로 설명하고, 자신감 있게 돕겠다고 답하세요. "
        f"반드시 100자 이상 150자 이내로 작성하세요. "
        f"존댓말, 전문적이고 따뜻한 톤으로 자연스럽게 말하세요. "
        f"제목이나 키워드가 아닌, 완전한 문장으로 답변하세요."
    )
    logger.info("[Deliberation:Stream] Turn2 Gemini 호출 시작")
    try:
        t2_text = await asyncio.wait_for(
            _single_leader_call(gc, leader_persona, t2_prompt), timeout=_TURN_TIMEOUT
        )
        logger.info(f"[Deliberation:Stream] Turn2 성공 ({len(t2_text)}자)")
    except BaseException as e:
        logger.warning(f"[Deliberation:Stream] Turn2 실패: {type(e).__name__}: {e}")
        t2_text = ""
        if isinstance(e, asyncio.CancelledError):
            raise
    if not t2_text:
        t2_text = f"네, {selected_specialty} 관점에서 바로 도와드리겠습니다."
    yield {
        "speaker": selected_name,
        "role": selected_specialty,
        "text": t2_text,
        "is_final": False,
    }
    logger.info("[Deliberation:Stream] Turn2 yield 완료")

    # ── Turn 3: CSO 서연 — 담당 리더 지명 ──
    t3_prompt = (
        f"{selected_name}님이 {selected_specialty} 분야에서 돕겠다고 했습니다.\n\n"
        f"당신은 CSO 서연입니다. {selected_name}님의 전문성을 인정하며 "
        f"이 질문의 담당 리더로 공식 지명하세요. "
        f"사용자에게 안심하라는 말도 덧붙이세요. "
        f"반드시 100자 이상 150자 이내로 작성하세요. "
        f"존댓말, 따뜻하고 신뢰감 있는 톤으로 자연스럽게 말하세요. "
        f"제목이나 키워드가 아닌, 완전한 문장으로 답변하세요."
    )
    logger.info("[Deliberation:Stream] Turn3 Gemini 호출 시작")
    try:
        t3_text = await asyncio.wait_for(
            _single_leader_call(gc, cso_persona, t3_prompt), timeout=_TURN_TIMEOUT
        )
        logger.info(f"[Deliberation:Stream] Turn3 성공 ({len(t3_text)}자)")
    except BaseException as e:
        logger.warning(f"[Deliberation:Stream] Turn3 실패: {type(e).__name__}: {e}")
        t3_text = ""
        if isinstance(e, asyncio.CancelledError):
            raise
    if not t3_text:
        t3_text = f"{selected_name}님이 담당하시겠습니다."
    yield {
        "speaker": "서연",
        "role": "CSO",
        "text": t3_text,
        "is_final": True,
    }
    logger.info("[Deliberation:Stream] 3턴 스트리밍 완료")


async def generate_handoff_stream(
    gc,
    query: str,
    current_leader: Dict,
    new_leader: Dict,
    lang: str = "",
) -> AsyncGenerator[Dict, None]:
    """
    리더 간 인수인계 대화 — 2턴 순차 yield.

    Turn 1: 현재 리더 → 인계 이유
    Turn 2: 새 리더   → 인사
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

    # ── Turn 1: 현재 리더 ──
    t1_prompt = (
        f"사용자 질문: {query[:300]}\n"
        f"당신은 {cur_name}({cur_specialty} 전문)입니다. "
        f"이 질문은 {new_specialty} 분야에 더 가까워서 "
        f"{new_name}님에게 인계하려 합니다. "
        f"왜 이 질문이 {new_specialty} 분야에 해당하는지, "
        f"그리고 {new_name}님이 더 잘 도와드릴 수 있는 이유를 설명하세요. "
        f"반드시 100자 이상 150자 이내로 작성하세요. "
        f"존댓말, 따뜻한 톤으로 자연스럽게 말하세요. "
        f"절대 '변호사'라는 명칭을 사용하지 마세요. '리더' 또는 '전문가'로 호칭하세요. "
        f"제목이나 키워드가 아닌, 완전한 문장으로 답변하세요."
    )
    t1_fallback = f"이 질문은 {new_specialty} 분야라 {new_name}님께 연결해 드리겠습니다."

    try:
        t1_text = await asyncio.wait_for(
            _single_leader_call(gc, cur_persona, t1_prompt), timeout=_TURN_TIMEOUT
        )
    except BaseException as e:
        logger.warning(f"[Handoff:Stream] Turn1 실패: {type(e).__name__}: {e}")
        t1_text = ""
        if isinstance(e, asyncio.CancelledError):
            raise
    if not t1_text:
        t1_text = t1_fallback
    yield {
        "speaker": cur_name,
        "role": cur_specialty,
        "text": t1_text,
    }

    # ── Turn 2: 새 리더 ──
    t2_prompt = (
        f"사용자 질문: {query[:300]}\n"
        f"당신은 {new_name}({new_specialty} 전문)입니다. "
        f"{cur_name}님이 이 질문을 인계해 주었습니다. "
        f"사용자에게 따뜻하게 인사하고, 자신의 전문 분야에서 "
        f"어떻게 도움을 드릴 수 있는지 구체적으로 설명하세요. "
        f"반드시 100자 이상 150자 이내로 작성하세요. "
        f"존댓말, 전문적이고 친절한 톤으로 자연스럽게 말하세요. "
        f"과장된 자기소개(CLO급, 유니콘 등)는 하지 마세요. 겸손하고 실질적으로 말하세요. "
        f"제목이나 키워드가 아닌, 완전한 문장으로 답변하세요."
    )
    t2_fallback = f"안녕하세요, {new_specialty} 전문 {new_name}입니다. 바로 도와드리겠습니다."

    try:
        t2_text = await asyncio.wait_for(
            _single_leader_call(gc, new_persona, t2_prompt), timeout=_TURN_TIMEOUT
        )
    except BaseException as e:
        logger.warning(f"[Handoff:Stream] Turn2 실패: {type(e).__name__}: {e}")
        t2_text = ""
        if isinstance(e, asyncio.CancelledError):
            raise
    if not t2_text:
        t2_text = t2_fallback
    yield {
        "speaker": new_name,
        "role": new_specialty,
        "text": t2_text,
    }
    logger.info(f"[Handoff:Stream] {cur_name} → {new_name} 스트리밍 완료")
