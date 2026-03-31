"""
Lawmadi OS v60 -- Paddle Billing + Email OTP (no signup).

Refactored v2: users table (UUID) + DB sessions (30d) + credit_ledger (balance_after).

Flow:
  1. User enters email on pricing page
  2. Backend sends 6-digit OTP via SMTP (hashed storage)
  3. User verifies OTP -> DB session token issued (30 days)
  4. Paddle Checkout opens with verified email
  5. Paddle webhook credits the user account (idempotent)
  6. On /ask, session cookie -> backend checks credits
  7. Post-deduction: credits deducted after successful response
"""
import os
import hmac
import hashlib
import json
import secrets
import time
import logging
import re
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter

logger = logging.getLogger("LawmadiOS.Paddle")
router = APIRouter(prefix="/api/paddle", tags=["paddle"])


def _get_real_ip(request: Request) -> str:
    """Extract real client IP from X-Forwarded-For (Cloud Run LB appends last)."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        ip = xff.split(",")[-1].strip()
        if ip:
            return ip
    return request.client.host if request.client else "0.0.0.0"


# paddle.py owns the Limiter — main.py uses this as app.state.limiter
limiter = Limiter(key_func=_get_real_ip)

# ─── Config ───
PADDLE_WEBHOOK_SECRET = os.getenv("PADDLE_WEBHOOK_SECRET", "").strip()
PADDLE_API_KEY = os.getenv("PADDLE_API_KEY", "").strip()
PADDLE_CLIENT_TOKEN = os.getenv("PADDLE_CLIENT_TOKEN", "").strip()
PADDLE_ENVIRONMENT = os.getenv("PADDLE_ENVIRONMENT", "sandbox")
try:
    DAILY_FREE_LIMIT = int(os.getenv("DAILY_FREE_LIMIT", "2"))
except ValueError:
    DAILY_FREE_LIMIT = 2
try:
    SESSION_EXPIRY_DAYS = int(os.getenv("SESSION_EXPIRY_DAYS", "30"))
except ValueError:
    SESSION_EXPIRY_DAYS = 30

# OTP config
_OTP_TTL_SEC = 300  # 5 minutes
_OTP_LENGTH = 6
_MAX_OTP_ATTEMPTS = 5

# In-memory OTP fallback (when DB unavailable)
_otp_store: Dict[str, Dict] = {}
_MAX_OTP_ENTRIES = 1000

# Credit pack definitions
CREDIT_PACKS = {
    "starter":  {"credits": 20,  "price_krw": 2100, "price_usd": 1.50},
    "standard": {"credits": 100, "price_krw": 7000, "price_usd": 4.99},
    "pro":      {"credits": 300, "price_krw": 13800, "price_usd": 9.99},
}

# Paddle Production price IDs (KRW + USD)
_PRICE_IDS = {
    "ko": {
        "starter":  os.getenv("PADDLE_PRICE_STARTER_KR",  "pri_01kkdd7fe430168kvyp8gm483x"),
        "standard": os.getenv("PADDLE_PRICE_STANDARD_KR", "pri_01kkdd7jgr306g90svgx5mnpp0"),
        "pro":      os.getenv("PADDLE_PRICE_PRO_KR",      "pri_01kkdd7mvtf1qtzxtdjkfs88fb"),
    },
    "en": {
        "starter":  os.getenv("PADDLE_PRICE_STARTER_EN",  "pri_01kkdd7qb8akd2h5yrwdrr2a5r"),
        "standard": os.getenv("PADDLE_PRICE_STANDARD_EN", "pri_01kkdd7sr5e5xhj067sxt09xem"),
        "pro":      os.getenv("PADDLE_PRICE_PRO_EN",      "pri_01kkdd7vwx7bs5m5t81yzz4qb4"),
    },
}

# Paddle price_id -> pack reverse mapping
_PRICE_TO_PACK = {}
for _lang_prices in _PRICE_IDS.values():
    for _pack_name, _price_id in _lang_prices.items():
        _PRICE_TO_PACK[_price_id] = _pack_name
_raw_mapping = os.getenv("PADDLE_PRICE_PACK_MAP", "")
if _raw_mapping:
    for pair in _raw_mapping.split(","):
        parts = pair.strip().split("=")
        if len(parts) == 2:
            _PRICE_TO_PACK[parts[0].strip()] = parts[1].strip()


# ─── Helpers ───

def _validate_email(email: str) -> bool:
    """Email format validation with CRLF injection defense."""
    if not email or '\r' in email or '\n' in email or len(email) > 254:
        return False
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))


_OTP_HMAC_SECRET = os.getenv("OTP_HMAC_SECRET", "").strip()
_OTP_DISABLED = False
if not _OTP_HMAC_SECRET:
    if PADDLE_ENVIRONMENT == "production":
        logger.error("❌ OTP_HMAC_SECRET 미설정 — production에서 OTP 비활성화 (보안 fail-closed)")
        _OTP_DISABLED = True
        _OTP_HMAC_SECRET = "disabled"
    else:
        logger.warning("⚠️ OTP_HMAC_SECRET 미설정 — sandbox fallback 사용")
        _OTP_HMAC_SECRET = "lawmadi-sandbox-only-hmac-key"


def _hash_otp(code: str, email: str = "") -> str:
    """Hash OTP code with HMAC-SHA256 using server-side secret key.
    email is included in the message (not the key) to bind OTP to specific email."""
    msg = f"{email}:{code}".encode()
    return hmac.new(_OTP_HMAC_SECRET.encode(), msg, hashlib.sha256).hexdigest()


def _cleanup_otp_store():
    """Remove expired entries from in-memory OTP store."""
    now = time.time()
    expired = [k for k, v in _otp_store.items() if v["expires"] < now]
    for k in expired:
        del _otp_store[k]
    while len(_otp_store) > _MAX_OTP_ENTRIES:
        oldest = min(_otp_store, key=lambda k: _otp_store[k]["expires"])
        del _otp_store[oldest]


# ─── User Management (users table) ───

def _get_or_create_user(email: str, conn=None, cur=None) -> Optional[dict]:
    """Get existing user or auto-create. Returns dict with user_id, email, etc."""
    owns_conn = conn is None
    try:
        if owns_conn:
            from connectors.db_client import get_connection, release_connection
            conn = get_connection()
            if conn is None:
                return None
            cur = conn.cursor()

        cur.execute("SELECT user_id, email, current_plan, credit_balance, daily_free_used, daily_free_reset_at, paddle_customer_id FROM users WHERE email = %s", (email,))
        row = cur.fetchone()
        if row:
            return {
                "user_id": str(row[0]), "email": row[1], "current_plan": row[2],
                "credit_balance": row[3], "daily_free_used": row[4],
                "daily_free_reset_at": row[5], "paddle_customer_id": row[6],
            }

        # Auto-create user (no signup form needed)
        user_id = str(uuid.uuid4())
        cur.execute(
            """INSERT INTO users (user_id, email, current_plan, credit_balance, daily_free_used)
               VALUES (%s, %s, 'free', 0, 0)
               ON CONFLICT (email) DO NOTHING
               RETURNING user_id, email, current_plan, credit_balance, daily_free_used, daily_free_reset_at, paddle_customer_id""",
            (user_id, email)
        )
        row = cur.fetchone()
        if row:
            conn.commit()
            return {
                "user_id": str(row[0]), "email": row[1], "current_plan": row[2],
                "credit_balance": row[3], "daily_free_used": row[4],
                "daily_free_reset_at": row[5], "paddle_customer_id": row[6],
            }
        conn.commit()
        # Race condition: another process inserted first, re-fetch
        cur.execute("SELECT user_id, email, current_plan, credit_balance, daily_free_used, daily_free_reset_at, paddle_customer_id FROM users WHERE email = %s", (email,))
        row = cur.fetchone()
        if row:
            return {
                "user_id": str(row[0]), "email": row[1], "current_plan": row[2],
                "credit_balance": row[3], "daily_free_used": row[4],
                "daily_free_reset_at": row[5], "paddle_customer_id": row[6],
            }
        return None
    except Exception as e:
        logger.error(f"[User] get_or_create failed: {e}")
        return None
    finally:
        if owns_conn and conn:
            if cur:
                cur.close()
            from connectors.db_client import release_connection
            release_connection(conn)


def get_user_by_id(user_id: str) -> Optional[dict]:
    """Fetch user by user_id."""
    try:
        from connectors.db_client_v2 import execute
        result = execute(
            "SELECT user_id, email, current_plan, credit_balance, daily_free_used, daily_free_reset_at, paddle_customer_id FROM users WHERE user_id = %s",
            (user_id,), fetch="one"
        )
        if result.get("ok") and result.get("data"):
            row = result["data"]
            return {
                "user_id": str(row[0]), "email": row[1], "current_plan": row[2],
                "credit_balance": row[3], "daily_free_used": row[4],
                "daily_free_reset_at": row[5], "paddle_customer_id": row[6],
            }
    except Exception as e:
        logger.warning(f"[User] get_by_id failed: {e}")
    return None


# ─── DB Session Management ───

_MAX_SESSIONS_PER_USER = 5

def _create_db_session(user_id: str) -> str:
    """Create DB session token (secure random, 30-day TTL). Returns token."""
    token = secrets.token_hex(32)  # 64-char hex string
    expires_days = SESSION_EXPIRY_DAYS
    try:
        from connectors.db_client_v2 import execute
        # Remove expired sessions for this user + enforce max sessions
        execute(
            "DELETE FROM sessions WHERE user_id = %s AND expires_at < NOW()",
            (user_id,), fetch="none"
        )
        execute(
            """DELETE FROM sessions WHERE session_token IN (
                SELECT session_token FROM sessions
                WHERE user_id = %s ORDER BY created_at DESC
                OFFSET %s
            )""",
            (user_id, _MAX_SESSIONS_PER_USER - 1), fetch="none"
        )
        execute(
            """INSERT INTO sessions (session_token, user_id, expires_at)
               VALUES (%s, %s, NOW() + MAKE_INTERVAL(days => %s))""",
            (token, user_id, int(expires_days)), fetch="none"
        )
    except Exception as e:
        logger.error(f"[Session] DB insert failed: {e}")
        raise
    return token


def verify_session_token(token: str) -> Optional[str]:
    """Verify DB session token. Returns user_id or None. FAIL_CLOSED."""
    if not token or len(token) != 64:
        return None
    # Validate hex format
    if not all(c in '0123456789abcdef' for c in token):
        return None
    try:
        from connectors.db_client_v2 import execute
        result = execute(
            "SELECT user_id FROM sessions WHERE session_token = %s AND expires_at > NOW()",
            (token,), fetch="one"
        )
        if result.get("ok") and result.get("data"):
            return str(result["data"][0])
    except Exception as e:
        logger.warning(f"[Session] Verify failed: {e}")
    return None


def _delete_session(token: str):
    """Delete session (logout)."""
    try:
        from connectors.db_client_v2 import execute
        execute("DELETE FROM sessions WHERE session_token = %s", (token,), fetch="none")
    except Exception as e:
        logger.warning(f"[Session] Delete failed: {e}")


def _get_session_token(request: Request) -> str:
    """Extract session token from HttpOnly cookie only (no header fallback — CSRF safe)."""
    return request.cookies.get("__session", "")


# ─── Auth Dependency: get_current_user ───

def get_current_user(request: Request) -> Optional[dict]:
    """Auth dependency. Returns user dict or None. FAIL_CLOSED."""
    token = _get_session_token(request)
    if not token:
        return None
    user_id = verify_session_token(token)
    if not user_id:
        return None
    return get_user_by_id(user_id)


# ─── OTP Send ───

@router.post("/otp/send")
@limiter.limit("3/minute")
async def send_otp(request: Request):
    """Send 6-digit OTP to email. No signup required."""
    if _OTP_DISABLED:
        raise HTTPException(status_code=503, detail="OTP service unavailable")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    email = str(body.get("email", "")).strip().lower()
    if not email or not _validate_email(email):
        raise HTTPException(status_code=400, detail="Valid email required")

    code = "".join([str(secrets.randbelow(10)) for _ in range(_OTP_LENGTH)])
    expires = time.time() + _OTP_TTL_SEC

    # Store OTP (hashed) — DB first, in-memory fallback
    _store_otp(email, code, expires)

    # Send email
    sent = await _send_otp_email(email, code)

    if not sent:
        logger.warning(f"[OTP] Email send failed for {email[:3]}***")
        if PADDLE_ENVIRONMENT == "sandbox":
            logger.info(f"[OTP-SANDBOX] code sent (sandbox fallback) for {email[:3]}***")
            return {"ok": True, "message": "OTP sent (sandbox mode)", "ttl": _OTP_TTL_SEC}
        raise HTTPException(
            status_code=500,
            detail="Email delivery failed. Please try again shortly or contact support."
        )

    logger.info(f"[OTP] Sent to {email[:3]}***")
    return {"ok": True, "message": "OTP sent", "ttl": _OTP_TTL_SEC}


def _store_otp(email: str, code: str, expires: float):
    """Store OTP (hashed) in DB (single transaction) or in-memory fallback."""
    code_hash = _hash_otp(code, email)
    try:
        from connectors.db_client import get_connection, release_connection
        conn = get_connection()
        if conn is None:
            raise RuntimeError("DB connection unavailable")
        cur = conn.cursor()
        try:
            # Single transaction: invalidate old + insert new + cleanup
            cur.execute("UPDATE otp_codes SET used = TRUE WHERE email = %s AND used = FALSE", (email,))
            cur.execute(
                """INSERT INTO otp_codes (id, email, code_hash, expires_at, used)
                   VALUES (%s, %s, %s, TO_TIMESTAMP(%s), FALSE)""",
                (str(uuid.uuid4()), email, code_hash, expires)
            )
            cur.execute(
                "DELETE FROM otp_codes WHERE email = %s AND (used = TRUE OR expires_at < NOW())",
                (email,)
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            release_connection(conn)
    except Exception as e:
        logger.warning(f"[OTP] DB store failed, using memory: {e}")
        _cleanup_otp_store()
        _otp_store[email] = {"code": code_hash, "expires": expires, "attempts": 0}


async def _send_otp_email(email: str, code: str) -> bool:
    """Send OTP via Gmail SMTP."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", "") or smtp_user

    if not smtp_user or not smtp_pass:
        logger.error("[OTP] SMTP_USER or SMTP_PASSWORD not configured — cannot send OTP email")
        return False

    try:
        import asyncio
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "[법마디] 인증번호 안내 / Verification Code"
        msg["From"] = f"=?UTF-8?B?67KV66eI65SUIChMYXdtYWRpKSDsnbjspp0=?= <{smtp_from}>"
        msg["To"] = email
        msg["Reply-To"] = "noreply@lawmadi.com"

        html = f"""
        <div style="font-family:-apple-system,'Malgun Gothic','맑은 고딕',sans-serif;max-width:440px;margin:0 auto;padding:40px 24px;background:#ffffff;">
            <div style="text-align:center;margin-bottom:28px;">
                <h2 style="color:#1e293b;margin:0;font-size:22px;">법마디 (Lawmadi)</h2>
                <p style="color:#94a3b8;font-size:13px;margin-top:4px;">AI 법률 분석 서비스</p>
            </div>
            <p style="color:#475569;font-size:15px;margin-bottom:4px;">인증번호를 확인해 주세요.</p>
            <p style="color:#94a3b8;font-size:12px;margin-top:2px;margin-bottom:12px;">Your verification code:</p>
            <div style="background:#f1f5f9;border-radius:12px;padding:24px;text-align:center;margin:16px 0;">
                <span style="font-size:36px;font-weight:900;letter-spacing:10px;color:#2563eb;">{code}</span>
            </div>
            <p style="color:#94a3b8;font-size:13px;line-height:1.8;">
                이 인증번호는 5분 후 만료됩니다.<br>
                본인이 요청하지 않았다면 이 메일을 무시하세요.<br>
                <span style="color:#b0b8c4;font-size:12px;">
                This code expires in 5 minutes. Ignore if not requested.
                </span>
            </p>
            <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0;">
            <p style="color:#cbd5e1;font-size:11px;text-align:center;line-height:1.6;">
                법마디 (Lawmadi) &middot; <a href="https://lawmadi.com" style="color:#cbd5e1;text-decoration:none;">lawmadi.com</a><br>
                이 메일은 발송 전용이며 회신할 수 없습니다.<br>
                <span style="font-size:10px;">This is an automated message. Please do not reply.</span>
            </p>
        </div>
        """
        msg.attach(MIMEText(html, "html"))

        def _smtp_send():
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, email, msg.as_string())

        await asyncio.to_thread(_smtp_send)
        return True
    except Exception as e:
        logger.error(f"[OTP] SMTP error: {e}")
        return False


