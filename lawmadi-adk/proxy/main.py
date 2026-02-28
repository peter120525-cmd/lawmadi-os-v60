"""
Lawmadi OS ADK — Cloud Functions Gen2 proxy.

Firebase Hosting -> Cloud Functions -> Vertex AI Agent Engine

Features:
  - /api/ask: JSON 응답
  - /api/ask-stream: SSE 스트리밍 응답
  - /api/ask-expert: 특정 리더 지정 질의
  - Model fallback (quota error auto-switch)
  - Agent Engine circuit breaker
  - IP-based sliding window rate limiting
  - Structured audit logging (Cloud Logging)
  - CSP headers, body size limit
  - p50/p95/p99 latency metrics

Deploy:
  gcloud functions deploy lawmadi-proxy \
    --gen2 \
    --runtime python312 \
    --trigger-http \
    --allow-unauthenticated \
    --region asia-northeast3 \
    --source lawmadi-adk/proxy \
    --entry-point handle_request \
    --set-env-vars AGENT_RESOURCE_NAME=projects/.../reasoningEngines/...

Firebase rewrite (firebase.json):
  "rewrites": [
    {"source": "/api/**", "function": {"functionId": "lawmadi-proxy", "region": "asia-northeast3"}}
  ]
"""

import hashlib
import hmac
import json
import logging
import math
import os
import re
import threading
import time

import functions_framework

from model_fallback import get_model, get_status as get_model_status, is_quota_error, on_quota_error

logger = logging.getLogger("LawmadiProxy")

# ---------------------------------------------------------------------------
# Agent Engine
# ---------------------------------------------------------------------------
AGENT_RESOURCE_NAME = os.environ.get("AGENT_RESOURCE_NAME", "")
_remote_agent = None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MAX_BODY_SIZE = int(os.environ.get("MAX_BODY_SIZE", str(2 * 1024 * 1024)))  # 2MB

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


def _security_headers() -> dict:
    """CSP + security headers."""
    return {
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "form-action 'self'; "
            "upgrade-insecure-requests"
        ),
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }


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
# Agent Engine circuit breaker
# ---------------------------------------------------------------------------
class _AgentCB:
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

    @property
    def state(self) -> str:
        with self._lock:
            return self._state


_agent_cb = _AgentCB(threshold=3, recovery=30)

# ---------------------------------------------------------------------------
# Rate limiter (IP hash sliding window)
# ---------------------------------------------------------------------------
_RATE_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", str(4 * 3600)))
_RATE_MAX = int(os.environ.get("RATE_LIMIT_MAX", "100"))
_rate_store: dict = {}
_rate_lock = threading.Lock()
_RATE_STORE_MAX = 5000


def _ip_hash(request) -> str:
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
    ip = ip.split(",")[0].strip()
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


def _check_rate_limit(ip_h: str) -> bool:
    now = time.time()
    cutoff = now - _RATE_WINDOW
    with _rate_lock:
        if len(_rate_store) > _RATE_STORE_MAX:
            stale = [k for k, ts in _rate_store.items() if not ts or ts[-1] < cutoff]
            for k in stale:
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
# Latency metrics (instance-scoped, rolling window)
# ---------------------------------------------------------------------------
_METRICS_LOCK = threading.Lock()
_LATENCY_SAMPLES: list = []  # ms values
_METRICS_MAX_SAMPLES = 500
_METRICS_TOTAL_REQUESTS = 0
_METRICS_TOTAL_ERRORS = 0


def _record_latency(ms: float) -> None:
    global _METRICS_TOTAL_REQUESTS
    with _METRICS_LOCK:
        _LATENCY_SAMPLES.append(ms)
        if len(_LATENCY_SAMPLES) > _METRICS_MAX_SAMPLES:
            _LATENCY_SAMPLES.pop(0)
        _METRICS_TOTAL_REQUESTS += 1


def _record_error() -> None:
    global _METRICS_TOTAL_ERRORS
    with _METRICS_LOCK:
        _METRICS_TOTAL_ERRORS += 1


