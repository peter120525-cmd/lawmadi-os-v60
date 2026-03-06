"""
Lawmadi OS v60 — Admin Dashboard API routes.
비즈니스 메트릭 조회 엔드포인트.
"""
import os
import logging
from typing import Any, Dict
from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from core.auth import verify_mcp_key as _verify_admin_auth

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger("LawmadiOS.Admin")
limiter = Limiter(key_func=get_remote_address)


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
