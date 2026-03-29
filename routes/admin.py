"""
Lawmadi OS v60 — Admin Dashboard API routes.
비즈니스 메트릭 조회 + Paddle 관리 엔드포인트.
"""
import os
import time
import hashlib
import logging
import re
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


@router.get("/chat-usage")
@limiter.limit("10/minute")
async def admin_chat_usage(
    request: Request,
    days: int = Query(default=7, ge=1, le=90),
    leader: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    query_type: Optional[str] = Query(default=None),
    exclude_admin: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    authorization: str = Header(default=""),
):
    """채팅 이용 로그 조회: 리더별/상태별/일자별 필터 + 사용자 통계 + 시간대별 분포 + 관리자 제외"""
    _verify_admin_auth(authorization)
    try:
        db = _optional_import("connectors.db_client_v2")
        if not db or not hasattr(db, "get_chat_usage_logs"):
            return JSONResponse(status_code=503, content={"ok": False, "error": "Chat usage logs not available"})
        return db.get_chat_usage_logs(
            days=days, leader=leader, status=status,
            query_type=query_type, limit=limit, offset=offset,
            exclude_admin=exclude_admin,
        )
    except Exception as e:
        logger.error(f"[Admin] chat-usage error: {e}")
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
    """수동 블랙리스트 추가. body: {"ip": "1.2.3.4", "duration": 3600, "reason": "..."}"""
    _verify_admin_auth(authorization)
    add_fn = _blacklist_fns.get("add_to_blacklist")
    if not add_fn:
        return JSONResponse(status_code=503, content={"ok": False, "error": "Blacklist not available"})
    body = await request.json()
    ip = body.get("ip", "").strip()
    duration = int(body.get("duration", 3600))
    reason = body.get("reason", "manual")
    if not ip:
        return JSONResponse(status_code=400, content={"ok": False, "error": "ip required"})
    add_fn(ip, duration, reason)
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:12]
    return {"ok": True, "ip_hash": ip_hash, "duration": duration}


# ─── Paddle 관리 API ───

_TXN_ID_RE = re.compile(r'^txn_[a-zA-Z0-9]+$')
_CTM_ID_RE = re.compile(r'^ctm_[a-zA-Z0-9]+$')


@router.get("/paddle/transactions")
@limiter.limit("10/minute")
async def admin_paddle_transactions(
    request: Request,
    status: str = Query(default=None, regex="^(completed|billed|past_due|canceled|draft)$"),
    customer_id: str = Query(default=None),
    per_page: int = Query(default=25, ge=1, le=100),
    after: str = Query(default=None),
    authorization: str = Header(default=""),
):
    """Paddle 거래 목록 조회."""
    _verify_admin_auth(authorization)
    if customer_id and not _CTM_ID_RE.match(customer_id):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid customer_id format"})

    from routes.paddle import list_paddle_transactions
    result = await list_paddle_transactions(
        status=status, after=after, per_page=per_page,
        customer_id=customer_id, order_by="created_at[DESC]",
    )
    if "data" in result:
        return {"ok": True, "data": result["data"], "meta": result.get("meta", {})}
    return JSONResponse(status_code=502, content={"ok": False, "error": result.get("error", "Paddle API error")})


@router.get("/paddle/transactions/{transaction_id}")
@limiter.limit("10/minute")
async def admin_paddle_transaction_detail(
    request: Request, transaction_id: str, authorization: str = Header(default=""),
):
    """Paddle 거래 상세 조회."""
    _verify_admin_auth(authorization)
    if not _TXN_ID_RE.match(transaction_id):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid transaction_id format"})

    from routes.paddle import get_paddle_transaction
    result = await get_paddle_transaction(transaction_id)
    if "data" in result:
        return {"ok": True, "data": result["data"]}
    return JSONResponse(status_code=502, content={"ok": False, "error": result.get("error", "Paddle API error")})