def _get_metrics() -> dict:
    with _METRICS_LOCK:
        samples = list(_LATENCY_SAMPLES)
        total = _METRICS_TOTAL_REQUESTS
        errors = _METRICS_TOTAL_ERRORS
    if not samples:
        return {
            "total_requests": total,
            "total_errors": errors,
            "latency_p50_ms": 0, "latency_p95_ms": 0, "latency_p99_ms": 0,
        }
    samples.sort()
    n = len(samples)

    def _percentile(p):
        idx = min(int(math.ceil(p / 100.0 * n)) - 1, n - 1)
        return round(samples[max(idx, 0)], 1)

    return {
        "total_requests": total,
        "total_errors": errors,
        "sample_count": n,
        "latency_p50_ms": _percentile(50),
        "latency_p95_ms": _percentile(95),
        "latency_p99_ms": _percentile(99),
        "latency_avg_ms": round(sum(samples) / n, 1),
    }


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------
def _audit(event_type: str, payload: dict) -> None:
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
    global _remote_agent
    if _remote_agent is None:
        import vertexai
        from vertexai import agent_engines
        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "lawmadi-db")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-northeast3")
        vertexai.init(project=project, location=location)
        _remote_agent = agent_engines.get(AGENT_RESOURCE_NAME)
    return _remote_agent


def _extract_leader_from_response(text: str) -> str:
    m = re.search(r"\b(L\d{2})\b", text[:200])
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Common pre-checks
# ---------------------------------------------------------------------------
def _pre_check(request, ch: dict):
    """Auth, rate limit, body size checks. Returns (error_response, ip_hash) or (None, ip_hash)."""
    # Auth
    if not _verify_auth(request):
        return (
            json.dumps({"status": "error", "response": "인증 실패"}),
            401, {**ch, "Content-Type": "application/json"},
        ), ""

    # Rate limit
    ip_h = _ip_hash(request)
    if not _check_rate_limit(ip_h):
        _audit("rate_limited", {"ip_hash": ip_h})
        return (
            json.dumps({"status": "error", "response": "요청 한도를 초과했습니다."}, ensure_ascii=False),
            429, {**ch, "Content-Type": "application/json; charset=utf-8"},
        ), ip_h

    # Body size
    content_length = request.content_length or 0
    if content_length > _MAX_BODY_SIZE:
        return (
            json.dumps({"status": "error", "response": "요청이 너무 큽니다."}),
            413, {**ch, "Content-Type": "application/json"},
        ), ip_h

    # CB
    if not _agent_cb.allow():
        _audit("agent_cb_open", {"ip_hash": ip_h})
        return (
            json.dumps({"status": "error", "response": "서비스가 일시적으로 불안정합니다."}, ensure_ascii=False),
            503, {**ch, "Content-Type": "application/json; charset=utf-8"},
        ), ip_h

    return None, ip_h


