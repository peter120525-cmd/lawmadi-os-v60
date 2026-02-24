"""Verification stats, visitor stats, admin leader/category stats routes."""
import os
import hmac
import logging
from typing import Any, Dict
from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger("LawmadiOS.Analytics")

_INTERNAL_API_KEY = ""
_limiter = None
_get_client_ip_fn = None


def set_dependencies(limiter, get_client_ip_fn):
    """Inject shared runtime objects from main.py at startup."""
    global _limiter, _get_client_ip_fn, _INTERNAL_API_KEY
    _limiter = limiter
    _get_client_ip_fn = get_client_ip_fn
    _INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")


def _verify_internal_auth(authorization: str = Header(default="")) -> None:
    """Bearer token verification for internal endpoints."""
    if not _INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="INTERNAL_API_KEY not configured")
    token = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token, _INTERNAL_API_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _optional_import(module_path, attr=None):
    """Fail-soft optional import — returns None on failure."""
    try:
        from importlib import import_module
        module = import_module(module_path)
        return getattr(module, attr) if attr else module
    except Exception:
        return None


# =============================================================
# Verification Stats API
# =============================================================

@router.get("/api/verification/stats")
async def get_verification_stats(days: int = 7, authorization: str = Header(default="")):
    """
    Verification statistics (admin).
    - days: recent N days (default: 7)
    - Auth required.
    """
    _verify_internal_auth(authorization)

    try:
        db_client_v2 = _optional_import("connectors.db_client_v2")
        if not db_client_v2 or not hasattr(db_client_v2, "get_verification_statistics"):
            return JSONResponse(
                status_code=503,
                content={"ok": False, "error": "Verification system not available"}
            )

        stats = db_client_v2.get_verification_statistics(days=days)
        return stats

    except Exception as e:
        logger.error(f"[VerificationStats] Query failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "통계 조회 중 오류가 발생했습니다."}
        )


# =============================================================
# Visitor Stats API
# =============================================================

@router.post("/api/visit")
async def record_visitor(request: Request):
    """
    Record visitor — IP auto-extracted as visitor_id.
    Returns whether visitor is new.
    """
    try:
        # Use injected _get_client_ip_fn
        visitor_id = _get_client_ip_fn(request) if _get_client_ip_fn else "unknown"

        if not visitor_id or visitor_id == "unknown":
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": "Could not determine client IP"}
            )

        db_client = _optional_import("connectors.db_client_v2")
        if db_client and hasattr(db_client, "record_visit"):
            result = db_client.record_visit(visitor_id)
            return result
        else:
            return {"ok": False, "error": "DB module not available"}

    except Exception as e:
        logger.error(f"[API] /api/visit failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "방문 기록 처리 중 오류가 발생했습니다."}
        )


@router.get("/api/visitor-stats")
async def get_visitor_statistics(request: Request):
    """
    Visitor statistics API.
    - today_visitors, total_visitors, today_visits, total_visits
    """
    try:
        db_client = _optional_import("connectors.db_client_v2")
        if db_client and hasattr(db_client, "get_visitor_stats"):
            stats = db_client.get_visitor_stats()
            return stats
        else:
            # DB disabled — return defaults
            return {
                "ok": True,
                "today_visitors": 0,
                "total_visitors": 0,
                "today_visits": 0,
                "total_visits": 0,
                "note": "DB disabled"
            }

    except Exception as e:
        logger.error(f"[API] /api/visitor-stats failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "today_visitors": 0,
                "total_visitors": 0,
                "error": "통계 조회 중 오류가 발생했습니다."
            }
        )


# =============================================================
# Admin Leader / Category Stats
# =============================================================

@router.get("/api/admin/leader-stats")
async def get_leader_stats_api(days: int = 30, authorization: str = Header(default="")):
    """
    Admin API: per-leader statistics.
    - days: recent N days (default 30)
    """
    _verify_internal_auth(authorization)

    try:
        db_client = _optional_import("connectors.db_client_v2")
        if db_client and hasattr(db_client, "get_leader_statistics"):
            stats = db_client.get_leader_statistics(days)
            return stats
        else:
            return {"ok": False, "error": "DB module not available"}

    except Exception as e:
        logger.error(f"[API] /api/admin/leader-stats failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "리더 통계 조회 중 오류가 발생했습니다."}
        )


@router.get("/api/admin/category-stats")
async def get_category_stats_api(days: int = 30, authorization: str = Header(default="")):
    """
    Admin API: query category statistics.
    - days: recent N days (default 30)
    """
    _verify_internal_auth(authorization)

    try:
        db_client = _optional_import("connectors.db_client_v2")
        if db_client and hasattr(db_client, "get_query_category_statistics"):
            stats = db_client.get_query_category_statistics(days)
            return stats
        else:
            return {"ok": False, "error": "DB module not available"}

    except Exception as e:
        logger.error(f"[API] /api/admin/category-stats failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "카테고리 통계 조회 중 오류가 발생했습니다."}
        )


@router.get("/api/admin/leader-queries/{leader_code}")
async def get_leader_queries_api(
    leader_code: str,
    limit: int = 10,
    authorization: str = Header(default="")
):
    """
    Admin API: sample queries received by a specific leader.
    - leader_code: leader code (e.g. "L08")
    - limit: max count (default 10)
    """
    _verify_internal_auth(authorization)

    try:
        db_client = _optional_import("connectors.db_client_v2")
        if db_client and hasattr(db_client, "get_leader_query_samples"):
            samples = db_client.get_leader_query_samples(leader_code, limit)
            return samples
        else:
            return {"ok": False, "error": "DB module not available"}

    except Exception as e:
        logger.error(f"[API] /api/admin/leader-queries failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "리더 질문 조회 중 오류가 발생했습니다."}
        )