@router.get("/paddle/customers")
@limiter.limit("10/minute")
async def admin_paddle_customers(
    request: Request,
    email: str = Query(default=None),
    per_page: int = Query(default=25, ge=1, le=100),
    after: str = Query(default=None),
    authorization: str = Header(default=""),
):
    """Paddle 고객 목록 조회."""
    _verify_admin_auth(authorization)
    from routes.paddle import list_paddle_customers
    result = await list_paddle_customers(after=after, per_page=per_page, email=email)
    if "data" in result:
        return {"ok": True, "data": result["data"], "meta": result.get("meta", {})}
    return JSONResponse(status_code=502, content={"ok": False, "error": result.get("error", "Paddle API error")})


@router.get("/paddle/customers/{customer_id}")
@limiter.limit("10/minute")
async def admin_paddle_customer_detail(
    request: Request, customer_id: str, authorization: str = Header(default=""),
):
    """Paddle 고객 상세 조회."""
    _verify_admin_auth(authorization)
    if not _CTM_ID_RE.match(customer_id):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid customer_id format"})

    from routes.paddle import get_paddle_customer
    result = await get_paddle_customer(customer_id)
    if "data" in result:
        return {"ok": True, "data": result["data"]}
    return JSONResponse(status_code=502, content={"ok": False, "error": result.get("error", "Paddle API error")})


@router.post("/paddle/refund")
@limiter.limit("5/minute")
async def admin_paddle_refund(
    request: Request, authorization: str = Header(default=""),
):
    """Paddle 환불(Adjustment) 처리.
    body: {"transaction_id": "txn_...", "reason": "사유", "action": "refund"|"credit"}
    """
    _verify_admin_auth(authorization)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON"})

    txn_id = str(body.get("transaction_id", "")).strip()
    reason = str(body.get("reason", "")).strip()
    action = str(body.get("action", "refund")).strip()

    if not txn_id or not _TXN_ID_RE.match(txn_id):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Valid transaction_id required (txn_...)"})
    if not reason or len(reason) > 500:
        return JSONResponse(status_code=400, content={"ok": False, "error": "reason required (max 500 chars)"})
    if action not in ("refund", "credit"):
        return JSONResponse(status_code=400, content={"ok": False, "error": "action must be 'refund' or 'credit'"})

    from routes.paddle import create_paddle_adjustment, revoke_credits_for_refund
    result = await create_paddle_adjustment(
        transaction_id=txn_id, reason=reason, action=action,
    )

    if "data" in result:
        # 환불 성공 시 DB에서 크레딧 차감
        adjustment_data = result["data"]
        await revoke_credits_for_refund(txn_id)
        logger.info(f"[Admin] Refund created: txn={txn_id}, action={action}")
        return {"ok": True, "data": adjustment_data}
    logger.warning(f"[Admin] Refund failed: txn={txn_id}, error={result.get('error')}")
    return JSONResponse(status_code=502, content={"ok": False, "error": result.get("error", "Paddle API error")})


@router.get("/paddle/adjustments")
@limiter.limit("10/minute")
async def admin_paddle_adjustments(
    request: Request,
    transaction_id: str = Query(default=None),
    per_page: int = Query(default=25, ge=1, le=100),
    after: str = Query(default=None),
    authorization: str = Header(default=""),
):
    """Paddle 환불/조정 내역 조회."""
    _verify_admin_auth(authorization)
    if transaction_id and not _TXN_ID_RE.match(transaction_id):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid transaction_id format"})

    from routes.paddle import list_paddle_adjustments
    result = await list_paddle_adjustments(
        transaction_id=transaction_id, after=after, per_page=per_page,
    )
    if "data" in result:
        return {"ok": True, "data": result["data"], "meta": result.get("meta", {})}
    return JSONResponse(status_code=502, content={"ok": False, "error": result.get("error", "Paddle API error")})


