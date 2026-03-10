"""
Lawmadi OS v60 — Admin Dashboard API routes.
비즈니스 메트릭 조회 엔드포인트.
"""
import os
import time
import hashlib
import logging
from typing import Any, Callable, Dict, Optional
from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from core.auth import verify_mcp_key as _verify_admin_auth

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger("LawmadiOS.Admin")
limiter = Limiter(key_func=get_remote_address)

# main.py에서 주입되는 블랙리스트 함수 참조
_blacklist_fns: Dict[str, Optional[Callable]] = {
    "get_blacklist": None,
    "remove_from_blacklist": None,
    "add_to_blacklist": None,
}

def set_blacklist_fns(get_fn, remove_fn, add_fn):
    _blacklist_fns["get_blacklist"] = get_fn
    _blacklist_fns["remove_from_blacklist"] = remove_fn
    _blacklist_fns["add_to_blacklist"] = add_fn


def _optional_import(module_path, attr=None):
    try:
        from importlib import import_module
        module = import_module(module_path)
        return getattr(module, attr) if attr else module
    except Exception:
        return None


@router.get("/dashboard")
@limiter.limit("10/minute")
async def admin_dashboard(request: Request, days: int = Query(default=7, ge=1, le=90), authorization: str = Header(default="")):
    """대시보드 메트릭: DAU, 쿼리 수, 평균 latency, 에러율, 상위 법률 카테고리"""
    _verify_admin_auth(authorization)
    try:
        db = _optional_import("connectors.db_client_v2")
        if not db or not hasattr(db, "get_dashboard_metrics"):
            return JSONResponse(status_code=503, content={"ok": False, "error": "Dashboard metrics not available"})
        return db.get_dashboard_metrics(days=days)
    except Exception as e:
        logger.error(f"[Admin] dashboard error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": "내부 서버 오류가 발생했습니다."})


@router.get("/conversion")
@limiter.limit("10/minute")
async def admin_conversion(request: Request, days: int = Query(default=30, ge=1, le=90), authorization: str = Header(default="")):
    """전환 메트릭: 총 쿼리 수, 변호사 문의 수, 피드백 수, 전환율"""
    _verify_admin_auth(authorization)
    try:
        db = _optional_import("connectors.db_client_v2")
        if not db or not hasattr(db, "get_conversion_metrics"):
            return JSONResponse(status_code=503, content={"ok": False, "error": "Conversion metrics not available"})
        return db.get_conversion_metrics(days=days)
    except Exception as e:
        logger.error(f"[Admin] conversion error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": "내부 서버 오류가 발생했습니다."})


@router.get("/retention")
@limiter.limit("10/minute")
async def admin_retention(request: Request, authorization: str = Header(default="")):
    """리텐션 메트릭: 재방문율, 평균 방문 횟수, 사용자 분포"""
    _verify_admin_auth(authorization)
    try:
        db = _optional_import("connectors.db_client_v2")
        if not db or not hasattr(db, "get_retention_metrics"):
            return JSONResponse(status_code=503, content={"ok": False, "error": "Retention metrics not available"})
        return db.get_retention_metrics()
    except Exception as e:
        logger.error(f"[Admin] retention error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": "내부 서버 오류가 발생했습니다."})


@router.get("/cost-estimate")
@limiter.limit("10/minute")
async def admin_cost_estimate(request: Request, days: int = Query(default=7, ge=1, le=90), authorization: str = Header(default="")):
    """비용 추정: Gemini/Claude API 호출 수, 추정 비용"""
    _verify_admin_auth(authorization)
    try:
        db = _optional_import("connectors.db_client_v2")
        if not db or not hasattr(db, "get_cost_estimate"):
            return JSONResponse(status_code=503, content={"ok": False, "error": "Cost estimate not available"})
        return db.get_cost_estimate(days=days)
    except Exception as e:
        logger.error(f"[Admin] cost-estimate error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": "내부 서버 오류가 발생했습니다."})


@router.get("/feedback-summary")
@limiter.limit("10/minute")
async def admin_feedback_summary(request: Request, days: int = Query(default=30, ge=1, le=90), authorization: str = Header(default="")):
    """피드백 요약: 총 피드백, 긍정/부정 비율, 리더별 분포"""
    _verify_admin_auth(authorization)
    try:
        db = _optional_import("connectors.db_client_v2")
        if not db or not hasattr(db, "get_feedback_summary"):
            return JSONResponse(status_code=503, content={"ok": False, "error": "Feedback summary not available"})
        return db.get_feedback_summary(days=days)
    except Exception as e:
        logger.error(f"[Admin] feedback-summary error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": "내부 서버 오류가 발생했습니다."})


@router.get("/blacklist")
@limiter.limit("10/minute")
async def admin_blacklist(request: Request, authorization: str = Header(default="")):
    """현재 블랙리스트 목록 조회 (IP 해시, 만료 시각)."""
    _verify_admin_auth(authorization)
    get_fn = _blacklist_fns.get("get_blacklist")
    if not get_fn:
        return JSONResponse(status_code=503, content={"ok": False, "error": "Blacklist not available"})
    entries = get_fn()
    return {"ok": True, "count": len(entries), "entries": entries}


@router.delete("/blacklist/{ip_hash}")
@limiter.limit("10/minute")
async def admin_blacklist_remove(request: Request, ip_hash: str, authorization: str = Header(default="")):
    """블랙리스트에서 IP 해제 (SHA-256 해시 12자리 prefix)."""
    _verify_admin_auth(authorization)
    remove_fn = _blacklist_fns.get("remove_from_blacklist")
    if not remove_fn:
        return JSONResponse(status_code=503, content={"ok": False, "error": "Blacklist not available"})
    removed = remove_fn(ip_hash)
    return {"ok": True, "removed": removed}


@router.post("/blacklist")
@limiter.limit("10/minute")
async def admin_blacklist_add(request: Request, authorization: str = Header(default="")):
    """수동 블랙리스트 추가. body: {"ip": "1.2.3.4", "duration": 3600}"""
    _verify_admin_auth(authorization)
    add_fn = _blacklist_fns.get("add_to_blacklist")
    if not add_fn:
        return JSONResponse(status_code=503, content={"ok": False, "error": "Blacklist not available"})
    body = await request.json()
    ip = body.get("ip", "").strip()
    duration = int(body.get("duration", 3600))
    if not ip:
        return JSONResponse(status_code=400, content={"ok": False, "error": "ip required"})
    add_fn(ip, duration)
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:12]
    return {"ok": True, "ip_hash": ip_hash, "duration": duration}
