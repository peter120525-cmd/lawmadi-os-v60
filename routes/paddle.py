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
from slowapi.util import get_remote_address

logger = logging.getLogger("LawmadiOS.Paddle")
router = APIRouter(prefix="/api/paddle", tags=["paddle"])
limiter = Limiter(key_func=get_remote_address)

# ─── Config ───
PADDLE_WEBHOOK_SECRET = os.getenv("PADDLE_WEBHOOK_SECRET", "").strip()
PADDLE_API_KEY = os.getenv("PADDLE_API_KEY", "").strip()
PADDLE_CLIENT_TOKEN = os.getenv("PADDLE_CLIENT_TOKEN", "").strip()
PADDLE_ENVIRONMENT = os.getenv("PADDLE_ENVIRONMENT", "sandbox")
DAILY_FREE_LIMIT = int(os.getenv("DAILY_FREE_LIMIT", "2"))
SESSION_EXPIRY_DAYS = int(os.getenv("SESSION_EXPIRY_DAYS", "30"))

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

# Paddle Sandbox price IDs (KRW + USD)
_PRICE_IDS = {
    "ko": {
        "starter":  os.getenv("PADDLE_PRICE_STARTER_KR",  "pri_01kk1d1pxdmrwwfxj5dstc31pr"),
        "standard": os.getenv("PADDLE_PRICE_STANDARD_KR", "pri_01kk1d4mnzp64jz6r079y8n4qa"),
        "pro":      os.getenv("PADDLE_PRICE_PRO_KR",      "pri_01kk1d6kaqcbe4261pxef9jasw"),
    },
    "en": {
        "starter":  os.getenv("PADDLE_PRICE_STARTER_EN",  "pri_01kk1e4d8dywx9dpxmm1pgapxv"),
        "standard": os.getenv("PADDLE_PRICE_STANDARD_EN", "pri_01kk1e621qz21ynfw1hfskg7a2"),
        "pro":      os.getenv("PADDLE_PRICE_PRO_EN",      "pri_01kk1e7mw72vtdftps4wq6qz3z"),
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


def _hash_otp(code: str, email: str = "") -> str:
    """Hash OTP code with HMAC-SHA256, using email as salt to prevent rainbow tables."""
    key = (email or "lawmadi-otp-salt").encode()
    return hmac.new(key, code.encode(), hashlib.sha256).hexdigest()


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
               VALUES (%s, %s, NOW() + INTERVAL '1 day' * %s)""",
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
    except Exception:
        pass


def _get_session_token(request: Request) -> str:
    """Extract session token from HttpOnly cookie only (no header fallback — CSRF safe)."""
    return request.cookies.get("lm_session", "")


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
        msg["Subject"] = f"[Lawmadi] Verification Code: {code}"
        msg["From"] = f"Lawmadi OS <{smtp_from}>"
        msg["To"] = email

        html = f"""
        <div style="font-family:-apple-system,sans-serif;max-width:400px;margin:0 auto;padding:40px 24px;">
            <div style="text-align:center;margin-bottom:24px;">
                <h2 style="color:#1e293b;margin:0;">Lawmadi OS</h2>
                <p style="color:#94a3b8;font-size:13px;margin-top:4px;">AI Legal Analysis</p>
            </div>
            <p style="color:#475569;font-size:15px;margin-bottom:4px;">Your verification code:</p>
            <div style="background:#f1f5f9;border-radius:12px;padding:24px;text-align:center;margin:16px 0;">
                <span style="font-size:36px;font-weight:900;letter-spacing:10px;color:#2563eb;">{code}</span>
            </div>
            <p style="color:#94a3b8;font-size:13px;line-height:1.6;">
                This code expires in 5 minutes.<br>
                If you did not request this code, please ignore this email.
            </p>
            <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0;">
            <p style="color:#cbd5e1;font-size:11px;text-align:center;">
                Lawmadi OS &middot; lawmadi-db.web.app
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
@limiter.limit("10/minute")
async def verify_otp_endpoint(request: Request):
    """Verify OTP -> create/get user -> issue DB session token."""
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
    except Exception:
        pass

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
        key="lm_session",
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
    response.delete_cookie("lm_session", path="/")
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
                "reference_id": r[3] or "",
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
    except Exception:
        pass


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

    if not customer_email:
        logger.error("[Paddle] No email in transaction.completed event")
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
    if paddle_cid and not user.get("paddle_customer_id"):
        try:
            from connectors.db_client_v2 import execute
            execute("UPDATE users SET paddle_customer_id = %s WHERE user_id = %s",
                    (paddle_cid, user["user_id"]), fetch="none")
        except Exception:
            pass

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
        custom = event_data.get("custom_data", {})
        if isinstance(custom, dict):
            pack = custom.get("pack", "")
            if pack in CREDIT_PACKS:
                total_credits = CREDIT_PACKS[pack]["credits"]

    total_credits = min(total_credits, _MAX_CREDITS)

    if total_credits > 0:
        add_credits(user["user_id"], total_credits, reason="purchase", reference_id=reference_id)
        logger.info(f"[Paddle] Credited {total_credits} to user={user['user_id'][:8]}")
    else:
        logger.error(f"[Paddle] CRITICAL: Could not determine credits for transaction {transaction_id}, email={customer_email[:3]}***. Manual review required.")


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
        except Exception:
            pass  # Column already exists or DB doesn't support IF NOT EXISTS

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
