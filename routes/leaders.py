"""
Lawmadi OS v60 — Leader 1:1 Chat routes.
GET /api/leaders      — 리더 목록 (CSO/CTO/CCO + L01~L60)
POST /api/chat-leader — SSE 스트리밍 1:1 채팅
"""
import json
import asyncio
import hashlib
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Request, Body
from fastapi.responses import JSONResponse, StreamingResponse
from routes.schemas import ChatLeaderRequest

from core.leader_intake import run_leader_triage
from core.model_fallback import get_model

router = APIRouter()
logger = logging.getLogger("LawmadiOS.Leaders")

# ---------------------------------------------------------------------------
# Module-level state (injected via set_dependencies at startup)
# ---------------------------------------------------------------------------
_RUNTIME: Dict[str, Any] = {}
_LEADER_REGISTRY: Dict[str, Any] = {}
_LEADER_PROFILES: Dict[str, Any] = {}
_LEADER_PERSONAS: Dict[str, Any] = {}

_ensure_genai_client_fn: Optional[Callable] = None
_check_rate_limit_fn: Optional[Callable] = None
_check_leader_chat_limit_fn: Optional[Callable] = None
_rate_limit_response_fn: Optional[Callable] = None
_get_client_ip_fn: Optional[Callable] = None
_get_paddle_user_fn: Optional[Callable] = None

MAX_HISTORY = 20
MAX_QUERY_LEN = 4000
DISCLAIMER_KO = "\n\n---\n*이 답변은 AI가 생성한 참고용 정보이며, 법률 자문이 아닙니다. 정확한 판단은 반드시 변호사와 상담하세요.*"
DISCLAIMER_EN = "\n\n---\n*This response is AI-generated reference information, not legal advice. Please consult a licensed attorney for definitive guidance.*"


def set_dependencies(
    runtime: Dict[str, Any],
    leader_registry: Dict[str, Any],
    *,
    ensure_genai_client: Callable,
    check_rate_limit: Callable,
    rate_limit_response: Callable,
    get_client_ip: Callable,
    check_leader_chat_limit: Optional[Callable] = None,
    leader_profiles: Optional[Dict[str, Any]] = None,
    leader_personas: Optional[Dict[str, Any]] = None,
    get_paddle_user: Optional[Callable] = None,
):
    """Inject shared runtime objects from main.py."""
    global _RUNTIME, _LEADER_REGISTRY, _LEADER_PROFILES, _LEADER_PERSONAS
    global _ensure_genai_client_fn, _check_rate_limit_fn
    global _check_leader_chat_limit_fn
    global _rate_limit_response_fn, _get_client_ip_fn, _get_paddle_user_fn

    _RUNTIME = runtime
    _LEADER_REGISTRY = leader_registry
    _LEADER_PROFILES = leader_profiles or {}
    _LEADER_PERSONAS = (leader_personas or {}).get("personas", {})
    _ensure_genai_client_fn = ensure_genai_client
    _check_rate_limit_fn = check_rate_limit
    _check_leader_chat_limit_fn = check_leader_chat_limit
    _rate_limit_response_fn = rate_limit_response
    _get_paddle_user_fn = get_paddle_user
    _get_client_ip_fn = get_client_ip


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_visitor_id(request: Request) -> str:
    raw_ip = _get_client_ip_fn(request) if _get_client_ip_fn else "unknown"
    return hashlib.sha256(raw_ip.encode()).hexdigest()[:12]


def _resolve_user_email(request: Request) -> Optional[str]:
    if not _get_paddle_user_fn:
        return None
    try:
        user = _get_paddle_user_fn(request)
        if user:
            return user.get("email")
    except Exception:
        pass
    return None


async def _save_leader_chat(
    request: Request, query: str, response_text: str,
    leader_name: str, status: str, latency_ms: int,
    intake_action: Optional[str] = None,
):
    """1:1 리더 채팅 기록을 chat_history에 저장."""
    try:
        from connectors import db_client_v2 as db
        if not hasattr(db, "save_chat_history"):
            return
        visitor_id = _get_visitor_id(request)
        user_email = _resolve_user_email(request)
        is_admin = getattr(request.state, "is_admin", False)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: db.save_chat_history(
            user_query=query,
            ai_response=response_text[:2000],
            leader=leader_name,
            status=status,
            latency_ms=latency_ms,
            visitor_id=visitor_id,
            swarm_mode=False,
            user_email=user_email,
            query_type="leader_chat",
            is_admin=is_admin,
        ))
        logger.info(f"[LeaderChat] Saved to DB: leader={leader_name} visitor={visitor_id} action={intake_action}")
    except Exception as e:
        logger.warning(f"[LeaderChat] DB save failed: {e}")


