"""Verification stats, visitor stats, admin leader/category stats, frontend error/perf logging routes."""
import os
import json
import logging
import hashlib
from typing import Any, Dict
from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from slowapi import Limiter
from core.metrics import get_summary, get_endpoint_metrics, get_leader_metrics
from core.auth import verify_internal_key as _verify_internal_auth

router = APIRouter()
logger = logging.getLogger("LawmadiOS.Analytics")

limiter: Limiter = None  # type: ignore[assignment]
_get_client_ip_fn = None


def set_dependencies(rate_limiter, get_client_ip_fn):
    """Inject shared runtime objects from main.py at startup."""
    global limiter, _get_client_ip_fn
    if rate_limiter:
        limiter = rate_limiter
    _get_client_ip_fn = get_client_ip_fn


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
@limiter.limit("60/hour")
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


# =============================================================
# Frontend Error Tracking API (신규)
# =============================================================

@router.post("/api/errors")
@limiter.limit("30/hour")
async def report_frontend_error(request: Request):
    """
    프론트엔드 JS 에러 수집.
    Body: { message, source, lineno, colno, stack, url, userAgent }
    """
    try:
        body = await request.body()
        if len(body) > 16 * 1024:  # 16KB 제한
            return JSONResponse(status_code=413, content={"ok": False})

        data = json.loads(body)
        visitor_ip = _get_client_ip_fn(request) if _get_client_ip_fn else "unknown"
        visitor_hash = hashlib.sha256(visitor_ip.encode()).hexdigest()[:12]

        logger.warning(
            f"🌐 [Frontend Error] visitor={visitor_hash} | "
            f"msg={str(data.get('message', ''))[:200]} | "
            f"source={data.get('source', '')[:100]} | "
            f"line={data.get('lineno', '')}:{data.get('colno', '')} | "
            f"url={data.get('url', '')[:200]}"
        )

        # DB 저장 (fail-soft)
        db_client = _optional_import("connectors.db_client_v2")
        if db_client and hasattr(db_client, "save_frontend_error"):
            db_client.save_frontend_error(
                visitor_id=visitor_hash,
                message=str(data.get("message", ""))[:500],
                source=str(data.get("source", ""))[:200],
                lineno=data.get("lineno", 0),
                colno=data.get("colno", 0),
                stack=str(data.get("stack", ""))[:2000],
                url=str(data.get("url", ""))[:500],
                user_agent=str(data.get("userAgent", ""))[:300],
            )

        return {"ok": True}

    except Exception as e:
        logger.error(f"[API] /api/errors failed: {e}")
        return JSONResponse(status_code=500, content={"ok": False})


# =============================================================
# Frontend Performance Tracking API (신규)
# =============================================================

@router.post("/api/perf")
@limiter.limit("30/hour")
async def report_frontend_perf(request: Request):
    """
    프론트엔드 성능 메트릭 수집 (Core Web Vitals + 페이지 로드 시간).
    Body: { lcp, fid, cls, ttfb, domLoad, fullLoad, url, userAgent }
    """
    try:
        body = await request.body()
        if len(body) > 8 * 1024:
            return JSONResponse(status_code=413, content={"ok": False})

        data = json.loads(body)
        visitor_ip = _get_client_ip_fn(request) if _get_client_ip_fn else "unknown"
        visitor_hash = hashlib.sha256(visitor_ip.encode()).hexdigest()[:12]

        logger.info(
            f"📊 [Frontend Perf] visitor={visitor_hash} | "
            f"LCP={data.get('lcp', '-')}ms | "
            f"FID={data.get('fid', '-')}ms | "
            f"CLS={data.get('cls', '-')} | "
            f"TTFB={data.get('ttfb', '-')}ms | "
            f"domLoad={data.get('domLoad', '-')}ms | "
            f"fullLoad={data.get('fullLoad', '-')}ms | "
            f"url={data.get('url', '')[:200]}"
        )

        # DB 저장 (fail-soft)
        db_client = _optional_import("connectors.db_client_v2")
        if db_client and hasattr(db_client, "save_frontend_perf"):
            db_client.save_frontend_perf(
                visitor_id=visitor_hash,
                lcp_ms=data.get("lcp"),
                fid_ms=data.get("fid"),
                cls_score=data.get("cls"),
                ttfb_ms=data.get("ttfb"),
                dom_load_ms=data.get("domLoad"),
                full_load_ms=data.get("fullLoad"),
                url=str(data.get("url", ""))[:500],
                user_agent=str(data.get("userAgent", ""))[:300],
            )

        return {"ok": True}

    except Exception as e:
        logger.error(f"[API] /api/perf failed: {e}")
        return JSONResponse(status_code=500, content={"ok": False})


# =============================================================
# Admin System Logs API (신규)
# =============================================================

@router.get("/api/admin/system-metrics")
async def get_system_metrics_api(authorization: str = Header(default="")):
    """
    Admin API: 실시간 시스템 메트릭.
    - 응답 시간 백분위 (p50/p95/p99)
    - 캐시 적중률
    - 에러 분류
    - 리더별/엔드포인트별 메트릭
    - 라우팅 방식 분포
    - 파이프라인 스테이지별 지연
    """
    _verify_internal_auth(authorization)

    try:
        return {
            "ok": True,
            "summary": get_summary(),
            "endpoints": get_endpoint_metrics(),
            "leaders": get_leader_metrics(),
        }

    except Exception as e:
        logger.error(f"[API] /api/admin/system-metrics failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "시스템 메트릭 조회 실패"}
        )


@router.get("/api/admin/frontend-errors")
async def get_frontend_errors_api(
    limit: int = 50,
    authorization: str = Header(default="")
):
    """Admin API: 최근 프론트엔드 에러 목록."""
    _verify_internal_auth(authorization)

    try:
        db_client = _optional_import("connectors.db_client_v2")
        if db_client and hasattr(db_client, "get_frontend_errors"):
            return db_client.get_frontend_errors(limit)
        return {"ok": False, "error": "DB module not available"}

    except Exception as e:
        logger.error(f"[API] /api/admin/frontend-errors failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "프론트엔드 에러 조회 실패"}
        )


@router.get("/api/admin/frontend-perf")
async def get_frontend_perf_api(
    limit: int = 100,
    authorization: str = Header(default="")
):
    """Admin API: 프론트엔드 성능 메트릭 (Core Web Vitals)."""
    _verify_internal_auth(authorization)

    try:
        db_client = _optional_import("connectors.db_client_v2")
        if db_client and hasattr(db_client, "get_frontend_perf_stats"):
            return db_client.get_frontend_perf_stats(limit)
        return {"ok": False, "error": "DB module not available"}

    except Exception as e:
        logger.error(f"[API] /api/admin/frontend-perf failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "프론트엔드 성능 조회 실패"}
        )