@router.get("/paddle/revenue")
@limiter.limit("10/minute")
async def admin_paddle_revenue(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    authorization: str = Header(default=""),
):
    """매출 통계: credit_ledger 기반 구매/차감/환불 요약."""
    _verify_admin_auth(authorization)
    db = _optional_import("connectors.db_client_v2")
    if not db:
        return JSONResponse(status_code=503, content={"ok": False, "error": "DB not available"})

    try:
        from connectors.db_client import _db_enabled, get_connection, release_connection
        if not _db_enabled():
            return JSONResponse(status_code=503, content={"ok": False, "error": "DB disabled"})

        conn = get_connection()
        if not conn:
            return JSONResponse(status_code=503, content={"ok": False, "error": "DB connection failed"})
        try:
            cur = conn.cursor()
            # 기간별 구매/차감/환불 집계
            cur.execute("""
                SELECT type,
                       COUNT(*) as cnt,
                       COALESCE(SUM(amount), 0) as total_amount
                FROM credit_ledger
                WHERE created_at >= NOW() - %s * INTERVAL '1 day'
                GROUP BY type
                ORDER BY type
            """, (days,))
            rows = cur.fetchall()
            summary = {}
            for r in rows:
                summary[r[0]] = {"count": r[1], "total_credits": r[2]}

            # 일별 구매 크레딧 추이
            cur.execute("""
                SELECT DATE(created_at AT TIME ZONE 'Asia/Seoul') as dt,
                       COALESCE(SUM(amount), 0) as daily_credits,
                       COUNT(*) as daily_txns
                FROM credit_ledger
                WHERE type = 'purchase'
                  AND created_at >= NOW() - %s * INTERVAL '1 day'
                GROUP BY dt
                ORDER BY dt DESC
                LIMIT 60
            """, (days,))
            daily = [{"date": str(r[0]), "credits": r[1], "transactions": r[2]} for r in cur.fetchall()]

            # 활성 유료 사용자 수
            cur.execute("SELECT COUNT(*) FROM users WHERE credit_balance > 0")
            paying_users = cur.fetchone()[0]

            # 총 사용자 수
            cur.execute("SELECT COUNT(*) FROM users")
            total_users = cur.fetchone()[0]

            cur.close()
            return {
                "ok": True,
                "days": days,
                "summary": summary,
                "daily_purchases": daily,
                "paying_users": paying_users,
                "total_users": total_users,
            }
        finally:
            release_connection(conn)
    except Exception as e:
        logger.error(f"[Admin] Revenue query failed: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": "Revenue query failed"})


@router.get("/paddle/users")
@limiter.limit("10/minute")
async def admin_paddle_users(
    request: Request,
    email: str = Query(default=None),
    plan: str = Query(default=None, regex="^(free|premium)$"),
    limit: int = Query(default=50, ge=1, le=200),
    authorization: str = Header(default=""),
):
    """내부 사용자 목록 조회 (users 테이블)."""
    _verify_admin_auth(authorization)
    try:
        from connectors.db_client import _db_enabled, get_connection, release_connection
        if not _db_enabled():
            return JSONResponse(status_code=503, content={"ok": False, "error": "DB disabled"})

        conn = get_connection()
        if not conn:
            return JSONResponse(status_code=503, content={"ok": False, "error": "DB connection failed"})
        try:
            cur = conn.cursor()
            where_clauses = []
            params = []

            if email:
                where_clauses.append("email ILIKE %s")
                params.append(f"%{email}%")
            if plan:
                where_clauses.append("current_plan = %s")
                params.append(plan)

            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            params.append(limit)

            cur.execute(f"""
                SELECT user_id, email, current_plan, credit_balance, daily_free_used,
                       paddle_customer_id, created_at, last_login_at
                FROM users {where_sql}
                ORDER BY created_at DESC
                LIMIT %s
            """, tuple(params))
            rows = cur.fetchall()
            cur.close()

            users = []
            for r in rows:
                users.append({
                    "user_id": str(r[0])[:8] + "...",
                    "email": r[1],
                    "plan": r[2],
                    "credits": r[3],
                    "daily_free_used": r[4],
                    "paddle_customer_id": r[5] or "",
                    "created_at": r[6].isoformat() if r[6] else "",
                    "last_login_at": r[7].isoformat() if r[7] else "",
                })
            return {"ok": True, "count": len(users), "users": users}
        finally:
            release_connection(conn)
    except Exception as e:
        logger.error(f"[Admin] Users query failed: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": "Users query failed"})