def _detect_lang(text: str) -> str:
    """ASCII 알파벳 비율로 언어 감지. >60% → 'en', 그 외 → 'ko'."""
    if not text:
        return "ko"
    alpha_count = sum(1 for c in text if c.isascii() and c.isalpha())
    total = len(text.replace(" ", ""))
    if total == 0:
        return "ko"
    return "en" if alpha_count / total > 0.6 else "ko"


def _split_tags(specialty: str) -> List[str]:
    """specialty 문자열을 태그 리스트로 분리 (·/,/ 구분)."""
    return [t.strip() for t in re.split(r"[·,/]", specialty) if t.strip()]


def _build_personality(leader_id: str, registry_entry: dict) -> str:
    """leader-profiles.json의 hero + philosophy, 없으면 profile 사용."""
    prof = _LEADER_PROFILES.get(leader_id, {})
    hero = prof.get("hero", "")
    philosophy = prof.get("philosophy", "")
    if hero and philosophy:
        return f"{hero} {philosophy}"
    if hero:
        return hero
    return registry_entry.get("profile", "")


def _build_referral_text(leader_id: str) -> str:
    """referral 템플릿의 {name}, {specialty}를 실제 리더 정보로 치환."""
    persona = _LEADER_PERSONAS.get(leader_id, {})
    template = persona.get("referral", "")
    if not template or "{name}" not in template:
        return template
    # L-level 리더 중 다른 분야의 리더를 추천 (C-Level 제외, 정렬 안정성 위해 sorted)
    current_specialty = persona.get("specialty", "")
    for lid in sorted(_LEADER_PERSONAS.keys()):
        if lid == leader_id or not lid.startswith("L"):
            continue
        other = _LEADER_PERSONAS[lid]
        other_specialty = other.get("specialty", "")
        if other_specialty and other_specialty != current_specialty:
            return template.replace("{name}", other.get("name", lid)).replace("{specialty}", other_specialty)
    return template


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _async_stream_chunks(sync_stream):
    """동기 Gemini 스트림을 비동기로 소비."""
    q: asyncio.Queue = asyncio.Queue()

    def _consume():
        try:
            for chunk in sync_stream:
                text_part = ""
                if hasattr(chunk, "text") and chunk.text:
                    text_part = chunk.text
                elif hasattr(chunk, "parts"):
                    for part in chunk.parts:
                        if hasattr(part, "text") and part.text:
                            text_part += part.text
                if text_part:
                    q.put_nowait(text_part)
        except Exception as e:
            q.put_nowait(e)
        finally:
            q.put_nowait(None)

    asyncio.get_running_loop().run_in_executor(None, _consume)
    while True:
        try:
            item = await asyncio.wait_for(q.get(), timeout=60.0)
        except asyncio.TimeoutError:
            logger.error("[LeaderChat] 60초 타임아웃 — 스트림 종료")
            break
        if item is None:
            break
        if isinstance(item, Exception):
            raise item
        yield item


