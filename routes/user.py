"""User-facing routes: plans, lawyer inquiry, feedback, suggest-questions, API v1."""
import os
import json
import re
import logging
from typing import Any, Dict, List, Callable, Coroutine
from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from google.genai import types as genai_types

from core.constants import OS_VERSION, DEFAULT_GEMINI_MODEL
from utils.helpers import _now_iso

router = APIRouter()
logger = logging.getLogger("LawmadiOS.User")

_RUNTIME: Dict[str, Any] = {}
_limiter = None

# In-memory stores (FIFO)
LAWYER_INQUIRY_STORE: List[Dict] = []
FEEDBACK_STORE: List[Dict] = []

# Stub references for /api/v1/ask and /api/v1/search
# These will be connected via set_dependencies from main.py
_ask_fn: Callable[..., Coroutine] = None  # type: ignore[assignment]
_search_fn: Callable[..., Coroutine] = None  # type: ignore[assignment]

# Zapier / external API key auth
_API_KEYS: set = set()


def set_dependencies(runtime, limiter=None, ask_fn=None, search_fn=None):
    """Inject shared runtime objects from main.py at startup."""
    global _RUNTIME, _limiter, _ask_fn, _search_fn, _API_KEYS
    _RUNTIME = runtime
    _limiter = limiter
    _ask_fn = ask_fn
    _search_fn = search_fn
    _API_KEYS = set(k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip())


def _verify_api_key(authorization: str = Header(default="")) -> None:
    """Zapier / external API key verification (Bearer token) — FAIL_CLOSED."""
    if not _API_KEYS:
        raise HTTPException(status_code=403, detail="API_KEYS not configured")
    token = authorization.removeprefix("Bearer ").strip()
    if token not in _API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")


# =============================================================
# Plans
# =============================================================

@router.get("/plans")
async def get_plans():
    """Premium plan info (frontend pricing page rendering)."""
    return {
        "plans": {
            "free": {
                "name": "무료",
                "price": 0,
                "features": [
                    "4시간당 10회 질문",
                    "기본 AI 분석",
                    "60명 리더 협업",
                    "SSOT 법령 검증",
                ],
            },
            "premium": {
                "name": "프리미엄",
                "price": 9900,
                "currency": "KRW",
                "period": "월",
                "features": [
                    "4시간당 100회 질문",
                    "5000자+ 심층 응답",
                    "Claude 전문가 검증",
                    "상담 이력 관리",
                    "전문 변호사 연결",
                ],
            },
        }
    }


# =============================================================
# Lawyer Inquiry (in-memory, latest 500 FIFO)
# =============================================================

@router.post("/lawyer-inquiry")
async def submit_lawyer_inquiry(request: Request):
    """Lawyer referral inquiry — name + contact + summary."""
    try:
        data = await request.json()
        name = str(data.get("name", "")).strip()[:50]
        phone = str(data.get("phone", "")).strip()[:20]
        query_summary = str(data.get("query_summary", "")).strip()[:500]
        leader = str(data.get("leader", "")).strip()[:50]

        if not name or not phone:
            return JSONResponse(status_code=400, content={"error": "이름과 연락처는 필수입니다."})

        entry = {
            "name": name,
            "phone": phone,
            "query_summary": query_summary,
            "leader": leader,
            "ts": _now_iso(),
            "status": "pending",
        }
        LAWYER_INQUIRY_STORE.append(entry)
        while len(LAWYER_INQUIRY_STORE) > 500:
            LAWYER_INQUIRY_STORE.pop(0)
        logger.info(f"[LAWYER-INQUIRY] Received: {name} / {leader} (total={len(LAWYER_INQUIRY_STORE)})")
        return {"ok": True, "message": "변호사 상담 신청이 접수되었습니다. 빠른 시일 내 연락드리겠습니다."}
    except Exception as e:
        logger.warning(f"[LAWYER-INQUIRY] error: {e}")
        return JSONResponse(status_code=400, content={"error": str(e)})


