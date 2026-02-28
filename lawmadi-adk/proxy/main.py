"""
Lawmadi OS ADK — Cloud Functions Gen2 프록시.

Firebase Hosting → Cloud Functions → Vertex AI Agent Engine
무료 tier 범위 내에서 작동.

배포:
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

import os
import hmac
import json
import asyncio
import logging
import re
import time
import functions_framework

logger = logging.getLogger("LawmadiProxy")

# Agent Engine 리소스 (배포 후 설정)
AGENT_RESOURCE_NAME = os.environ.get("AGENT_RESOURCE_NAME", "")
_remote_agent = None

# ── CORS 허용 도메인 (메인 앱과 동일) ──
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
    """요청 Origin이 허용 목록에 있으면 반환, 아니면 빈 문자열."""
    origin = request.headers.get("Origin", "")
    if origin in _ALLOWED_ORIGINS:
        return origin
    return ""


def _cors_headers(request) -> dict:
    """CORS 응답 헤더 생성."""
    origin = _get_cors_origin(request)
    if origin:
        return {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}
    return {}


def _verify_auth(request) -> bool:
    """Bearer 토큰 인증 검증. INTERNAL_API_KEY 미설정 시 통과(개발 환경)."""
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


def _get_agent():
    """Lazy init: Agent Engine 클라이언트."""
    global _remote_agent
    if _remote_agent is None:
        import vertexai
        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "lawmadi-v50")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-northeast3")
        client = vertexai.Client(project=project, location=location)
        _remote_agent = client.agent_engines.get(AGENT_RESOURCE_NAME)
    return _remote_agent


def _extract_leader_from_response(text: str) -> str:
    """응답 텍스트에서 리더 정보 추출 시도."""
    # Agent가 tool_call 결과로 리더 ID를 포함했는지 확인
    m = re.search(r"\b(L\d{2})\b", text[:200])
    return m.group(1) if m else ""


@functions_framework.http
def handle_ask(request):
    """POST /api/ask → Agent Engine 쿼리.

    요청 body: {"query": "...", "user_id": "..."}
    응답: {"response": "...", "leader": "...", "status": "ok", "meta": {...}}
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

    # 인증 검증
    if not _verify_auth(request):
        return (
            json.dumps({"status": "error", "response": "인증 실패"}),
            401,
            {**ch, "Content-Type": "application/json"},
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

    try:
        agent = _get_agent()

        # Agent Engine 쿼리
        response_text = ""
        tool_calls_info = []

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
                        # tool call 결과에서 리더 정보 추출
                        if hasattr(part, "function_response"):
                            fr = part.function_response
                            if hasattr(fr, "response") and isinstance(fr.response, dict):
                                if "leader_id" in fr.response:
                                    tool_calls_info.append(fr.response)

        asyncio.run(_query())

        elapsed = round(time.time() - start_time, 2)

        # classify_query tool 결과에서 리더 정보 추출
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
                "model": "gemini-2.5-flash",
                "elapsed_seconds": elapsed,
                "engine": "vertex-ai-agent-engine",
                "leader_name": leader_name,
            },
        }

        return (
            json.dumps(result, ensure_ascii=False),
            200,
            {**ch, "Content-Type": "application/json; charset=utf-8"},
        )

    except Exception as e:
        logger.error(f"Agent Engine 쿼리 실패: {e}")
        elapsed = round(time.time() - start_time, 2)

        return (
            json.dumps(
                {
                    "status": "error",
                    "response": "죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                    "meta": {"error": str(e), "elapsed_seconds": elapsed},
                },
                ensure_ascii=False,
            ),
            500,
            {**ch, "Content-Type": "application/json; charset=utf-8"},
        )