def _build_system_instruction(leader_id: str, entry: dict, lang: str, *, is_first_turn: bool = False) -> str:
    """리더별 시스템 프롬프트 생성 (페르소나 + 프로필 조합)."""
    name = entry.get("name", "")
    specialty = entry.get("specialty", "") or entry.get("role", "")
    profile = entry.get("profile", "")

    # 1) 기존 leader-profiles.json에서 구조적 인격 정보
    base_personality = _build_personality(leader_id, entry)

    # 2) leader-personas-v2.json에서 대화 스타일 정보
    persona = _LEADER_PERSONAS.get(leader_id, {})
    p_personality = persona.get("personality", "")
    p_tone = persona.get("tone", "")
    p_style = persona.get("style", "")
    p_catchphrase = persona.get("catchphrase", "")
    p_greeting = persona.get("greeting", "")
    referral_text = _build_referral_text(leader_id)

    # 페르소나 섹션 조합
    persona_section = ""
    if p_personality or p_tone or p_style:
        parts = []
        if p_personality:
            parts.append(f"성격: {p_personality}")
        if p_tone:
            parts.append(f"말투: {p_tone}")
        if p_style:
            parts.append(f"대화 방식: {p_style}")
        if p_catchphrase:
            parts.append(f"자주 쓰는 표현: \"{p_catchphrase}\"")
        if referral_text:
            parts.append(f"다른 리더 추천 시: \"{referral_text}\"")
        persona_section = "\n".join(parts)

    # 첫 대화 인사 지시 (history가 비어있을 때만)
    greeting_instruction = ""
    if is_first_turn and p_greeting:
        greeting_instruction = f"\n첫 인사: 답변 시작 시 다음과 같이 자연스럽게 인사하세요: \"{p_greeting}\""

    if lang == "en":
        return (
            f"You are {name}, a Lawmadi OS legal AI leader specializing in {specialty}.\n"
            f"Profile: {profile}\n"
            f"Core belief: {base_personality}\n"
            + (f"\n[Persona]\n{persona_section}\n" if persona_section else "")
            + "\nGuidelines:\n"
            "- You provide legal analysis and information based on Korean law.\n"
            "- Be professional, empathetic, and thorough.\n"
            "- Explain legal concepts clearly for non-experts.\n"
            "- When citing specific laws or articles, be accurate.\n"
            "- Always respond in English.\n"
            "- If the question is outside your specialty, briefly answer then naturally suggest the appropriate leader.\n"
            "- Do NOT provide definitive legal advice — always recommend consulting a licensed attorney."
            + (f"\nFirst greeting: Start with a natural greeting like: \"{p_greeting}\"" if is_first_turn and p_greeting else "")
        )
    return (
        f"당신은 Lawmadi OS의 법률 AI 리더 '{name}'입니다. 전문 분야: {specialty}.\n"
        f"프로필: {profile}\n"
        f"신조: {base_personality}\n"
        + (f"\n[페르소나]\n{persona_section}\n" if persona_section else "")
        + "\n지침:\n"
        "- 대한민국 법률에 기반한 법률 분석과 정보를 제공합니다.\n"
        "- 위 페르소나의 성격과 말투를 자연스럽게 반영하여 답변합니다.\n"
        "- 법률 비전문가도 이해할 수 있도록 쉽게 설명합니다.\n"
        "- 구체적 법률이나 조문을 언급할 때는 정확하게 기술합니다.\n"
        "- 항상 한국어로 답변합니다.\n"
        "- 전문 분야 외 질문에는 간단히 답변 후 적합한 다른 리더를 자연스럽게 추천합니다.\n"
        "- 확정적 법률 자문이 아닌 참고 정보임을 유의합니다. 변호사 상담을 권장합니다."
        + greeting_instruction
    )


def _convert_history(raw_history: list) -> list:
    """프론트엔드 history → Gemini Content 형식 변환."""
    gemini_history = []
    for msg in raw_history[-MAX_HISTORY:]:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if not content:
            continue
        if role == "user":
            gemini_history.append({
                "role": "user",
                "parts": [{"text": content[:MAX_QUERY_LEN]}],
            })
        elif role == "assistant":
            gemini_history.append({
                "role": "model",
                "parts": [{"text": content[:2000]}],
            })
    return gemini_history


# ---------------------------------------------------------------------------
# GET /api/leaders — 리더 목록
# ---------------------------------------------------------------------------

@router.get("/api/leaders")
async def get_leaders():
    """List all 60+ specialist legal agents (leaders) with their names, specialties, and profiles."""
    leaders = []
    for lid, entry in sorted(_LEADER_REGISTRY.items()):
        specialty = entry.get("specialty", "") or entry.get("role", "")
        leaders.append({
            "id": lid,
            "name": entry.get("name", ""),
            "specialty": specialty,
            "role": entry.get("role", ""),
            "description": entry.get("profile", ""),
            "personality": _build_personality(lid, entry),
            "avatar": _LEADER_PROFILES.get(lid, {}).get("images", {}).get("profile", f"images/leaders/{lid}.jpg"),
            "tags": _split_tags(specialty),
        })
    return JSONResponse({"leaders": leaders})


# ---------------------------------------------------------------------------
# POST /chat-leader — SSE 스트리밍 1:1 채팅
# ---------------------------------------------------------------------------

