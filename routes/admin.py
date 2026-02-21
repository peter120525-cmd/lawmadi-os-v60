"""
Lawmadi OS v60 — Admin Dashboard API routes.
비즈니스 메트릭 조회 엔드포인트.
"""
import os
import logging
from typing import Any, Dict
from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger("LawmadiOS.Admin")


def _verify_admin_auth(authorization: str = Header(default="")) -> None:
    """Admin API 인증 — MCP_API_KEY 사용"""
    api_key = os.getenv("MCP_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=403, detail="MCP_API_KEY not configured")
    token = authorization.removeprefix("Bearer ").strip()
    if token != api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _optional_import(module_path, attr=None):
    try:
        from importlib import import_module
        module = import_module(module_path)
        return getattr(module, attr) if attr else module
    except Exception:
        return None


@router.get("/dashboard")
async def admin_dashboard(days: int = Query(default=7, ge=1, le=90), authorization: str = Header(default="")):
    """대시보드 메트릭: DAU, 쿼리 수, 평균 latency, 에러율, 상위 법률 카테고리"""
    _verify_admin_auth(authorization)
    try:
        db = _optional_import("connectors.db_client_v2")
        if not db or not hasattr(db, "get_dashboard_metrics"):
            return JSONResponse(status_code=503, content={"ok": False, "error": "Dashboard metrics not available"})
        return db.get_dashboard_metrics(days=days)
    except Exception as e:
        logger.error(f"[Admin] dashboard error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/conversion")
async def admin_conversion(days: int = Query(default=30, ge=1, le=365), authorization: str = Header(default="")):
    """전환 메트릭: 총 쿼리 수, 변호사 문의 수, 피드백 수, 전환율"""
    _verify_admin_auth(authorization)
    try:
        db = _optional_import("connectors.db_client_v2")
        if not db or not hasattr(db, "get_conversion_metrics"):
            return JSONResponse(status_code=503, content={"ok": False, "error": "Conversion metrics not available"})
        return db.get_conversion_metrics(days=days)
    except Exception as e:
        logger.error(f"[Admin] conversion error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/retention")
async def admin_retention(authorization: str = Header(default="")):
    """리텐션 메트릭: 재방문율, 평균 방문 횟수, 사용자 분포"""
    _verify_admin_auth(authorization)
    try:
        db = _optional_import("connectors.db_client_v2")
        if not db or not hasattr(db, "get_retention_metrics"):
            return JSONResponse(status_code=503, content={"ok": False, "error": "Retention metrics not available"})
        return db.get_retention_metrics()
    except Exception as e:
        logger.error(f"[Admin] retention error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/cost-estimate")
async def admin_cost_estimate(days: int = Query(default=7, ge=1, le=90), authorization: str = Header(default="")):
    """비용 추정: Gemini/Claude API 호출 수, 추정 비용"""
    _verify_admin_auth(authorization)
    try:
        db = _optional_import("connectors.db_client_v2")
        if not db or not hasattr(db, "get_cost_estimate"):
            return JSONResponse(status_code=503, content={"ok": False, "error": "Cost estimate not available"})
        return db.get_cost_estimate(days=days)
    except Exception as e:
        logger.error(f"[Admin] cost-estimate error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/feedback-summary")
async def admin_feedback_summary(days: int = Query(default=30, ge=1, le=365), authorization: str = Header(default="")):
    """피드백 요약: 총 피드백, 긍정/부정 비율, 리더별 분포"""
    _verify_admin_auth(authorization)
    try:
        db = _optional_import("connectors.db_client_v2")
        if not db or not hasattr(db, "get_feedback_summary"):
            return JSONResponse(status_code=503, content={"ok": False, "error": "Feedback summary not available"})
        return db.get_feedback_summary(days=days)
    except Exception as e:
        logger.error(f"[Admin] feedback-summary error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
