"""
Lawmadi OS ADK — Cloud Functions Gen2 proxy.

Firebase Hosting -> Cloud Functions -> Vertex AI Agent Engine

Features:
  - Model fallback (quota error auto-switch)
  - Agent Engine circuit breaker
  - IP-based sliding window rate limiting
  - Structured audit logging (Cloud Logging)

Deploy:
  gcloud functions deploy lawmadi-proxy \
    --gen2 \
    --runtime python312 \
    --trigger-http \
    --allow-unauthenticated \
    --region asia-northeast3 \
    --source lawmadi-adk/proxy \
    --entry-point handle_ask \
    --set-env-vars AGENT_RESOURCE_NAME=projects/.../reasoningEngines/...

Firebase rewrite (firebase.json):
  "rewrites": [
    {"source": "/api/ask", "function": {"functionId": "lawmadi-proxy", "region": "asia-northeast3"}}
  ]
"""

import hashlib
import hmac
import json
import logging
import os
import re
import threading
import time

import functions_framework

from model_fallback import get_model, is_quota_error, on_quota_error

logger = logging.getLogger("LawmadiProxy")

# ---------------------------------------------------------------------------
# Agent Engine
# ---------------------------------------------------------------------------
AGENT_RESOURCE_NAME = os.environ.get("AGENT_RESOURCE_NAME", "")
_remote_agent = None

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
_ALLOWED_ORIGINS = {
    "https://lawmadi.com",
    "https://www.lawmadi.com",
    "https://lawmadi-os.web.app",
    "https://lawmadi-db.web.app",
    "http://localhost:3000",
}
_extra = os.environ.get("CORS_EXTRA_ORIGINS", "")
if _extra:
    _ALLOWED_ORIGINS.update(o.strip() for o in _extra.split(",") if o.strip())


def _get_cors_origin(request) -> str:
    origin = request.headers.get("Origin", "")
    return origin if origin in _ALLOWED_ORIGINS else ""


def _cors_headers(request) -> dict:
    origin = _get_cors_origin(request)
    if origin:
        return {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}
    return {}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def _verify_auth(request) -> bool:
    """Bearer token auth. Passes if INTERNAL_API_KEY not set (dev mode)."""
    api_key = os.environ.get("INTERNAL_API_KEY", "").strip()
    if not api_key:
        return True
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    token = auth[7:].strip()
    if not token:
        return False
    return hmac.compare_digest(token, api_key)


# ---------------------------------------------------------------------------
# Agent Engine circuit breaker (inline, separate from DRF CB)
# ---------------------------------------------------------------------------
class _AgentCB:
    """Lightweight circuit breaker for Agent Engine calls."""

    def __init__(self, threshold: int = 3, recovery: int = 30):
        self._lock = threading.Lock()
        self._failures = 0
        self._threshold = threshold
        self._recovery = recovery
        self._state = "CLOSED"
        self._last_fail: float = 0.0

    def allow(self) -> bool:
        with self._lock:
            if self._state == "OPEN":
                if time.time() - self._last_fail >= self._recovery:
                    self._state = "HALF_OPEN"
                    return True
                return False
            return True

    def success(self) -> None:
        with self._lock:
            self._failures = 0
            self._state = "CLOSED"

    def failure(self) -> None:
        with self._lock:
            self._failures += 1
            self._last_fail = time.time()
            if self._failures >= self._threshold:
                self._state = "OPEN"


_agent_cb = _AgentCB(threshold=3, recovery=30)

# ---------------------------------------------------------------------------
# Rate limiter (IP hash sliding window, instance-scoped)
# ---------------------------------------------------------------------------
_RATE_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", str(4 * 3600)))  # 4h
_RATE_MAX = int(os.environ.get("RATE_LIMIT_MAX", "100"))
_rate_store: dict = {}  # ip_hash -> [timestamps]
_rate_lock = threading.Lock()
_RATE_STORE_MAX = 5000


def _ip_hash(request) -> str:
    """Hash client IP for privacy-safe rate limiting."""
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
    ip = ip.split(",")[0].strip()
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


def _check_rate_limit(ip_h: str) -> bool:
    """Return True if request is allowed, False if rate-limited."""
    now = time.time()
    cutoff = now - _RATE_WINDOW
    with _rate_lock:
        # Stale cleanup
        if len(_rate_store) > _RATE_STORE_MAX:
            stale_keys = [
                k for k, ts in _rate_store.items()
                if not ts or ts[-1] < cutoff
            ]
            for k in stale_keys:
                del _rate_store[k]

        timestamps = _rate_store.get(ip_h, [])
        timestamps = [t for t in timestamps if t > cutoff]

        if len(timestamps) >= _RATE_MAX:
            _rate_store[ip_h] = timestamps
            return False

        timestamps.append(now)
        _rate_store[ip_h] = timestamps
        return True


# ---------------------------------------------------------------------------
# Audit logging (structured JSON via print -> Cloud Logging)
# ---------------------------------------------------------------------------
def _audit(event_type: str, payload: dict) -> None:
    """Emit structured audit log. Fail-soft."""
    try:
        entry = {
            "severity": "INFO",
            "event": event_type,
            "timestamp": time.time(),
            **payload,
        }
        print(json.dumps(entry, ensure_ascii=False, default=str))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Agent Engine client