# ─── OTP Verify ───

@router.post("/otp/verify")
@limiter.limit("5/minute")
async def verify_otp_endpoint(request: Request):
    """Verify OTP -> create/get user -> issue DB session token."""
    if _OTP_DISABLED:
        raise HTTPException(status_code=503, detail="OTP service unavailable")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    email = str(body.get("email", "")).strip().lower()
    code = str(body.get("code", "")).strip()

    if not email or not _validate_email(email):
        raise HTTPException(status_code=400, detail="Valid email required")
    if not code or len(code) != _OTP_LENGTH:
        raise HTTPException(status_code=400, detail="Invalid OTP format")

    result = _verify_otp_code(email, code)

    if result == "expired":
        return JSONResponse(status_code=410, content={"ok": False, "error": "OTP expired"})
    if result == "max_attempts":
        return JSONResponse(status_code=429, content={"ok": False, "error": "Too many attempts"})
    if result in ("invalid", "not_found"):
        # Unified response to prevent email enumeration
        return JSONResponse(status_code=401, content={"ok": False, "error": "Invalid OTP"})

    # Get or create user
    user = _get_or_create_user(email)
    if not user:
        raise HTTPException(status_code=500, detail="Failed to create user account")

    # Issue DB session token (30 days)
    token = _create_db_session(user["user_id"])

    # Update last_login_at
    try:
        from connectors.db_client_v2 import execute
        execute("UPDATE users SET last_login_at = NOW() WHERE user_id = %s", (user["user_id"],), fetch="none")
    except Exception as e:
        logger.warning(f"[Session] last_login_at update failed: {e}")

    logger.info(f"[OTP] Verified, session created for user_id={user['user_id'][:8]}")

    response = JSONResponse(content={
        "ok": True,
        "user": {
            "email": user["email"],
            "credit_balance": user["credit_balance"],
            "current_plan": user["current_plan"],
        },
        "expires_in": SESSION_EXPIRY_DAYS * 86400,
    })
    response.set_cookie(
        key="__session",
        value=token,
        max_age=SESSION_EXPIRY_DAYS * 86400,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return response


def _verify_otp_code(email: str, code: str) -> str:
    """Verify OTP code. Returns: 'ok', 'invalid', 'expired', 'max_attempts', 'not_found'."""
    code_hash = _hash_otp(code, email)

    # Try DB first
    try:
        from connectors.db_client_v2 import execute

        # Get latest unused OTP
        result = execute(
            """SELECT id, code_hash, expires_at, attempts FROM otp_codes
               WHERE email = %s AND used = FALSE
               ORDER BY created_at DESC LIMIT 1""",
            (email,), fetch="one"
        )
        if result.get("ok") and result.get("data"):
            row = result["data"]
            otp_id, stored_hash, expires_at = str(row[0]), row[1], row[2]
            db_attempts = row[3] if len(row) > 3 else 0

            # Brute force protection: max attempts per OTP
            if db_attempts >= _MAX_OTP_ATTEMPTS:
                return "max_attempts"

            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            if hasattr(expires_at, 'timestamp') and expires_at.timestamp() < now.timestamp():
                return "expired"

            if hmac.compare_digest(stored_hash, code_hash):
                # Mark as used
                execute("UPDATE otp_codes SET used = TRUE WHERE id = %s", (otp_id,), fetch="none")
                return "ok"

            # Increment attempts on wrong code
            execute(
                "UPDATE otp_codes SET attempts = attempts + 1 WHERE id = %s",
                (otp_id,), fetch="none"
            )
            return "invalid"
        # No OTP found in DB — fall through to memory check
    except Exception as e:
        logger.warning(f"[OTP] DB verify failed, trying memory: {e}")

    # Fallback: in-memory
    entry = _otp_store.get(email)
    if not entry:
        return "not_found"

    if entry["attempts"] >= _MAX_OTP_ATTEMPTS:
        return "max_attempts"

    entry["attempts"] += 1

    if entry["expires"] < time.time():
        del _otp_store[email]
        return "expired"

    if hmac.compare_digest(entry["code"], code_hash):
        del _otp_store[email]
        return "ok"

    return "invalid"


# ─── Auth Endpoints ───

@router.get("/me")
@limiter.limit("30/minute")
async def auth_me(request: Request):
    """Get current user info from session."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Reset daily_free if new day (KST)
    _maybe_reset_daily_free(user)

    return {
        "ok": True,
        "user": {
            "email": user["email"],
            "credit_balance": user["credit_balance"],
            "current_plan": user["current_plan"],
            "daily_free_used": user["daily_free_used"],
            "daily_free_limit": DAILY_FREE_LIMIT,
        }
    }


@router.post("/logout")
async def auth_logout(request: Request):
    """Logout: delete session."""
    token = _get_session_token(request)
    if token:
        _delete_session(token)
    response = JSONResponse(content={"ok": True})
    response.delete_cookie("__session", path="/", secure=True, samesite="lax")
    return response


# ─── Credit Balance ───

@router.get("/credits")
@limiter.limit("30/minute")
async def get_credits(request: Request):
    """Get credit balance for authenticated user."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    _maybe_reset_daily_free(user)

    return {
        "ok": True,
        "credits": user["credit_balance"],
        "current_plan": user["current_plan"],
        "daily_free_used": user["daily_free_used"],
        "daily_free_limit": DAILY_FREE_LIMIT,
    }


@router.get("/credits/history")
@limiter.limit("10/minute")
async def credit_history(request: Request):
    """Return recent credit ledger entries for authenticated user."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from connectors.db_client import _db_enabled, get_connection, release_connection
    if not _db_enabled():
        return {"ok": True, "history": [], "balance": user["credit_balance"]}

    conn = None
    try:
        conn = get_connection()
        if not conn:
            return {"ok": True, "history": [], "balance": user["credit_balance"]}
        cur = conn.cursor()
        cur.execute(
            """SELECT amount, type, balance_after, reference_id, created_at
               FROM credit_ledger WHERE user_id = %s
               ORDER BY created_at DESC LIMIT 50""",
            (user["user_id"],)
        )
        rows = cur.fetchall()
        cur.close()
        history = []
        for r in rows:
            history.append({
                "amount": r[0],
                "type": r[1],
                "balance_after": r[2],
                "reference_id": (r[3] or "")[:8] + "..." if r[3] else "",
                "created_at": r[4].isoformat() if r[4] else "",
            })
        return {"ok": True, "history": history, "balance": user["credit_balance"]}
    except Exception as e:
        logger.warning(f"[Credits] History query failed: {e}")
        return {"ok": True, "history": [], "balance": user["credit_balance"]}
    finally:
        if conn:
            release_connection(conn)


@router.post("/credits/check")
@limiter.limit("30/minute")
async def check_credits(request: Request):
    """Check if user can afford a query. Returns cost and availability."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        body = await request.json()
    except Exception:
        body = {}

    query_type = str(body.get("query_type", "general")).strip()
    cost = _get_query_cost(query_type)

    _maybe_reset_daily_free(user)

    # Free user daily quota check
    if user["credit_balance"] == 0 and user["current_plan"] == "free":
        if query_type in ("expert", "combo"):
            return JSONResponse(status_code=402, content={
                "ok": False, "error": "INSUFFICIENT_CREDITS",
                "message": "Expert mode requires credits. Please purchase a credit pack.",
                "balance": 0, "required": cost,
            })
        if user["daily_free_used"] < DAILY_FREE_LIMIT:
            return {"ok": True, "can_proceed": True, "cost": 0, "free_remaining": DAILY_FREE_LIMIT - user["daily_free_used"]}
        return JSONResponse(status_code=402, content={
            "ok": False, "error": "DAILY_LIMIT_REACHED",
            "message": "Daily free limit reached. Purchase credits to continue.",
            "balance": 0, "daily_free_used": user["daily_free_used"],
        })

    if user["credit_balance"] < cost:
        return JSONResponse(status_code=402, content={
            "ok": False, "error": "INSUFFICIENT_CREDITS",
            "balance": user["credit_balance"], "required": cost,
        })

    return {"ok": True, "can_proceed": True, "cost": cost, "balance": user["credit_balance"]}


def _get_query_cost(query_type: str) -> int:
    """Return credit cost for query type."""
    costs = {"general": 1, "expert": 2, "combo": 3}
    return costs.get(query_type, 1)


# ─── Credit Operations ───

def deduct_credit(user_id: str, amount: int = 1, reference_id: str = "") -> bool:
    """Post-deduction: deduct credits atomically with ledger entry. FOR UPDATE lock."""
    if amount <= 0:
        logger.warning(f"[Credit] deduct_credit 거부: amount={amount} (must be > 0)")
        return False
    from connectors.db_client import _db_enabled, get_connection, release_connection
    if not _db_enabled():
        return False
    conn = None
    try:
        conn = get_connection()
        if conn is None:
            return False
        cur = conn.cursor()

        # Row-level lock prevents concurrent double-deduction
        cur.execute(
            "SELECT credit_balance FROM users WHERE user_id = %s FOR UPDATE",
            (user_id,)
        )
        row = cur.fetchone()
        if not row or row[0] < amount:
            conn.rollback()
            cur.close()
            return False

        new_balance = row[0] - amount
        cur.execute(
            "UPDATE users SET credit_balance = %s WHERE user_id = %s",
            (new_balance, user_id)
        )

        # Ledger entry with balance_after
        deduct_type = "expert_deduct" if amount >= 2 else "question_deduct"
        cur.execute(
            """INSERT INTO credit_ledger (id, user_id, amount, type, balance_after, reference_id)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (str(uuid.uuid4()), user_id, -amount, deduct_type, new_balance, reference_id or None)
        )

        conn.commit()
        cur.close()
        logger.info(f"[Credits] Deducted {amount} from user={user_id[:8]}, balance={new_balance}")
        return True
    except Exception as e:
        logger.warning(f"[Credits] Deduct failed: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False
    finally:
        if conn:
            release_connection(conn)


def use_daily_free(user_id: str, reference_id: str = "") -> bool:
    """Increment daily_free_used for free users. Returns True if allowed."""
    from connectors.db_client import _db_enabled, get_connection, release_connection
    if not _db_enabled():
        return False
    conn = None
    try:
        conn = get_connection()
        if conn is None:
            return False
        cur = conn.cursor()

        cur.execute(
            "SELECT credit_balance, daily_free_used, daily_free_reset_at FROM users WHERE user_id = %s FOR UPDATE",
            (user_id,)
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            cur.close()
            return False

        balance, free_used, reset_at = row[0], row[1], row[2]

        # Reset if new day (KST)
        from datetime import datetime, timezone, timedelta
        kst = timezone(timedelta(hours=9))
        now_kst = datetime.now(kst)
        if reset_at and hasattr(reset_at, 'date') and reset_at.astimezone(kst).date() < now_kst.date():
            free_used = 0

        if free_used >= DAILY_FREE_LIMIT:
            conn.rollback()
            cur.close()
            return False

        cur.execute(
            "UPDATE users SET daily_free_used = %s, daily_free_reset_at = NOW() WHERE user_id = %s",
            (free_used + 1, user_id)
        )

        # Ledger entry
        cur.execute(
            """INSERT INTO credit_ledger (id, user_id, amount, type, balance_after, reference_id)
               VALUES (%s, %s, 0, 'daily_free', %s, %s)""",
            (str(uuid.uuid4()), user_id, balance, reference_id or None)
        )

        conn.commit()
        cur.close()
        logger.info(f"[Credits] Daily free used for user={user_id[:8]}, count={free_used + 1}")
        return True
    except Exception as e:
        logger.warning(f"[Credits] Daily free failed: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False
    finally:
        if conn:
            release_connection(conn)


def add_credits(user_id: str, amount: int, reason: str = "purchase", reference_id: str = "") -> bool:
    """Add credits to user account with ledger entry."""
    if amount <= 0:
        logger.warning(f"[Credit] add_credits 거부: amount={amount} (must be > 0)")
        return False
    _MAX_CREDITS = 999_999
    from connectors.db_client import _db_enabled, get_connection, release_connection
    if not _db_enabled():
        return False
    conn = None
    try:
        conn = get_connection()
        if conn is None:
            return False
        cur = conn.cursor()

        cur.execute(
            "SELECT credit_balance FROM users WHERE user_id = %s FOR UPDATE",
            (user_id,)
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            cur.close()
            return False

        new_balance = min(row[0] + amount, _MAX_CREDITS)
        cur.execute(
            "UPDATE users SET credit_balance = %s WHERE user_id = %s",
            (new_balance, user_id)
        )

        # Update plan if credits > 0
        if new_balance > 0:
            cur.execute("UPDATE users SET current_plan = 'premium' WHERE user_id = %s AND current_plan = 'free'", (user_id,))

        # Ledger entry
        cur.execute(
            """INSERT INTO credit_ledger (id, user_id, amount, type, balance_after, reference_id)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (str(uuid.uuid4()), user_id, amount, reason, new_balance, reference_id or None)
        )

        conn.commit()
        cur.close()
        logger.info(f"[Credits] Added {amount} to user={user_id[:8]}, balance={new_balance} ({reason})")
        return True
    except Exception as e:
        logger.error(f"[Credits] Add failed: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False
    finally:
        if conn:
            release_connection(conn)


def _maybe_reset_daily_free(user: dict):
    """Reset daily_free_used if new day (KST). Mutates user dict."""
    try:
        from datetime import datetime, timezone, timedelta
        kst = timezone(timedelta(hours=9))
        now_kst = datetime.now(kst)
        reset_at = user.get("daily_free_reset_at")
        if reset_at and hasattr(reset_at, 'date'):
            if reset_at.astimezone(kst).date() < now_kst.date():
                user["daily_free_used"] = 0
                from connectors.db_client_v2 import execute
                execute(
                    "UPDATE users SET daily_free_used = 0, daily_free_reset_at = NOW() WHERE user_id = %s",
                    (user["user_id"],), fetch="none"
                )
    except Exception as e:
        logger.warning(f"[Credit] Daily free reset failed: {e}")


# ─── Paddle Webhook ───

@router.post("/webhook")
async def paddle_webhook(request: Request):
    """Handle Paddle webhook events."""
    raw_body = await request.body()

    # Verify webhook signature: mandatory in production, skip in sandbox if no secret
    if PADDLE_WEBHOOK_SECRET:
        sig_header = request.headers.get("Paddle-Signature", "")
        if not _verify_paddle_signature(raw_body, sig_header):
            logger.warning("[Paddle] Webhook signature verification failed")
            raise HTTPException(status_code=403, detail="Invalid signature")
    elif PADDLE_ENVIRONMENT == "production":
        logger.error("[Paddle] PADDLE_WEBHOOK_SECRET not set in production — rejecting")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    else:
        logger.warning("[Paddle] Webhook signature skip (sandbox, no secret)")

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = data.get("event_type", "")
    event_data = data.get("data", {})

    logger.info(f"[Paddle] Webhook: {event_type}")

    if event_type == "transaction.completed":
        await _handle_transaction_completed(event_data)
    elif event_type == "transaction.payment_failed":
        logger.warning(f"[Paddle] Payment failed: {event_data.get('id', 'unknown')}")
    elif event_type == "adjustment.created":
        await _handle_adjustment_created(event_data)
    else:
        logger.info(f"[Paddle] Unhandled event: {event_type}")

    return {"ok": True}


def _verify_paddle_signature(raw_body: bytes, sig_header: str) -> bool:
    """Verify Paddle webhook signature (ts + h1 scheme)."""
    if not PADDLE_WEBHOOK_SECRET or not sig_header:
        return False
    try:
        parts = {}
        for segment in sig_header.split(";"):
            kv = segment.strip().split("=", 1)
            if len(kv) == 2:
                parts[kv[0]] = kv[1]

        ts = parts.get("ts", "")
        h1 = parts.get("h1", "")
        if not ts or not h1:
            return False

        # Timestamp freshness (2 min tolerance)
        try:
            if abs(time.time() - int(ts)) > 120:
                logger.warning("[Paddle] Webhook timestamp too old")
                return False
        except ValueError:
            return False

        signed_payload = f"{ts}:{raw_body.decode('utf-8')}"
        expected = hmac.new(
            PADDLE_WEBHOOK_SECRET.encode(),
            signed_payload.encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(h1, expected)
    except Exception as e:
        logger.error(f"[Paddle] Signature verification error: {e}")
        return False


def _is_webhook_processed(reference_id: str) -> bool:
    """Check if webhook already processed (idempotency via credit_ledger)."""
    try:
        from connectors.db_client_v2 import execute
        result = execute(
            "SELECT 1 FROM credit_ledger WHERE reference_id = %s LIMIT 1",
            (reference_id,), fetch="one"
        )
        return bool(result.get("ok") and result.get("data"))
    except Exception:
        return False


async def _handle_transaction_completed(event_data: dict):
    """Process completed transaction -> add credits (idempotent)."""
    transaction_id = event_data.get("id", "")
    if not transaction_id:
        logger.error("[Paddle] No transaction ID in event")
        return

    reference_id = f"paddle:{transaction_id}"

    # Idempotency check
    if _is_webhook_processed(reference_id):
        logger.info(f"[Paddle] Transaction {transaction_id} already processed (skip)")
        return

    # Extract customer email
    customer_email = ""
    customer = event_data.get("customer", {})
    if isinstance(customer, dict):
        customer_email = customer.get("email", "")
    if not customer_email:
        billing = event_data.get("billing_details", {})
        if isinstance(billing, dict):
            customer_email = billing.get("email", "")

    # Fallback: lookup email via Paddle API using customer_id
    if not customer_email:
        paddle_cid = ""
        if isinstance(customer, dict):
            paddle_cid = customer.get("id", "")
        if not paddle_cid:
            paddle_cid = event_data.get("customer_id", "")
        if paddle_cid:
            logger.info(f"[Paddle] No email in event, fetching from API for {paddle_cid}")
            try:
                customer_email = await _fetch_customer_email(paddle_cid)
            except Exception as e:
                logger.error(f"[Paddle] Customer API lookup failed: {e}")

    if not customer_email:
        logger.error(f"[Paddle] No email in transaction.completed event (txn={transaction_id})")
        return

    customer_email = customer_email.strip().lower()

    # Get or create user
    user = _get_or_create_user(customer_email)
    if not user:
        logger.error(f"[Paddle] Failed to get/create user for {customer_email[:3]}***")
        return

    # Update paddle_customer_id if present
    paddle_cid = ""
    if isinstance(customer, dict):
        paddle_cid = customer.get("id", "")
    if not paddle_cid:
        paddle_cid = event_data.get("customer_id", "")
    if paddle_cid and not user.get("paddle_customer_id"):
        try:
            from connectors.db_client_v2 import execute
            execute("UPDATE users SET paddle_customer_id = %s WHERE user_id = %s",
                    (paddle_cid, user["user_id"]), fetch="none")
        except Exception as e:
            logger.warning(f"[Paddle] customer_id update failed: {e}")

    # Determine credits from line items
    items = event_data.get("items", [])
    total_credits = 0
    _MAX_QTY = 100
    _MAX_CREDITS = 999_999
    for item in items:
        price = item.get("price", {})
        price_id = price.get("id", "") if isinstance(price, dict) else ""
        qty = item.get("quantity", 1)

        if not isinstance(qty, int) or qty < 1 or qty > _MAX_QTY:
            logger.warning(f"[Paddle] Invalid quantity {qty}, clamping to 1")
            qty = 1

        pack_name = _PRICE_TO_PACK.get(price_id, "")
        if pack_name and pack_name in CREDIT_PACKS:
            total_credits += CREDIT_PACKS[pack_name]["credits"] * qty

    if total_credits == 0:
        logger.error(f"[Paddle] price_id→pack 매핑 실패 — 크레딧 미지급 (price_id 미등록 가능성)")
        # custom_data fallback 비활성화: price_id 매핑만 신뢰 (보안)

    total_credits = min(total_credits, _MAX_CREDITS)

    if total_credits > 0:
        add_credits(user["user_id"], total_credits, reason="purchase", reference_id=reference_id)
        logger.info(f"[Paddle] Credited {total_credits} to user={user['user_id'][:8]}")
    else:
        logger.error(f"[Paddle] CRITICAL: Could not determine credits for transaction {transaction_id}, email={customer_email[:3]}***. Manual review required.")


# ─── Adjustment (Refund) Webhook Handler ───

async def _handle_adjustment_created(event_data: dict):
    """Process adjustment.created webhook -> revoke credits for refunds."""
    adjustment_id = event_data.get("id", "")
    action = event_data.get("action", "")
    transaction_id = event_data.get("transaction_id", "")

    if action not in ("refund", "full_refund"):
        logger.info(f"[Paddle] Adjustment {adjustment_id} is '{action}', not refund — skip credit revoke")
        return

    if not transaction_id:
        logger.error(f"[Paddle] No transaction_id in adjustment {adjustment_id}")
        return

    logger.info(f"[Paddle] Processing refund adjustment: adj={adjustment_id}, txn={transaction_id}")
    await revoke_credits_for_refund(transaction_id)


async def revoke_credits_for_refund(transaction_id: str):
    """환불 시 해당 거래의 크레딧을 DB에서 차감 (idempotent)."""
    from connectors.db_client import _db_enabled, get_connection, release_connection
    if not _db_enabled():
        logger.warning("[Paddle] DB disabled — cannot revoke credits")
        return

    ref_id = f"paddle:{transaction_id}"
    refund_ref = f"refund:{transaction_id}"
    conn = get_connection()
    if not conn:
        logger.error("[Paddle] DB connection failed for credit revoke")
        return
    try:
        cur = conn.cursor()
        # 원래 충전 기록에서 user_id, amount 조회
        cur.execute(
            "SELECT user_id, amount FROM credit_ledger WHERE reference_id = %s AND type = 'purchase' LIMIT 1",
            (ref_id,)
        )
        row = cur.fetchone()
        if not row:
            logger.warning(f"[Paddle] Refund: no purchase ledger for {ref_id}")
            cur.close()
            return

        user_id, original_amount = str(row[0]), int(row[1])

        # 멱등성: 이미 환불 처리됐는지 확인
        cur.execute(
            "SELECT 1 FROM credit_ledger WHERE reference_id = %s LIMIT 1",
            (refund_ref,)
        )
        if cur.fetchone():
            logger.info(f"[Paddle] Refund already processed for {transaction_id}")
            cur.close()
            return

        # 크레딧 차감 (FOR UPDATE lock)
        cur.execute("SELECT credit_balance FROM users WHERE user_id = %s FOR UPDATE", (user_id,))
        balance_row = cur.fetchone()
        if not balance_row:
            cur.close()
            return

        current_balance = int(balance_row[0])
        deduct = min(original_amount, current_balance)
        new_balance = current_balance - deduct

        cur.execute(
            """INSERT INTO credit_ledger (id, user_id, amount, type, balance_after, reference_id)
               VALUES (%s, %s, %s, 'refund', %s, %s)""",
            (str(uuid.uuid4()), user_id, -deduct, new_balance, refund_ref)
        )
        cur.execute(
            "UPDATE users SET credit_balance = %s, current_plan = CASE WHEN %s <= 0 THEN 'free' ELSE current_plan END WHERE user_id = %s",
            (new_balance, new_balance, user_id)
        )
        conn.commit()
        cur.close()
        logger.info(f"[Paddle] Refund credit revoked: user={user_id[:8]}, deducted={deduct}, new_balance={new_balance}")
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"[Paddle] Credit revoke for refund failed: {e}")
    finally:
        release_connection(conn)


# ─── Paddle Customer Email Lookup ───

async def _fetch_customer_email(customer_id: str) -> str:
    """Fetch customer email from Paddle API by customer_id."""
    result = await paddle_api_get(f"/customers/{customer_id}")
    # Paddle API returns {"data": {...}} on success, {"ok": false, "error": ...} on failure
    data = result.get("data", {})
    if isinstance(data, dict) and data.get("email"):
        email = data["email"].strip().lower()
        logger.info(f"[Paddle] Fetched email via API for {customer_id[:15]}...")
        return email
    logger.warning(f"[Paddle] Could not fetch email for {customer_id}: {str(result)[:200]}")
    return ""


# ─── Paddle API Client ───

_PADDLE_API_BASE = "https://api.paddle.com"
_PADDLE_SANDBOX_API_BASE = "https://sandbox-api.paddle.com"


def _paddle_api_base() -> str:
    return _PADDLE_SANDBOX_API_BASE if PADDLE_ENVIRONMENT == "sandbox" else _PADDLE_API_BASE


async def paddle_api_get(path: str, params: Optional[dict] = None) -> dict:
    """GET request to Paddle API. Returns parsed JSON or error dict."""
    import asyncio
    import urllib.request
    import urllib.parse
    import urllib.error

    if not PADDLE_API_KEY:
        return {"ok": False, "error": "PADDLE_API_KEY not configured"}

    base = _paddle_api_base()
    url = f"{base}{path}"
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})

    def _do():
        req = urllib.request.Request(url, method="GET")
        req.add_header("Authorization", f"Bearer {PADDLE_API_KEY}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            try:
                return {"ok": False, "error": json.loads(body)}
            except Exception:
                return {"ok": False, "error": body, "status": e.code}

    return await asyncio.to_thread(_do)


async def paddle_api_post(path: str, body: dict) -> dict:
    """POST request to Paddle API. Returns parsed JSON or error dict."""
    import asyncio
    import urllib.request
    import urllib.error

    if not PADDLE_API_KEY:
        return {"ok": False, "error": "PADDLE_API_KEY not configured"}

    base = _paddle_api_base()
    url = f"{base}{path}"
    payload = json.dumps(body).encode()

    def _do():
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Authorization", f"Bearer {PADDLE_API_KEY}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raw = e.read().decode() if e.fp else ""
            try:
                return {"ok": False, "error": json.loads(raw)}
            except Exception:
                return {"ok": False, "error": raw, "status": e.code}

    return await asyncio.to_thread(_do)


async def get_paddle_transaction(transaction_id: str) -> dict:
    """Fetch a single transaction from Paddle API."""
    return await paddle_api_get(f"/transactions/{transaction_id}")


async def list_paddle_transactions(
    status: str = None, after: str = None, per_page: int = 25,
    customer_id: str = None, order_by: str = None,
) -> dict:
    """List transactions from Paddle API with optional filters."""
    params = {"per_page": str(per_page)}
    if status:
        params["status"] = status
    if after:
        params["after"] = after
    if customer_id:
        params["customer_id"] = customer_id
    if order_by:
        params["order_by"] = order_by
    return await paddle_api_get("/transactions", params)


async def get_paddle_customer(customer_id: str) -> dict:
    """Fetch a single customer from Paddle API."""
    return await paddle_api_get(f"/customers/{customer_id}")


async def list_paddle_customers(
    after: str = None, per_page: int = 25, email: str = None,
) -> dict:
    """List customers from Paddle API."""
    params = {"per_page": str(per_page)}
    if after:
        params["after"] = after
    if email:
        params["email"] = email
    return await paddle_api_get("/customers", params)


async def create_paddle_adjustment(
    transaction_id: str, reason: str, action: str = "refund",
    items: Optional[list] = None,
) -> dict:
    """Create adjustment (refund/credit) via Paddle API.
    action: "refund" (full) or "credit" (partial/account credit).
    items: optional list of {"item_id": ..., "type": "full"/"partial", "amount": ...}
    """
    body: dict = {
        "action": action,
        "transaction_id": transaction_id,
        "reason": reason,
    }
    if items:
        body["items"] = items
    return await paddle_api_post("/adjustments", body)


async def list_paddle_adjustments(
    transaction_id: str = None, after: str = None, per_page: int = 25,
) -> dict:
    """List adjustments (refunds) from Paddle API."""
    params = {"per_page": str(per_page)}
    if transaction_id:
        params["transaction_id"] = transaction_id
    if after:
        params["after"] = after
    return await paddle_api_get("/adjustments", params)


# ─── Paddle Client Config ───

@router.get("/config")
async def paddle_config(request: Request):
    """Return Paddle public config for frontend (no secrets)."""
    lang = request.query_params.get("lang", "ko")
    if lang not in ("ko", "en"):
        lang = "ko"
    return {
        "environment": PADDLE_ENVIRONMENT,
        "client_token": PADDLE_CLIENT_TOKEN,
        "prices": _PRICE_IDS.get(lang, _PRICE_IDS["ko"]),
        "packs": CREDIT_PACKS,
    }


# ─── DB Table Init ───

def init_paddle_tables():
    """Initialize payment-related tables (v2 schema)."""
    from connectors.db_client import _db_enabled, get_connection, release_connection

    if not _db_enabled():
        return

    conn = None
    cur = None
    try:
        conn = get_connection()
        if conn is None:
            raise RuntimeError("DB connection failed")
        cur = conn.cursor()

        # Users table (central user identity)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id              VARCHAR(36) PRIMARY KEY,
                email                VARCHAR(255) UNIQUE NOT NULL,
                display_name         VARCHAR(100),
                paddle_customer_id   VARCHAR(50),
                current_plan         VARCHAR(20) NOT NULL DEFAULT 'free',
                credit_balance       INTEGER NOT NULL DEFAULT 0,
                daily_free_used      INTEGER NOT NULL DEFAULT 0,
                daily_free_reset_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_login_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # OTP codes table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS otp_codes (
                id           VARCHAR(36) PRIMARY KEY,
                email        VARCHAR(255) NOT NULL,
                code_hash    VARCHAR(64) NOT NULL,
                expires_at   TIMESTAMPTZ NOT NULL,
                used         BOOLEAN NOT NULL DEFAULT FALSE,
                attempts     INTEGER NOT NULL DEFAULT 0,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_otp_email_expires
            ON otp_codes (email, expires_at DESC)
        """)
        # Migrate: add attempts column if missing (safe for existing tables)
        try:
            cur.execute("ALTER TABLE otp_codes ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0")
        except Exception as e:
            logger.debug(f"[DB] ALTER TABLE otp_codes (attempts column): {e}")

        # Sessions table (DB-backed, 30-day TTL)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_token  VARCHAR(64) PRIMARY KEY,
                user_id        VARCHAR(36) NOT NULL REFERENCES users(user_id),
                expires_at     TIMESTAMPTZ NOT NULL,
                created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_user
            ON sessions (user_id)
        """)

        # Credit ledger (audit trail with balance_after)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS credit_ledger (
                id             VARCHAR(36) PRIMARY KEY,
                user_id        VARCHAR(36) NOT NULL REFERENCES users(user_id),
                amount         INTEGER NOT NULL,
                type           VARCHAR(30) NOT NULL,
                balance_after  INTEGER NOT NULL,
                reference_id   VARCHAR(100),
                created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_ledger_user
            ON credit_ledger (user_id, created_at DESC)
        """)
        # Unique on reference_id for webhook idempotency
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_ledger_ref_unique
            ON credit_ledger (reference_id) WHERE reference_id IS NOT NULL AND reference_id LIKE 'paddle:%'
        """)

        # ─── Migration: copy data from old tables if they exist ───
        # Migrate user_credits -> users (one-time)
        cur.execute("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_credits') THEN
                    -- Only migrate rows not yet in users
                    INSERT INTO users (user_id, email, credit_balance)
                    SELECT gen_random_uuid()::text, uc.email_hash, uc.credits
                    FROM user_credits uc
                    WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.email = uc.email_hash)
                    ON CONFLICT (email) DO NOTHING;
                END IF;
            END $$
        """)

        # Cleanup expired sessions and OTPs on startup
        cur.execute("DELETE FROM sessions WHERE expires_at < NOW()")
        cur.execute("DELETE FROM otp_codes WHERE expires_at < NOW() OR used = TRUE")

        conn.commit()
        logger.info("[Paddle] v2 tables initialized + expired sessions/OTPs cleaned")
    except Exception as e:
        logger.error(f"[Paddle] Table init failed: {e}")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)
