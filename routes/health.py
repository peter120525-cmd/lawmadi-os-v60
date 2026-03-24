"""Health, metrics, diagnostics routes."""
import os
import sys
import logging
from typing import Any, Dict
from fastapi import APIRouter, Header, HTTPException
from core.constants import OS_VERSION, GEMINI_MODEL, LAWMADILM_API_URL
from core.model_fallback import get_model, get_status as get_model_status
from core.metrics import get_summary as get_enhanced_metrics
from core.auth import verify_internal_key as _verify_internal_auth, verify_jwt_token, extract_bearer_token
from utils.helpers import _now_iso

router = APIRouter()
logger = logging.getLogger("LawmadiOS.Health")

_RUNTIME: Dict[str, Any] = {}
_METRICS: Dict[str, Any] = {}
_LAW_CACHE: Dict[str, Any] = {}
_KEYWORD_INDEX: Dict[str, list] = {}
_db_client = None


def set_dependencies(runtime, metrics, law_cache=None, keyword_index=None, db_client=None):
    """Inject shared runtime objects from main.py at startup."""
    global _RUNTIME, _METRICS, _LAW_CACHE, _KEYWORD_INDEX, _db_client
    _RUNTIME = runtime
    _METRICS = metrics
    _LAW_CACHE = law_cache or {}
    _KEYWORD_INDEX = keyword_index or {}
    _db_client = db_client


def _diagnostic_snapshot() -> Dict[str, Any]:
    """System diagnostic snapshot — modules, metrics, versions."""
    return {
        "timestamp": _now_iso(),
        "python": sys.version,
        "pid": os.getpid(),
        "os_version": OS_VERSION,
        "gemini_model": get_model(),
        "model_fallback": get_model_status(),
        "modules": {
            "drf": bool(_RUNTIME.get("drf")),
            "selector": bool(_RUNTIME.get("selector")),
            "guard": bool(_RUNTIME.get("guard")),
            "search_service": bool(_RUNTIME.get("search_service")),
            "swarm_orchestrator": bool(_RUNTIME.get("swarm_orchestrator")),
            "clevel_handler": bool(_RUNTIME.get("clevel_handler")),
            "genai_client": bool(_RUNTIME.get("genai_client")),
            "lawmadilm_api": bool(LAWMADILM_API_URL),
            "tier_router": "active" if _RUNTIME.get("genai_client") else "fallback_keyword",
            "law_cache": f"{len(_LAW_CACHE)} types, {len(_KEYWORD_INDEX)} keywords" if _LAW_CACHE else "not_loaded",
            "db_client": bool(_db_client),
            "gemini_key": bool(os.getenv("GEMINI_KEY")),
        },
        "metrics": _METRICS,
        "enhanced_metrics": get_enhanced_metrics(),
    }


@router.get("/ping")
async def ping():
    """Lightweight ping for mcp-proxy and load balancers."""
    return {"status": "ok"}


@router.get("/health")
async def health():
    """Health check endpoint — minimal info only (diagnostics require auth)."""
    return {
        "status": "online",
        "os_version": OS_VERSION,
    }


def _verify_admin_auth(authorization: str) -> None:
    """Dual auth: JWT (role=admin) 우선, 실패 시 API key fallback."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    try:
        token = extract_bearer_token(authorization)
        payload = verify_jwt_token(token)
        if payload.get("role") == "admin":
            return
        raise HTTPException(status_code=403, detail="Admin role required")
    except HTTPException:
        # JWT 실패 → INTERNAL_API_KEY fallback (CI/CD 호환)
        _verify_internal_auth(authorization)


@router.get("/metrics")
async def metrics(authorization: str = Header(default="")):
    """Runtime metrics (admin auth required)."""
    _verify_admin_auth(authorization)
    return _METRICS


@router.get("/diagnostics")
async def diagnostics(authorization: str = Header(default="")):
    """Full diagnostic snapshot (admin auth required)."""
    _verify_admin_auth(authorization)
    return _diagnostic_snapshot()