# ---------------------------------------------------------------------------
def _get_agent():
    """Lazy init: Agent Engine client."""
    global _remote_agent
    if _remote_agent is None:
        import vertexai
        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "lawmadi-v50")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-northeast3")
        client = vertexai.Client(project=project, location=location)
        _remote_agent = client.agent_engines.get(AGENT_RESOURCE_NAME)
    return _remote_agent


def _extract_leader_from_response(text: str) -> str:
    m = re.search(r"\b(L\d{2})\b", text[:200])
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------
@functions_framework.http
def handle_ask(request):
    """POST /api/ask -> Agent Engine query.

    Request body: {"query": "...", "user_id": "..."}
    Response: {"response": "...", "leader": "...", "status": "ok", "meta": {...}}
    """
    ch = _cors_headers(request)

    # CORS preflight
    if request.method == "OPTIONS":
        return ("", 204, {
            **ch,
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        })

    if request.method != "POST":
        return (
            json.dumps({"status": "error", "response": "POST만 허용됩니다."}),
            405,
            {**ch, "Content-Type": "application/json"},
        )

    # Auth
    if not _verify_auth(request):
        return (
            json.dumps({"status": "error", "response": "인증 실패"}),
            401,
            {**ch, "Content-Type": "application/json"},
        )

    # Rate limit (after auth, before Agent Engine)
    ip_h = _ip_hash(request)
    if not _check_rate_limit(ip_h):
        _audit("rate_limited", {"ip_hash": ip_h})
        return (
            json.dumps({
                "status": "error",
                "response": "요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.",
            }, ensure_ascii=False),
            429,
            {**ch, "Content-Type": "application/json; charset=utf-8"},
        )

    try:
        body = request.get_json(silent=True) or {}
    except Exception:
        body = {}

    query = body.get("query", "").strip()
    if not query:
        return (
            json.dumps({"status": "error", "response": "질문을 입력해주세요."}),
            400,
            {**ch, "Content-Type": "application/json"},
        )

    user_id = body.get("user_id", "anonymous")
    start_time = time.time()
    model = get_model()

    # Circuit breaker check
    if not _agent_cb.allow():
        _audit("agent_cb_open", {"query": query[:2000]})
        return (
            json.dumps({
                "status": "error",
                "response": "서비스가 일시적으로 불안정합니다. 잠시 후 다시 시도해주세요.",
            }, ensure_ascii=False),
            503,
            {**ch, "Content-Type": "application/json; charset=utf-8"},
        )

    try:
        agent = _get_agent()

        # Agent Engine query (sync streaming)
        response_text = ""
        tool_calls_info = []

        import asyncio

        async def _query():
            nonlocal response_text
            async for event in agent.async_stream_query(
                user_id=user_id,
                message=query,
            ):
                if hasattr(event, "content") and event.content:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            response_text += part.text
                        if hasattr(part, "function_response"):
                            fr = part.function_response
                            if hasattr(fr, "response") and isinstance(fr.response, dict):
                                if "leader_id" in fr.response:
                                    tool_calls_info.append(fr.response)

        asyncio.run(_query())

        elapsed = round(time.time() - start_time, 2)
        _agent_cb.success()

        # Extract leader info from classify_query tool result
        leader_id = ""
        leader_name = ""
        for info in tool_calls_info:
            if "leader_id" in info:
                leader_id = info.get("leader_id", "")
                leader_name = info.get("leader_name", "")
                break

        if not leader_id:
            leader_id = _extract_leader_from_response(response_text)

        result = {
            "status": "ok",
            "response": response_text,
            "leader": leader_id,
            "meta": {
                "model": model,
                "elapsed_seconds": elapsed,
                "engine": "vertex-ai-agent-engine",
                "leader_name": leader_name,
            },
        }

        # Audit: success
        _audit("query_success", {
            "query": query[:2000],
            "response_sha256": hashlib.sha256(
                response_text.encode()
            ).hexdigest()[:16],
            "leader": leader_id,
            "status": "ok",
            "latency_ms": int(elapsed * 1000),
            "model": model,
        })

        return (
            json.dumps(result, ensure_ascii=False),
            200,
            {**ch, "Content-Type": "application/json; charset=utf-8"},
        )

    except Exception as e:
        elapsed = round(time.time() - start_time, 2)
        _agent_cb.failure()

        # Model fallback on quota error
        if is_quota_error(e):
            new_model = on_quota_error()
            logger.warning(f"Quota error, switched to {new_model}: {e}")
            _audit("quota_error", {
                "query": query[:2000],
                "model": model,
                "new_model": new_model,
                "latency_ms": int(elapsed * 1000),
            })
            return (
                json.dumps({
                    "status": "error",
                    "response": "모델 할당량 초과로 전환 중입니다. 다시 시도해주세요.",
                    "meta": {"model": new_model, "elapsed_seconds": elapsed},
                }, ensure_ascii=False),
                503,
                {**ch, "Content-Type": "application/json; charset=utf-8"},
            )

        logger.error(f"Agent Engine query failed: {e}")

        # Audit: failure
        _audit("query_error", {
            "query": query[:2000],
            "error": str(e)[:500],
            "latency_ms": int(elapsed * 1000),
            "model": model,
        })

        return (
            json.dumps({
                "status": "error",
                "response": "죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                "meta": {"error": str(e), "elapsed_seconds": elapsed},
            }, ensure_ascii=False),
            500,
            {**ch, "Content-Type": "application/json; charset=utf-8"},
        )