# ---------------------------------------------------------------------------
# /api/ask — JSON response
# ---------------------------------------------------------------------------
def _handle_ask(request, ch: dict):
    err, ip_h = _pre_check(request, ch)
    if err:
        return err

    try:
        body = request.get_json(silent=True) or {}
    except Exception:
        body = {}

    query = body.get("query", "").strip()
    if not query:
        return (
            json.dumps({"status": "error", "response": "질문을 입력해주세요."}),
            400, {**ch, "Content-Type": "application/json"},
        )

    user_id = body.get("user_id", "anonymous")
    start_time = time.time()
    model = get_model()

    try:
        agent = _get_agent()
        response_text = ""
        tool_calls_info = []

        import asyncio

        async def _query():
            nonlocal response_text
            async for event in agent.async_stream_query(
                user_id=user_id, message=query,
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
        _record_latency(elapsed * 1000)

        leader_id, leader_name = "", ""
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

        _audit("query_success", {
            "query": query[:2000],
            "response_sha256": hashlib.sha256(response_text.encode()).hexdigest()[:16],
            "leader": leader_id, "latency_ms": int(elapsed * 1000), "model": model,
        })

        return (
            json.dumps(result, ensure_ascii=False), 200,
            {**ch, **_security_headers(), "Content-Type": "application/json; charset=utf-8"},
        )

    except Exception as e:
        elapsed = round(time.time() - start_time, 2)
        _agent_cb.failure()
        _record_error()

        if is_quota_error(e):
            new_model = on_quota_error()
            _audit("quota_error", {"model": model, "new_model": new_model})
            return (
                json.dumps({"status": "error", "response": "모델 할당량 초과로 전환 중입니다."}, ensure_ascii=False),
                503, {**ch, "Content-Type": "application/json; charset=utf-8"},
            )

        logger.error(f"Agent Engine query failed: {e}")
        _audit("query_error", {"query": query[:2000], "error": str(e)[:500], "model": model})

        return (
            json.dumps({
                "status": "error",
                "response": "죄송합니다. 일시적인 오류가 발생했습니다.",
                "meta": {"error": str(e), "elapsed_seconds": elapsed},
            }, ensure_ascii=False),
            500, {**ch, **_security_headers(), "Content-Type": "application/json; charset=utf-8"},
        )


# ---------------------------------------------------------------------------
# /api/ask-stream — SSE streaming response
# ---------------------------------------------------------------------------
def _handle_ask_stream(request, ch: dict):
    err, ip_h = _pre_check(request, ch)
    if err:
        return err

    try:
        body = request.get_json(silent=True) or {}
    except Exception:
        body = {}

    query = body.get("query", "").strip()
    if not query:
        return (
            json.dumps({"status": "error", "response": "질문을 입력해주세요."}),
            400, {**ch, "Content-Type": "application/json"},
        )

    user_id = body.get("user_id", "anonymous")
    model = get_model()

    def _sse_generator():
        import asyncio

        start_time = time.time()
        response_text = ""
        tool_calls_info = []

        async def _stream():
            nonlocal response_text
            agent = _get_agent()
            async for event in agent.async_stream_query(
                user_id=user_id, message=query,
            ):
                if hasattr(event, "content") and event.content:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            response_text += part.text
                            yield part.text
                        if hasattr(part, "function_response"):
                            fr = part.function_response
                            if hasattr(fr, "response") and isinstance(fr.response, dict):
                                if "leader_id" in fr.response:
                                    tool_calls_info.append(fr.response)

        try:
            # SSE: deliberation_start
            yield f"event: deliberation_start\ndata: {json.dumps({'status': 'starting'})}\n\n"

            loop = asyncio.new_event_loop()
            gen = _stream()

            async def _collect():
                chunks = []
                async for chunk in gen:
                    chunks.append(chunk)
                return chunks

            chunks = loop.run_until_complete(_collect())
            loop.close()

            # SSE: content chunks
            for chunk in chunks:
                yield f"data: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"

            elapsed = round(time.time() - start_time, 2)
            _agent_cb.success()
            _record_latency(elapsed * 1000)

            leader_id, leader_name = "", ""
            for info in tool_calls_info:
                if "leader_id" in info:
                    leader_id = info.get("leader_id", "")
                    leader_name = info.get("leader_name", "")
                    break
            if not leader_id:
                leader_id = _extract_leader_from_response(response_text)

            # SSE: done
            done_data = {
                "status": "ok", "leader": leader_id,
                "meta": {"model": model, "elapsed_seconds": elapsed, "leader_name": leader_name},
            }
            yield f"event: done\ndata: {json.dumps(done_data, ensure_ascii=False)}\n\n"

            _audit("stream_success", {
                "query": query[:2000], "leader": leader_id,
                "latency_ms": int(elapsed * 1000), "model": model,
            })

        except Exception as e:
            _agent_cb.failure()
            _record_error()
            logger.error(f"SSE stream error: {e}")
            err_data = {"status": "error", "error": str(e)[:500]}
            yield f"event: error\ndata: {json.dumps(err_data)}\n\n"

    sse_headers = {
        **ch,
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return (_sse_generator(), 200, sse_headers)


# ---------------------------------------------------------------------------
# /api/ask-expert — 특정 리더 지정 질의
# ---------------------------------------------------------------------------
def _handle_ask_expert(request, ch: dict):
    err, ip_h = _pre_check(request, ch)
    if err:
        return err

    try:
        body = request.get_json(silent=True) or {}
    except Exception:
        body = {}

    query = body.get("query", "").strip()
    leader_id = body.get("leader_id", "").strip()
    if not query:
        return (
            json.dumps({"status": "error", "response": "질문을 입력해주세요."}),
            400, {**ch, "Content-Type": "application/json"},
        )
    if not leader_id or not re.match(r"^L\d{2}$", leader_id):
        return (
            json.dumps({"status": "error", "response": "유효한 leader_id를 입력해주세요 (L01~L60)."}),
            400, {**ch, "Content-Type": "application/json"},
        )

    user_id = body.get("user_id", "anonymous")
    # 리더 지정 메시지로 Agent에게 전달
    expert_query = f"[리더지정: {leader_id}] {query}"

    start_time = time.time()
    model = get_model()

    try:
        agent = _get_agent()
        response_text = ""

        import asyncio

        async def _query():
            nonlocal response_text
            async for event in agent.async_stream_query(
                user_id=user_id, message=expert_query,
            ):
                if hasattr(event, "content") and event.content:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            response_text += part.text

        asyncio.run(_query())

        elapsed = round(time.time() - start_time, 2)
        _agent_cb.success()
        _record_latency(elapsed * 1000)

        result = {
            "status": "ok",
            "response": response_text,
            "leader": leader_id,
            "meta": {"model": model, "elapsed_seconds": elapsed, "engine": "vertex-ai-agent-engine"},
        }

        _audit("expert_query", {"query": query[:2000], "leader": leader_id, "model": model})

        return (
            json.dumps(result, ensure_ascii=False), 200,
            {**ch, **_security_headers(), "Content-Type": "application/json; charset=utf-8"},
        )

    except Exception as e:
        elapsed = round(time.time() - start_time, 2)
        _agent_cb.failure()
        _record_error()
        logger.error(f"Expert query failed: {e}")
        return (
            json.dumps({
                "status": "error", "response": "오류가 발생했습니다.",
                "meta": {"error": str(e), "elapsed_seconds": elapsed},
            }, ensure_ascii=False),
            500, {**ch, "Content-Type": "application/json; charset=utf-8"},
        )


# ---------------------------------------------------------------------------
# /api/admin/metrics — p50/p95/p99 latency + system status
# ---------------------------------------------------------------------------
def _handle_metrics(request, ch: dict):
    if not _verify_auth(request):
        return (json.dumps({"status": "error"}), 401, {**ch, "Content-Type": "application/json"})

    metrics = _get_metrics()
    metrics["model"] = get_model_status()
    metrics["agent_cb_state"] = _agent_cb.state

    return (
        json.dumps(metrics, ensure_ascii=False), 200,
        {**ch, "Content-Type": "application/json; charset=utf-8"},
    )


# ---------------------------------------------------------------------------
# Router: single entry point for Cloud Functions
# ---------------------------------------------------------------------------
@functions_framework.http
def handle_request(request):
    """Main router — dispatches to /api/ask, /api/ask-stream, /api/ask-expert, /api/admin/metrics."""
    ch = _cors_headers(request)

    # CORS preflight
    if request.method == "OPTIONS":
        return ("", 204, {
            **ch,
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        })

    path = request.path.rstrip("/")

    if path == "/api/ask-stream" and request.method == "POST":
        return _handle_ask_stream(request, ch)
    elif path == "/api/ask-expert" and request.method == "POST":
        return _handle_ask_expert(request, ch)
    elif path == "/api/admin/metrics" and request.method == "GET":
        return _handle_metrics(request, ch)
    elif path in ("/api/ask", "/") and request.method == "POST":
        return _handle_ask(request, ch)
    else:
        return (
            json.dumps({"status": "error", "response": "Not Found"}),
            404, {**ch, "Content-Type": "application/json"},
        )


# Backward compat: keep handle_ask as alias
handle_ask = handle_request