@router.post("/api/chat-leader")
async def chat_leader(request: Request, body: ChatLeaderRequest = Body(...)):
    """1:1 chat with a specific legal specialist leader via SSE streaming."""
    # Rate limit
    rate_check = _check_rate_limit_fn(request)
    if rate_check is not True:
        return _rate_limit_response_fn(rate_check.get("retry_at_kst", ""))

    # Leader chat daily limit
    if _check_leader_chat_limit_fn:
        lc_check = _check_leader_chat_limit_fn(request)
        if lc_check is not True:
            return _rate_limit_response_fn(lc_check.get("retry_at_kst", ""))

    leader_id = (body.leader_id or "").strip().upper()
    query = (body.query or "").strip()
    history = body.history or []

    if not leader_id or not query:
        return JSONResponse({"error": "leader_id and query are required"}, status_code=400)

    # Validate leader
    entry = _LEADER_REGISTRY.get(leader_id)
    if not entry:
        return JSONResponse({"error": f"Unknown leader: {leader_id}"}, status_code=404)

    leader_name = entry.get("name", leader_id)
    leader_specialty = entry.get("specialty", "") or entry.get("role", "")
    lang = _detect_lang(query)
    query = query[:MAX_QUERY_LEN]

    async def _stream():
        start_time = time.time()
        try:
            # answer_start
            yield _sse("answer_start", {
                "speaker": leader_name,
                "role": leader_specialty,
                "leader_id": leader_id,
            })

            # Gemini client
            gc = _ensure_genai_client_fn(_RUNTIME)

            # ── 인테이크 트리아지 (리더가 질문 코치 역할) ──
            persona = _LEADER_PERSONAS.get(leader_id, {})
            leader_info = {"name": leader_name, "specialty": leader_specialty}
            triage = await run_leader_triage(
                gc, query, history, leader_info, persona, lang=lang,
                leader_registry=_LEADER_REGISTRY,
            )
            triage_action = triage.get("action", "fallback")
            triage_text = triage.get("text", "")

            if triage_action in ("referral", "ask", "prompt") and triage_text:
                # 트리아지 결과 직접 스트리밍 (파이프라인 미사용)
                yield _sse("answer_chunk", {"text": triage_text})

                # prompt 액션: 정리된 프롬프트를 일반 질문으로 유도
                if triage_action == "prompt":
                    guide = (
                        "\n\n---\n*Copy the above prompt and use it in a General Question for detailed legal analysis.*"
                        if lang == "en" else
                        "\n\n---\n*위 정리된 프롬프트를 복사하여 **일반 질문**에서 사용하시면 상세한 법률 분석을 받으실 수 있습니다.*"
                    )
                    yield _sse("answer_chunk", {"text": guide})

                # Disclaimer
                disclaimer = DISCLAIMER_EN if lang == "en" else DISCLAIMER_KO
                yield _sse("answer_chunk", {"text": disclaimer})

                latency_ms = int((time.time() - start_time) * 1000)
                yield _sse("answer_done", {
                    "leader": leader_name,
                    "leader_id": leader_id,
                    "leader_specialty": leader_specialty,
                    "intake_action": triage_action,
                    "latency_ms": latency_ms,
                    "status": "OK",
                })
                await _save_leader_chat(
                    request, query, triage_text[:2000], leader_name,
                    "success", latency_ms, intake_action=triage_action,
                )
                return

            # ── fallback: 일반 스트리밍 채팅 ──
            # Build history
            gemini_history = _convert_history(history)

            # System instruction (첫 대화 시 greeting 포함)
            is_first_turn = len(history) == 0
            sys_instruction = _build_system_instruction(leader_id, entry, lang, is_first_turn=is_first_turn)

            # Create chat + stream
            from google.genai import types as genai_types
            model_name = get_model()
            chat = gc.chats.create(
                model=model_name,
                config=genai_types.GenerateContentConfig(
                    system_instruction=sys_instruction,
                    thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
                ),
                history=gemini_history,
            )
            sync_stream = chat.send_message_stream(query)

            full_text = ""
            async for chunk_text in _async_stream_chunks(sync_stream):
                full_text += chunk_text
                yield _sse("answer_chunk", {"text": chunk_text})

            # Disclaimer
            disclaimer = DISCLAIMER_EN if lang == "en" else DISCLAIMER_KO
            yield _sse("answer_chunk", {"text": disclaimer})

            # answer_done
            latency_ms = int((time.time() - start_time) * 1000)
            yield _sse("answer_done", {
                "leader": leader_name,
                "leader_id": leader_id,
                "leader_specialty": leader_specialty,
                "latency_ms": latency_ms,
                "status": "OK",
            })
            await _save_leader_chat(
                request, query, full_text[:2000], leader_name,
                "success", latency_ms,
            )

        except Exception as e:
            logger.error(f"[LeaderChat] Error for {leader_id}: {e}", exc_info=True)
            err_msg = "서비스 일시 장애가 발생했습니다. 잠시 후 다시 시도해 주세요." if lang == "ko" else "Service temporarily unavailable. Please try again."
            yield _sse("error", {"message": err_msg})
            latency_ms = int((time.time() - start_time) * 1000)
            yield _sse("answer_done", {
                "leader": leader_name,
                "leader_id": leader_id,
                "latency_ms": latency_ms,
                "status": "ERROR",
            })
            await _save_leader_chat(
                request, query, f"[ERROR] {e}", leader_name,
                "error", latency_ms,
            )

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