# =============================================================
# Feedback (in-memory, latest 1000 FIFO)
# =============================================================

@router.post("/feedback")
async def submit_feedback(request: Request):
    """Response satisfaction feedback (up/down) storage."""
    try:
        data = await request.json()
        rating = data.get("rating", "")
        if rating not in ("up", "down"):
            return JSONResponse(status_code=400, content={"error": "rating must be 'up' or 'down'"})
        entry = {
            "trace_id": str(data.get("trace_id", ""))[:64],
            "rating": rating,
            "query": str(data.get("query", ""))[:500],
            "leader": str(data.get("leader", ""))[:50],
            "ts": _now_iso(),
        }
        FEEDBACK_STORE.append(entry)
        # FIFO: keep latest 1000
        while len(FEEDBACK_STORE) > 1000:
            FEEDBACK_STORE.pop(0)
        logger.info(f"[FEEDBACK] {rating} from {entry['leader']} (total={len(FEEDBACK_STORE)})")
        return {"ok": True}
    except Exception as e:
        logger.warning(f"[FEEDBACK] error: {e}")
        return JSONResponse(status_code=400, content={"error": str(e)})


# =============================================================
# Suggest Questions (Gemini-based)
# =============================================================

@router.post("/suggest-questions")
async def suggest_questions(request: Request):
    """Suggest 3 follow-up questions based on current query/leader."""
    try:
        data = await request.json()
        query = str(data.get("query", ""))[:500]
        leader = str(data.get("leader", ""))[:50]
        specialty = str(data.get("specialty", ""))[:50]

        if not query:
            return {"suggestions": []}

        gc = _RUNTIME.get("genai_client")
        if not gc:
            return {"suggestions": []}

        prompt = (
            f"사용자가 '{specialty}' 분야의 법률 전문가({leader})에게 다음 질문을 했습니다:\n"
            f"\"{query}\"\n\n"
            f"이 질문에 이어서 사용자가 물어볼 만한 후속 질문 3개를 생성하세요.\n"
            f"각 질문은 20자~50자로 간결하고 구체적으로 작성하세요.\n"
            f"JSON 배열 형식으로만 답하세요: [\"질문1\", \"질문2\", \"질문3\"]"
        )

        resp = gc.models.generate_content(
            model=DEFAULT_GEMINI_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(max_output_tokens=200, temperature=0.7),
        )
        text = (resp.text or "").strip()

        # Parse JSON array
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            suggestions = json.loads(match.group())
            suggestions = [str(s).strip() for s in suggestions if isinstance(s, str) and s.strip()][:3]
        else:
            suggestions = []

        return {"suggestions": suggestions}
    except Exception as e:
        logger.warning(f"[SUGGEST] error: {e}")
        return {"suggestions": []}


# =============================================================
# API v1 (Zapier integration)
# =============================================================

@router.get("/api/v1/me")
async def api_v1_me(authorization: str = Header(default="")):
    """API key verification test (Zapier auth test)."""
    _verify_api_key(authorization)
    return {"status": "OK", "version": OS_VERSION, "authenticated": True}


@router.post("/api/v1/ask")
async def api_v1_ask(request: Request, authorization: str = Header(default="")):
    """Legal question (API key required) — Zapier integration."""
    _verify_api_key(authorization)
    # Reuse main /ask logic
    if _ask_fn:
        return await _ask_fn(request)
    raise HTTPException(status_code=503, detail="ask handler not configured")


@router.get("/api/v1/search")
async def api_v1_search(q: str, limit: int = 10, authorization: str = Header(default="")):
    """Law search (API key required) — Zapier integration."""
    _verify_api_key(authorization)
    # Reuse main /search logic
    if _search_fn:
        return await _search_fn(q, limit)
    raise HTTPException(status_code=503, detail="search handler not configured")
