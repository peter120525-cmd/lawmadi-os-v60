"""
Lawmadi OS v60 — Legal analysis routes.
/ask, /ask-stream, /ask-expert, /search, /trending
main.py에서 분리됨 (A8).
"""
import os
import re
import json
import uuid
import time
import asyncio
import logging
import datetime
import traceback
from typing import Any, Callable, Dict, List, Optional, Union

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from google.genai import types as genai_types

from core.constants import OS_VERSION, DEFAULT_GEMINI_MODEL
from utils.helpers import (
    _safe_extract_gemini_text,
    _remove_think_blocks,
    _now_iso,
    _is_low_signal,
)
from core.constitutional import validate_constitutional_compliance
from core.classifier import (
    _claude_analyze_query,
    _fallback_tier_classification,
    select_swarm_leader,
)
from core.pipeline import _run_legal_pipeline
from prompts.system_instructions import build_system_instruction as _build_system_instruction
from tools.drf_tools import (
    search_law_drf,
    search_precedents_drf,
    search_admrul_drf,
    search_expc_drf,
    search_constitutional_drf,
    search_ordinance_drf,
    search_legal_term_drf,
    search_admin_appeals_drf,
    search_treaty_drf,
)

router = APIRouter()
logger = logging.getLogger("LawmadiOS.Legal")

# ---------------------------------------------------------------------------
# Module-level state (injected via set_dependencies at startup)
# ---------------------------------------------------------------------------
_RUNTIME: Dict[str, Any] = {}
_METRICS: Dict[str, Any] = {}
_LEADER_REGISTRY: Dict[str, Any] = {}
_limiter = None

# Function references injected from main.py
_check_rate_limit_fn: Optional[Callable] = None
_rate_limit_response_fn: Optional[Callable] = None
_check_response_cache_fn: Optional[Callable] = None
_match_ssot_sources_fn: Optional[Callable] = None
_resolve_leader_from_ssot_fn: Optional[Callable] = None
_ensure_genai_client_fn: Optional[Callable] = None
_classify_gemini_error_fn: Optional[Callable] = None
_remove_markdown_tables_fn: Optional[Callable] = None
_remove_separator_lines_fn: Optional[Callable] = None
_compute_quality_meta_fn: Optional[Callable] = None
_audit_fn: Optional[Callable] = None
_get_client_ip_fn: Optional[Callable] = None
_sha256_fn: Optional[Callable] = None
_optional_import_fn: Optional[Callable] = None


def set_dependencies(
    runtime: Dict[str, Any],
    metrics: Dict[str, Any],
    leader_registry: Dict[str, Any],
    limiter,
    *,
    check_rate_limit,
    rate_limit_response,
    check_response_cache,
    match_ssot_sources,
    resolve_leader_from_ssot,
    ensure_genai_client,
    classify_gemini_error,
    remove_markdown_tables,
    remove_separator_lines,
    compute_quality_meta,
    audit_fn,
    get_client_ip,
    sha256_fn,
    optional_import_fn,
):
    """Inject shared runtime objects and utility functions from main.py."""
    global _RUNTIME, _METRICS, _LEADER_REGISTRY, _limiter
    global _check_rate_limit_fn, _rate_limit_response_fn, _check_response_cache_fn
    global _match_ssot_sources_fn, _resolve_leader_from_ssot_fn, _ensure_genai_client_fn
    global _classify_gemini_error_fn, _remove_markdown_tables_fn, _remove_separator_lines_fn
    global _compute_quality_meta_fn, _audit_fn, _get_client_ip_fn, _sha256_fn, _optional_import_fn

    _RUNTIME = runtime
    _METRICS = metrics
    _LEADER_REGISTRY = leader_registry
    _limiter = limiter
    _check_rate_limit_fn = check_rate_limit
    _rate_limit_response_fn = rate_limit_response
    _check_response_cache_fn = check_response_cache
    _match_ssot_sources_fn = match_ssot_sources
    _resolve_leader_from_ssot_fn = resolve_leader_from_ssot
    _ensure_genai_client_fn = ensure_genai_client
    _classify_gemini_error_fn = classify_gemini_error
    _remove_markdown_tables_fn = remove_markdown_tables
    _remove_separator_lines_fn = remove_separator_lines
    _compute_quality_meta_fn = compute_quality_meta
    _audit_fn = audit_fn
    _get_client_ip_fn = get_client_ip
    _sha256_fn = sha256_fn
    _optional_import_fn = optional_import_fn


# ---------------------------------------------------------------------------
# DRF tool list builder
# ---------------------------------------------------------------------------
def _get_drf_tools() -> list:
    """Return DRF tool function list if SSOT is available."""
    if not _RUNTIME.get("drf_healthy", False):
        return []
    return [
        search_law_drf,
        search_precedents_drf,
        search_admrul_drf,
        search_expc_drf,
        search_constitutional_drf,
        search_ordinance_drf,
        search_legal_term_drf,
        search_admin_appeals_drf,
        search_treaty_drf,
    ]


# =============================================================
# POST /ask
# =============================================================

@router.post("/ask")
async def ask(request: Request):

    # 4시간당 10회 제한
    rate_check = _check_rate_limit_fn(request)
    if rate_check is not True:
        return _rate_limit_response_fn(rate_check.get("retry_at_kst", ""))

    trace = str(uuid.uuid4())
    start_time = time.time()

    try:
        body = await request.body()
        _MAX_BODY_SIZE = 128 * 1024
        if len(body) > _MAX_BODY_SIZE:
            return JSONResponse(status_code=413, content={"error": "요청이 너무 큽니다 (128KB 제한)", "blocked": True})

        data = json.loads(body)
        query = (data.get("query", "") or "").strip()
        raw_history = data.get("history", [])
        lang = (data.get("lang", "") or "").strip().lower()

        # 입력 길이 제한 (DoS 방지)
        MAX_QUERY_LEN = 2000
        if len(query) > MAX_QUERY_LEN:
            query = query[:MAX_QUERY_LEN]

        # history 배열 크기 사전 제한
        if not isinstance(raw_history, list):
            raw_history = []
        raw_history = raw_history[-6:]

        # 대화 히스토리 → Gemini Content 형식 변환 (최근 6턴)
        gemini_history = []
        for msg in raw_history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user" and content:
                gemini_history.append({"role": "user", "parts": [{"text": content[:MAX_QUERY_LEN]}]})
            elif role == "assistant" and content:
                gemini_history.append({"role": "model", "parts": [{"text": content[:2000]}]})

        # IP 주소를 사용자 ID로 사용 (자동 추출)
        visitor_id = _get_client_ip_fn(request)
        logger.info(f"🔍 Request from IP: {visitor_id}")

        config = _RUNTIME.get("config", {})

        # -------------------------------------------------
        # 0) Low Signal 차단
        # -------------------------------------------------
        if _is_low_signal(query):
            if lang == "en":
                msg = (
                    "[Yuna (CCO) Notice]\n\n"
                    "Hi! I'm Yuna. 😊\n\n"
                    "A test input has been detected. The server is running normally.\n\n"
                    "To provide a more accurate answer, please share:\n"
                    "- Case overview (what happened)\n"
                    "- Dates / parties involved / supporting documents\n"
                    "- Desired outcome\n\n"
                    "If you have a legal concern, please ask a specific question.\n"
                    "60 expert leaders are here to help!\n"
                )
            else:
                msg = (
                    "[유나 (CCO) 안내]\n\n"
                    "안녕하세요! 유나입니다. 😊\n\n"
                    "테스트 입력이 감지되었습니다. 서버는 정상 동작 중이에요.\n\n"
                    "더 정확한 답변을 드리기 위해 다음 정보를 알려주시면 좋겠어요:\n"
                    "- 사건 개요 (어떤 상황인지)\n"
                    "- 날짜/당사자/증빙 자료\n"
                    "- 원하시는 결과\n\n"
                    "법률 문제로 걱정이 있으시다면, 구체적으로 질문해 주세요.\n"
                    "60명의 전문 리더가 함께 도와드릴게요!\n"
                )
            _audit_fn("ask_low_signal", {"query": query, "status": "SKIPPED", "latency_ms": 0})
            return {"trace_id": trace, "response": msg, "leader": "유나", "leader_specialty": "콘텐츠 설계", "status": "SUCCESS"}

        # -------------------------------------------------
        # 0.3) 응답 캐시 확인 (정확 일치 → 즉시 반환)
        # -------------------------------------------------
        cached = _check_response_cache_fn(query)
        if cached:
            latency = int((time.time() - start_time) * 1000)
            logger.info(f"⚡ [Cache HIT] leader={cached.get('leader', '?')} latency={latency}ms")
            _audit_fn("ask_cache_hit", {"query": query, "leader": cached.get("leader", "?"), "status": "CACHE_HIT", "latency_ms": latency})
            return {
                "trace_id": trace,
                "response": cached.get("response", ""),
                "leader": cached.get("leader", "마디"),
                "leader_specialty": cached.get("leader_specialty", "통합"),
                "tier": cached.get("tier", 1),
                "status": "SUCCESS",
                "latency_ms": latency,
                "swarm_mode": False,
                "constitutional_check": "PASS",
                "ssot_sources": cached.get("ssot_sources", []),
                "meta": cached.get("meta", {}),
            }

        # -------------------------------------------------
        # 0.5) Gemini 키 점검
        # -------------------------------------------------
        if not os.getenv("GEMINI_KEY"):
            _audit_fn("ask_fail_closed", {"query": query, "status": "FAIL_CLOSED", "leader": "SYSTEM"})
            raise HTTPException(status_code=503, detail="⚠️ GEMINI_KEY 미설정으로 추론이 비활성화되었습니다.")

        # -------------------------------------------------
        # 1) Security Guard
        # -------------------------------------------------
        guard = _RUNTIME.get("guard")
        if guard:
            check_result = guard.check(query)

            if check_result == "CRISIS":
                safety_config = config.get("security_layer", {}).get("safety", {})
                crisis_res = safety_config.get("crisis_resources", {})
                if lang == "en":
                    lines = ["🚨 Your safety is the top priority.\n"]
                    for label, number in crisis_res.items():
                        lines.append(f"  📞 {label}: {number}")
                    lines.append("\nPlease contact the above professional organizations immediately.")
                else:
                    lines = ["🚨 당신의 안전이 가장 중요합니다.\n"]
                    for label, number in crisis_res.items():
                        lines.append(f"  📞 {label}: {number}")
                    lines.append("\n위 전문 기관으로 지금 바로 연락하세요.")
                _audit_fn("ask_crisis", {"query": query, "status": "CRISIS", "leader": "SAFETY"})
                return {"trace_id": trace, "response": "\n".join(lines), "leader": "SAFETY", "status": "CRISIS"}

            if check_result is False:
                blocked_msg = "🚫 Blocked by security policy." if lang == "en" else "🚫 보안 정책에 의해 차단되었습니다."
                _audit_fn("ask_blocked", {"query": query, "status": "BLOCKED", "leader": "GUARD"})
                return {"trace_id": trace, "response": blocked_msg, "status": "BLOCKED"}

        # -------------------------------------------------
        # 2) 🎯 TIER ROUTER: Claude 분석 → 티어 분류 → 리더 배정
        # -------------------------------------------------
        clevel = _RUNTIME.get("clevel_handler")
        clevel_decision = None
        if clevel:
            clevel_decision = clevel.should_invoke_clevel(query)
            if clevel_decision and clevel_decision.get("invoke"):
                logger.info(f"🎯 C-Level 호출: {clevel_decision.get('executive_id')} - {clevel_decision.get('reason')}")

        # -------------------------------------------------
        # 3) Dual SSOT 가용 여부
        # -------------------------------------------------
        ssot_available = _RUNTIME.get("drf_healthy", False)

        # -------------------------------------------------
        # 3.5) LLM Tool 설정 (SSOT 살아있을 때만 활성화)
        # -------------------------------------------------
        tools = _get_drf_tools()

        now_kst = _now_iso()

        # -------------------------------------------------
        # 4) 📦 SSOT 캐시 매칭 → Claude 분석 → 리더 배정
        # -------------------------------------------------
        matched_sources = _match_ssot_sources_fn(query, top_k=5)
        if matched_sources:
            _src_strs = [s["type"] + ":" + s["law"] for s in matched_sources[:3]]
            logger.info(f"📦 [Cache] 매칭: {', '.join(_src_strs)}")

        analysis = await _claude_analyze_query(query)
        if not analysis:
            analysis = _fallback_tier_classification(query)
            logger.info(f"🔄 키워드 기반 fallback 분류: tier={analysis['tier']}")

        tier = analysis.get("tier", 1)
        leader_name = analysis.get("leader_name", "마디")
        leader_specialty = analysis.get("leader_specialty", "통합")
        is_legal = analysis.get("is_legal", True)
        is_document = analysis.get("is_document", False)
        swarm_mode = False

        # SSOT 기반 리더 검증/보정
        if matched_sources and is_legal:
            ssot_leader = _resolve_leader_from_ssot_fn(matched_sources)
            if ssot_leader and ssot_leader["name"] != leader_name:
                logger.info(f"🔄 [SSOT Override] {leader_name}→{ssot_leader['name']}({ssot_leader['specialty']})")
                leader_name = ssot_leader["name"]
                leader_specialty = ssot_leader["specialty"]
                analysis["leader_name"] = leader_name
                analysis["leader_specialty"] = leader_specialty

        logger.info(f"🎯 [Tier {tier}] leader={leader_name}({leader_specialty}), "
                    f"legal={is_legal}, document={is_document}")

        # -------------------------------------------------
        # 4.1) 비법률 즉시 응답
        # -------------------------------------------------
        if not is_legal:
            if lang == "en":
                instant_msg = (
                    f"[Yuna (CCO) Content Design]\n\n"
                    "## 💡 Key Answer\n"
                    "Your question appears to be a general inquiry rather than a legal matter. "
                    "As a legal analysis system, I may not be able to provide a specialized answer, "
                    "but let me briefly guide you.\n\n"
                    "## 📌 Key Points\n"
                    "• Lawmadi OS is a **Korean legal analysis system**\n"
                    "• 60 expert leaders provide detailed analysis by legal field\n"
                    "• We cover lease, divorce, inheritance, criminal, labor law, and more\n\n"
                    "## 🔍 Learn More\n"
                    "If you have a legal concern, please ask a specific question! "
                    "For example, \"I can't get my lease deposit back\" — "
                    "an expert leader will begin analysis immediately."
                )
            else:
                instant_msg = (
                    f"[유나 (CCO) 콘텐츠 설계]\n\n"
                    "## 💡 핵심 답변\n"
                    "말씀하신 내용은 법률 분야가 아닌 일반 질문으로 판단됩니다. "
                    "저는 법률 분석 시스템이라 전문적인 답변이 어려울 수 있지만, "
                    "간단히 안내드릴게요.\n\n"
                    "## 📌 주요 포인트\n"
                    "• Lawmadi OS는 **대한민국 법률 분석 전문 시스템**입니다\n"
                    "• 60명의 전문 리더가 법률 분야별로 정밀 분석해 드려요\n"
                    "• 임대차, 이혼, 상속, 형사, 노동법 등 다양한 분야를 다룹니다\n\n"
                    "## 🔍 더 알아보기\n"
                    "법률과 관련된 고민이 있으시다면 구체적으로 질문해 주세요! "
                    "예를 들어 \"전세 보증금을 못 돌려받고 있어요\" 같은 질문이면 "
                    "전문 리더가 즉시 분석을 시작합니다."
                )
            latency = int((time.time() - start_time) * 1000)
            _METRICS["requests"] += 1
            return JSONResponse(content={
                "trace_id": trace,
                "response": instant_msg,
                "leader": "유나",
                "leader_specialty": "콘텐츠 설계",
                "tier": 0,
                "status": "SUCCESS",
                "latency_ms": latency,
                "swarm_mode": False,
            })

        # -------------------------------------------------
        # 4.2) C-Level 직접 호출 처리
        # -------------------------------------------------
        if clevel_decision and clevel_decision.get("mode") == "direct":
            exec_id = clevel_decision.get("executive_id")
            logger.info(f"🎯 C-Level 직접 모드: {exec_id}")
            clevel_instruction = clevel.get_clevel_system_instruction(exec_id, _build_system_instruction("general"))
            gc = _ensure_genai_client_fn(_RUNTIME)
            model_name = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
            chat = gc.chats.create(
                model=model_name,
                config=genai_types.GenerateContentConfig(
                    tools=tools,
                    system_instruction=clevel_instruction,
                    max_output_tokens=3000,
                    automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=False),
                ),
                history=gemini_history,
            )
            resp = chat.send_message(f"now_kst={now_kst}\nssot_available={ssot_available}\n사용자 질문: {query}")
            final_text = _safe_extract_gemini_text(resp)
            leader_name = clevel.executives.get(exec_id, {}).get("name", exec_id)
            leader_specialty = clevel.executives.get(exec_id, {}).get("role", exec_id)

        # -------------------------------------------------
        # 5) 🎯 5-Stage Legal Pipeline
        # -------------------------------------------------
        else:
            final_text = await _run_legal_pipeline(
                query, analysis, tools, gemini_history, now_kst, ssot_available, lang=lang, mode="general"
            )

        # -------------------------------------------------
        # 5.5) 담당 리더 정보 헤더 삽입
        # -------------------------------------------------
        if lang == "en":
            leader_header = f"**Assigned: {leader_name} ({leader_specialty} Expert)**\n\n"
        else:
            leader_header = f"**담당: {leader_name} ({leader_specialty} 전문)**\n\n"
        if not final_text.startswith(f"[{leader_name}") and not final_text.startswith(f"**담당:") and not final_text.startswith(f"**Assigned:"):
            final_text = leader_header + final_text

        # -------------------------------------------------
        # 6) 규칙 기반 헌법 준수 검증
        # -------------------------------------------------
        if not validate_constitutional_compliance(final_text):
            gov_msg = "⚠️ Response restricted by system integrity policy." if lang == "en" else "⚠️ 시스템 무결성 정책에 의해 답변이 제한되었습니다."
            _audit_fn("ask_fail_closed", {"query": query, "status": "GOVERNANCE", "leader": leader_name})
            return {"trace_id": trace, "response": gov_msg, "status": "FAIL_CLOSED"}

        const_check = {"passed": True}  # Stage 5에서 이미 처리됨

        latency_ms = int((time.time() - start_time) * 1000)

        # 느린 쿼리 로깅
        if latency_ms > 10000:
            logger.warning(f"🐌 [SLOW_REQUEST] {latency_ms}ms | tier={tier} | query={query[:80]} | leader={leader_name}")

        # -------------------------------------------------
        # 7) Metrics
        # -------------------------------------------------
        _METRICS["requests"] += 1
        req_count = _METRICS["requests"]
        prev_avg = _METRICS["avg_latency_ms"]
        _METRICS["avg_latency_ms"] = int(((prev_avg * (req_count - 1)) + latency_ms) / max(req_count, 1))

        # -------------------------------------------------
        # 8) Audit
        # -------------------------------------------------
        _audit_fn("ask", {
            "query": query,
            "leader": leader_name,
            "tier": tier,
            "complexity": analysis.get("complexity", ""),
            "is_document": is_document,
            "status": "SUCCESS",
            "latency_ms": latency_ms,
            "response_sha256": _sha256_fn(final_text),
            "swarm_mode": False,
            "cache_sources": [f"{s['type']}:{s['law']}" for s in matched_sources[:3]],
        })

        # -------------------------------------------------
        # 9) 백그라운드 검증 + DB 저장
        # -------------------------------------------------
        async def _background_verify_and_save():
            """백그라운드에서 SSOT 검증 + DB 저장 수행"""
            try:
                verifier_module = _optional_import_fn("engines.response_verifier")
                if verifier_module:
                    verifier = verifier_module.get_verifier()
                    loop = asyncio.get_event_loop()
                    verification_result = await loop.run_in_executor(
                        None,
                        lambda: verifier.verify_response(
                            user_query=query,
                            gemini_response=final_text,
                            tools_used=[],
                            tool_results=[]
                        )
                    )
                    v_result = verification_result.get("result", "SKIP")
                    v_score = verification_result.get("ssot_compliance_score", 0)
                    v_issues = verification_result.get("issues", [])
                    if v_result == "FAIL":
                        logger.warning(f"🚨 [SSOT 검증 실패] 점수: {v_score}, 문제: {v_issues}")
                    else:
                        logger.info(f"✅ [SSOT 검증 통과] 점수: {v_score}")

                    db_client_v2 = _optional_import_fn("connectors.db_client_v2")
                    if db_client_v2 and hasattr(db_client_v2, "save_verification_result"):
                        await loop.run_in_executor(
                            None,
                            lambda: db_client_v2.save_verification_result(
                                session_id=trace, user_query=query, gemini_response=final_text,
                                tools_used=[], tool_results=[],
                                verification_result=v_result, ssot_compliance_score=v_score,
                                issues_found=v_issues, claude_feedback=verification_result.get("feedback", "")
                            )
                        )
            except Exception as verify_error:
                logger.warning(f"⚠️ [Verification] 백그라운드 검증 실패 (무시): {verify_error}")

            try:
                db_client_v2 = _optional_import_fn("connectors.db_client_v2")
                if db_client_v2 and hasattr(db_client_v2, "save_chat_history"):
                    query_category = db_client_v2.classify_query_category(query)
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        lambda: db_client_v2.save_chat_history(
                            user_query=query, ai_response=final_text, leader=leader_name,
                            status="success", latency_ms=latency_ms, visitor_id=visitor_id,
                            swarm_mode=False, leaders_used=None, query_category=query_category
                        )
                    )
            except Exception as log_error:
                logger.warning(f"⚠️ [ChatHistory] 백그라운드 저장 실패 (무시): {log_error}")

        asyncio.create_task(_background_verify_and_save())

        # 후처리: think 블록 → 표 → 구분선 제거
        final_text_clean = _remove_think_blocks(final_text)
        final_text_clean = _remove_markdown_tables_fn(final_text_clean)
        final_text_clean = _remove_separator_lines_fn(final_text_clean)

        return {
            "trace_id": trace,
            "response": final_text_clean,
            "leader": leader_name,
            "leader_specialty": leader_specialty,
            "tier": tier,
            "status": "SUCCESS",
            "latency_ms": latency_ms,
            "swarm_mode": False,
            "constitutional_check": "PASS" if const_check.get("passed", True) else "WARNING",
            "ssot_sources": [f"{s['type']}:{s['law']}" for s in matched_sources[:3]] if matched_sources else [],
            "meta": _compute_quality_meta_fn(final_text_clean, matched_sources),
        }

    except Exception as e:
        _METRICS["errors"] += 1
        ref = datetime.datetime.now().strftime("%H%M%S")
        logger.error(f"💥 커널 에러 (trace={trace}, ref={ref}): {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        _audit_fn("ask_error", {"query": str(locals().get("query", "")), "status": "ERROR", "leader": "SYSTEM", "latency_ms": 0, "error_type": type(e).__name__})
        _lang = locals().get("lang", "")
        if _lang == "en":
            user_msg = f"⚠️ A system error occurred. Please try again shortly. (Ref: {ref})"
        else:
            user_msg = _classify_gemini_error_fn(e, ref)
        return {"trace_id": trace, "response": user_msg, "status": "ERROR"}


# =============================================================
# 🔄 SSE 스트리밍 응답 (/ask-stream)
# =============================================================

@router.post("/ask-stream")
async def ask_stream(request: Request):
    """SSE 스트리밍 엔드포인트 — 실시간 토큰 전송"""

    # 4시간당 10회 제한
    rate_check = _check_rate_limit_fn(request)
    if rate_check is not True:
        return _rate_limit_response_fn(rate_check.get("retry_at_kst", ""))

    trace = str(uuid.uuid4())
    start_time = time.time()

    try:
        body = await request.body()
        _MAX_BODY_SIZE = 128 * 1024
        if len(body) > _MAX_BODY_SIZE:
            async def _size_err():
                yield f"event: error\ndata: {json.dumps({'message': '요청이 너무 큽니다 (128KB 제한)'}, ensure_ascii=False)}\n\n"
            return StreamingResponse(_size_err(), media_type="text/event-stream")

        data = json.loads(body)
        query = (data.get("query", "") or "").strip()
        raw_history = data.get("history", [])
        lang = (data.get("lang", "") or "").strip().lower()
        stream_mode = (data.get("mode", "") or "").strip().lower() or "general"

        MAX_QUERY_LEN = 2000
        if len(query) > MAX_QUERY_LEN:
            query = query[:MAX_QUERY_LEN]

        if not isinstance(raw_history, list):
            raw_history = []
        raw_history = raw_history[-6:]

        gemini_history = []
        for msg in raw_history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user" and content:
                gemini_history.append({"role": "user", "parts": [{"text": content[:MAX_QUERY_LEN]}]})
            elif role == "assistant" and content:
                gemini_history.append({"role": "model", "parts": [{"text": content[:2000]}]})

        visitor_id = _get_client_ip_fn(request)
        config = _RUNTIME.get("config", {})

    except Exception as parse_err:
        logger.error(f"💥 요청 파싱 실패: {type(parse_err).__name__}: {parse_err}")
        async def _error_gen():
            yield f"event: error\ndata: {json.dumps({'message': f'요청 파싱 실패: {type(parse_err).__name__}'}, ensure_ascii=False)}\n\n"
        return StreamingResponse(_error_gen(), media_type="text/event-stream")

    # --- SSE generator ---
    async def _sse_generator():
        nonlocal query, raw_history, gemini_history, visitor_id, config, trace, start_time, lang, stream_mode

        final_text = ""
        leader_name = "유나"
        leader_specialty = "콘텐츠 설계"
        swarm_mode = False

        def _sse(event: str, payload: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

        async def _async_stream_chunks(sync_stream):
            """동기 스트림 이터레이터를 비동기로 소비 (이벤트 루프 블로킹 방지)"""
            q = asyncio.Queue()
            def _consume():
                try:
                    for chunk in sync_stream:
                        text_part = ""
                        if hasattr(chunk, 'text') and chunk.text:
                            text_part = chunk.text
                        elif hasattr(chunk, 'parts'):
                            for part in chunk.parts:
                                if hasattr(part, 'text') and part.text:
                                    text_part += part.text
                        if text_part:
                            q.put_nowait(text_part)
                    q.put_nowait(None)
                except Exception as e:
                    q.put_nowait(e)
            asyncio.get_running_loop().run_in_executor(None, _consume)
            while True:
                item = await q.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    raise item
                yield item

        try:
            # 0) Low Signal
            if _is_low_signal(query):
                if lang == "en":
                    msg = (
                        "[Yuna (CCO) Notice]\n\n"
                        "Hi! I'm Yuna. 😊\n\n"
                        "A test input has been detected. The server is running normally.\n\n"
                        "To provide a more accurate answer, please share:\n"
                        "- Case overview (what happened)\n"
                        "- Dates / parties involved / supporting documents\n"
                        "- Desired outcome\n\n"
                        "If you have a legal concern, please ask a specific question.\n"
                        "60 expert leaders are here to help!\n"
                    )
                else:
                    msg = (
                        "[유나 (CCO) 안내]\n\n"
                        "안녕하세요! 유나입니다. 😊\n\n"
                        "테스트 입력이 감지되었습니다. 서버는 정상 동작 중이에요.\n\n"
                        "더 정확한 답변을 드리기 위해 다음 정보를 알려주시면 좋겠어요:\n"
                        "- 사건 개요 (어떤 상황인지)\n"
                        "- 날짜/당사자/증빙 자료\n"
                        "- 원하시는 결과\n\n"
                        "법률 문제로 걱정이 있으시다면, 구체적으로 질문해 주세요.\n"
                        "60명의 전문 리더가 함께 도와드릴게요!\n"
                    )
                yield _sse("chunk", {"text": msg})
                yield _sse("done", {"leader": "유나", "leader_specialty": "콘텐츠 설계", "latency_ms": 0, "trace_id": trace})
                return

            # 0.3) 응답 캐시 확인
            cached = _check_response_cache_fn(query)
            if cached:
                latency_ms = int((time.time() - start_time) * 1000)
                logger.info(f"⚡ [Stream Cache HIT] leader={cached.get('leader', '?')} latency={latency_ms}ms")
                yield _sse("status", {"step": "analyzing", "leader": cached.get("leader", "마디")})
                yield _sse("chunk", {"text": cached.get("response", "")})
                yield _sse("done", {
                    "leader": cached.get("leader", "마디"),
                    "leader_specialty": cached.get("leader_specialty", "통합"),
                    "latency_ms": latency_ms, "trace_id": trace,
                    "swarm_mode": False, "response": cached.get("response", ""),
                    "status": "SUCCESS",
                })
                _audit_fn("ask_stream_cache_hit", {"query": query, "leader": cached.get("leader", "?"), "status": "CACHE_HIT", "latency_ms": latency_ms})
                return

            # 0.5) Gemini 키
            if not os.getenv("GEMINI_KEY"):
                yield _sse("error", {"message": "⚠️ GEMINI_KEY 미설정으로 추론이 비활성화되었습니다."})
                return

            # 1) Security Guard
            guard = _RUNTIME.get("guard")
            if guard:
                check_result = guard.check(query)
                if check_result == "CRISIS":
                    safety_config = config.get("security_layer", {}).get("safety", {})
                    crisis_res = safety_config.get("crisis_resources", {})
                    if lang == "en":
                        lines = ["🚨 Your safety is the top priority.\n"]
                        for label, number in crisis_res.items():
                            lines.append(f"  📞 {label}: {number}")
                        lines.append("\nPlease contact the above professional organizations immediately.")
                    else:
                        lines = ["🚨 당신의 안전이 가장 중요합니다.\n"]
                        for label, number in crisis_res.items():
                            lines.append(f"  📞 {label}: {number}")
                        lines.append("\n위 전문 기관으로 지금 바로 연락하세요.")
                    yield _sse("chunk", {"text": "\n".join(lines)})
                    yield _sse("done", {"leader": "SAFETY", "specialty": "", "latency_ms": 0, "trace_id": trace})
                    return
                if check_result is False:
                    blocked_msg = "🚫 Blocked by security policy." if lang == "en" else "🚫 보안 정책에 의해 차단되었습니다."
                    yield _sse("error", {"message": blocked_msg})
                    return

            # 2) C-Level
            clevel = _RUNTIME.get("clevel_handler")
            clevel_decision = None
            if clevel:
                clevel_decision = clevel.should_invoke_clevel(query)

            # 3) SSOT / Tools
            ssot_available = _RUNTIME.get("drf_healthy", False)
            tools = _get_drf_tools()

            now_kst = _now_iso()
            model_name = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
            gc = _ensure_genai_client_fn(_RUNTIME)

            # ─── 경로 A: C-Level 직접 호출 (스트리밍) ───
            if clevel_decision and clevel_decision.get("mode") == "direct":
                exec_id = clevel_decision.get("executive_id")
                clevel_instruction = clevel.get_clevel_system_instruction(exec_id, _build_system_instruction(stream_mode))
                if lang == "en":
                    clevel_instruction += "\n\nIMPORTANT: Respond entirely in English. Translate Korean legal terms with the original Korean in parentheses."
                leader_name = clevel.executives.get(exec_id, {}).get("name", exec_id)
                leader_specialty = clevel.executives.get(exec_id, {}).get("role", exec_id)

                yield _sse("status", {"step": "analyzing", "leader": leader_name})

                chat = gc.chats.create(
                    model=model_name,
                    config=genai_types.GenerateContentConfig(
                        tools=tools,
                        system_instruction=clevel_instruction,
                        max_output_tokens=3000,
                        automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=False),
                    ),
                    history=gemini_history,
                )

                accumulated = ""
                async for text_part in _async_stream_chunks(
                    chat.send_message_stream(
                        f"now_kst={now_kst}\nssot_available={ssot_available}\n사용자 질문: {query}"
                    )
                ):
                    accumulated += text_part
                    yield _sse("chunk", {"text": text_part})

                final_text = accumulated
                swarm_mode = False

            # ─── 경로 B: Swarm 모드 ───
            elif not (clevel_decision and clevel_decision.get("mode") == "direct"):
                orchestrator = _RUNTIME.get("swarm_orchestrator")

                if orchestrator and os.getenv("USE_SWARM", "true").lower() == "true":
                    yield _sse("status", {"step": "detecting_domain"})

                    _stream_matched = _match_ssot_sources_fn(query, top_k=5)
                    detected_domains = orchestrator.detect_domains(query, ssot_sources=_stream_matched)
                    selected_leaders = orchestrator.select_leaders(query, detected_domains, ssot_sources=_stream_matched)

                    use_swarm = (
                        orchestrator.swarm_enabled
                        and len(selected_leaders) > 1
                    )

                    leader_names_list = [l.get("name", "?") for l in selected_leaders]
                    yield _sse("status", {"step": "analyzing", "leader": ", ".join(leader_names_list)})

                    if not use_swarm:
                        # 단일 리더
                        leader = selected_leaders[0]
                        leader_name = leader.get("name", "유나")
                        leader_specialty = leader.get("specialty", "콘텐츠 설계")
                        swarm_mode = False

                        clevel_id = leader.get("_clevel")

                        # ─── 비법률 질문 즉시 응답 (CCO fallback, 스트리밍 없이) ───
                        if clevel_id == "CCO" and not detected_domains:
                            if lang == "en":
                                msg = (
                                    f"[Yuna (CCO) Content Design]\n\n"
                                    f"## 💡 Key Answer\n"
                                    f"Your question appears to be a general inquiry rather than a legal matter. "
                                    f"As a legal analysis system, I may not be able to provide a specialized answer, "
                                    f"but let me briefly guide you.\n\n"
                                    f"## 📌 Key Points\n"
                                    f"• Lawmadi OS is a **Korean legal analysis system**\n"
                                    f"• 60 expert leaders provide detailed analysis by legal field\n"
                                    f"• We cover lease, divorce, inheritance, criminal, labor law, and more\n\n"
                                    f"## 🔍 Learn More\n"
                                    f"If you have a legal concern, please ask a specific question! "
                                    f"For example, \"I can't get my lease deposit back\" — "
                                    f"an expert leader will begin analysis immediately."
                                )
                            else:
                                msg = (
                                    f"[유나 (CCO) 콘텐츠 설계]\n\n"
                                    f"## 💡 핵심 답변\n"
                                    f"말씀하신 내용은 법률 분야가 아닌 일반 질문으로 판단됩니다. "
                                    f"저는 법률 분석 시스템이라 전문적인 답변이 어려울 수 있지만, "
                                    f"간단히 안내드릴게요.\n\n"
                                    f"## 📌 주요 포인트\n"
                                    f"• Lawmadi OS는 **대한민국 법률 분석 전문 시스템**입니다\n"
                                    f"• 60명의 전문 리더가 법률 분야별로 정밀 분석해 드려요\n"
                                    f"• 임대차, 이혼, 상속, 형사, 노동법 등 다양한 분야를 다룹니다\n\n"
                                    f"## 🔍 더 알아보기\n"
                                    f"법률과 관련된 고민이 있으시다면 구체적으로 질문해 주세요! "
                                    f"예를 들어 \"전세 보증금을 못 돌려받고 있어요\" 같은 질문이면 "
                                    f"전문 리더가 즉시 분석을 시작합니다."
                                )
                            yield _sse("chunk", {"text": msg})
                            final_text = msg
                            latency_ms = int((time.time() - start_time) * 1000)
                            _METRICS["requests"] += 1
                            yield _sse("done", {
                                "leader": "유나", "leader_specialty": "콘텐츠 설계",
                                "latency_ms": latency_ms, "trace_id": trace,
                                "swarm_mode": False, "response": msg, "status": "SUCCESS",
                            })
                            _audit_fn("ask_stream", {"query": query, "leader": "유나", "status": "SUCCESS_INSTANT", "latency_ms": latency_ms, "swarm_mode": False})
                            return

                        _lang_suffix = "\n\nIMPORTANT: Respond entirely in English. Translate Korean legal terms with the original Korean in parentheses." if lang == "en" else ""
                        if clevel_id:
                            sys_instr = orchestrator._build_clevel_instruction(leader, _build_system_instruction(stream_mode)) if hasattr(orchestrator, '_build_clevel_instruction') else _build_system_instruction(stream_mode)
                            sys_instr += _lang_suffix
                        else:
                            sys_instr = (
                                f"{_build_system_instruction(stream_mode)}\n\n"
                                f"🎯 당신의 역할: {leader.get('name', '')} ({leader.get('role', '')})\n"
                                f"🎯 전문 분야: {leader_specialty}\n"
                                f"🎯 관점: {leader_specialty} 전문가 관점에서 이 사안을 분석하세요.\n\n"
                                f"반드시 [{leader.get('name', '')} ({leader_specialty}) 분석]으로 시작하세요."
                                f"{_lang_suffix}"
                            )

                        chat = gc.chats.create(
                            model=model_name,
                            config=genai_types.GenerateContentConfig(
                                tools=tools,
                                system_instruction=sys_instr,
                                max_output_tokens=4096,
                                automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=False),
                            ),
                            history=gemini_history,
                        )

                        accumulated = ""
                        async for text_part in _async_stream_chunks(
                            chat.send_message_stream(
                                f"now_kst={now_kst}\nssot_available={ssot_available}\n사용자 질문: {query}"
                            )
                        ):
                            accumulated += text_part
                            yield _sse("chunk", {"text": text_part})

                        # AFC로 인해 스트림 텍스트가 비었으면 non-stream fallback
                        if len(accumulated.strip()) < 10:
                            logger.warning(f"⚠️ [Stream] 단일리더 스트림 텍스트 비어있음 → non-stream fallback")
                            fallback_resp = chat.send_message(
                                f"now_kst={now_kst}\nssot_available={ssot_available}\n사용자 질문: {query}"
                            )
                            accumulated = _safe_extract_gemini_text(fallback_resp)
                            if accumulated:
                                yield _sse("chunk", {"text": accumulated})

                        final_text = accumulated

                    else:
                        # 다중 리더: 병렬 분석 → synthesis만 스트리밍
                        yield _sse("status", {"step": "parallel_analysis", "leaders": leader_names_list})

                        loop = asyncio.get_event_loop()
                        swarm_results = await loop.run_in_executor(
                            None,
                            lambda: orchestrator.parallel_swarm_analysis(
                                query, selected_leaders, tools,
                                _build_system_instruction(stream_mode), model_name
                            )
                        )

                        successful = [r for r in swarm_results if r.get("success", False)]
                        leader_name = ", ".join([r["leader"] for r in swarm_results][:3])
                        if len(swarm_results) > 3:
                            leader_name += f" 외 {len(swarm_results)-3}명"
                        leader_specialty = ", ".join([r["specialty"] for r in swarm_results][:3])
                        swarm_mode = len(successful) > 1

                        if len(successful) == 1:
                            final_text = successful[0]["analysis"]
                            yield _sse("chunk", {"text": final_text})
                        else:
                            yield _sse("status", {"step": "synthesizing"})

                            synthesis_orchestrator = _RUNTIME.get("swarm_orchestrator")
                            accumulated = ""
                            async for text_chunk in synthesis_orchestrator.synthesize_swarm_results_stream(
                                query, swarm_results, model_name
                            ):
                                accumulated += text_chunk
                                yield _sse("chunk", {"text": text_chunk})

                            final_text = accumulated

                        # C-Level swarm 보강
                        if clevel and clevel_decision and clevel_decision.get("mode") == "swarm":
                            exec_id = clevel_decision.get("executive_id", "CSO")
                            exec_name = clevel.executives.get(exec_id, {}).get("name", exec_id)
                            try:
                                clevel_instruction = clevel.get_clevel_system_instruction(exec_id, _build_system_instruction(stream_mode))
                                _gc = _ensure_genai_client_fn(_RUNTIME)
                                clevel_chat = _gc.chats.create(
                                    model=model_name,
                                    config=genai_types.GenerateContentConfig(
                                        system_instruction=clevel_instruction,
                                    ),
                                )
                                clevel_resp = clevel_chat.send_message(
                                    f"다음은 법률 리더들의 분석 결과입니다:\n\n{final_text}\n\n"
                                    f"위 분석에 대해 {exec_name}({exec_id}) 관점에서 전략적 보강 의견을 2~3문장으로 추가하세요.\n"
                                    f"사용자 원래 질문: {query}"
                                )
                                clevel_opinion = _safe_extract_gemini_text(clevel_resp)
                                if clevel_opinion:
                                    extra = f"\n\n---\n**[{exec_name} ({exec_id}) 전략 보강]**\n{clevel_opinion}"
                                    final_text += extra
                                    yield _sse("chunk", {"text": extra})
                                    leader_name += f", {exec_name}"
                            except Exception as ce:
                                logger.warning(f"⚠️ C-Level swarm 보강 실패 (무시): {ce}")

                else:
                    # Fallback 단일 리더
                    leader = select_swarm_leader(query, _LEADER_REGISTRY)
                    leader_name = leader['name']
                    leader_specialty = leader.get('specialty', '콘텐츠 설계')
                    swarm_mode = False
                    _is_cco_fallback = leader.get("_clevel") == "CCO"
                    _fb_max_tokens = 800 if _is_cco_fallback else 3000

                    # ─── Fallback 비법률 즉시 응답 ───
                    if _is_cco_fallback:
                        if lang == "en":
                            msg = (
                                "[Yuna (CCO) Content Design]\n\n"
                                "## 💡 Key Answer\n"
                                "Your question appears to be a general inquiry rather than a legal matter. "
                                "As a legal analysis system, I may not be able to provide a specialized answer, "
                                "but let me briefly guide you.\n\n"
                                "## 📌 Key Points\n"
                                "• Lawmadi OS is a **Korean legal analysis system**\n"
                                "• 60 expert leaders provide detailed analysis by legal field\n"
                                "• We cover lease, divorce, inheritance, criminal, labor law, and more\n\n"
                                "## 🔍 Learn More\n"
                                "If you have a legal concern, please ask a specific question! "
                                "For example, \"I can't get my lease deposit back\" — "
                                "an expert leader will begin analysis immediately."
                            )
                        else:
                            msg = (
                                "[유나 (CCO) 콘텐츠 설계]\n\n"
                                "## 💡 핵심 답변\n"
                                "말씀하신 내용은 법률 분야가 아닌 일반 질문으로 판단됩니다. "
                                "저는 법률 분석 시스템이라 전문적인 답변이 어려울 수 있지만, "
                                "간단히 안내드릴게요.\n\n"
                                "## 📌 주요 포인트\n"
                                "• Lawmadi OS는 **대한민국 법률 분석 전문 시스템**입니다\n"
                                "• 60명의 전문 리더가 법률 분야별로 정밀 분석해 드려요\n"
                                "• 임대차, 이혼, 상속, 형사, 노동법 등 다양한 분야를 다룹니다\n\n"
                                "## 🔍 더 알아보기\n"
                                "법률과 관련된 고민이 있으시다면 구체적으로 질문해 주세요! "
                                "예를 들어 \"전세 보증금을 못 돌려받고 있어요\" 같은 질문이면 "
                                "전문 리더가 즉시 분석을 시작합니다."
                            )
                        yield _sse("chunk", {"text": msg})
                        final_text = msg
                        latency_ms = int((time.time() - start_time) * 1000)
                        _METRICS["requests"] += 1
                        yield _sse("done", {
                            "leader": "유나", "leader_specialty": "콘텐츠 설계",
                            "latency_ms": latency_ms, "trace_id": trace,
                            "swarm_mode": False, "response": msg, "status": "SUCCESS",
                        })
                        _audit_fn("ask_stream", {"query": query, "leader": "유나", "status": "SUCCESS_INSTANT", "latency_ms": latency_ms, "swarm_mode": False})
                        return

                    yield _sse("status", {"step": "analyzing", "leader": leader_name})

                    fallback_instruction = (
                        f"{_build_system_instruction(stream_mode)}\n"
                        f"현재 당신은 '{leader['name']}({leader['role']})' 노드입니다.\n"
                        f"🎯 전문 분야: {leader.get('specialty', '통합')}\n"
                        f"🎯 관점: {leader.get('specialty', '통합')} 전문가 관점에서 이 사안을 분석하세요.\n"
                    )
                    if _is_cco_fallback:
                        fallback_instruction += (
                            f"📏 **비법률 질문은 반드시 500자 이내로 간결하게 답변하세요.**\n"
                            f"**비법률 목차**: ## 💡 핵심 답변 → ## 📌 주요 포인트 → ## 🔍 더 알아보기\n"
                        )
                    fallback_instruction += f"반드시 [{leader['name']} ({leader.get('specialty', '통합')}) 답변]으로 시작하세요."
                    if lang == "en":
                        fallback_instruction += "\n\nIMPORTANT: Respond entirely in English. Translate Korean legal terms with the original Korean in parentheses."
                    chat = gc.chats.create(
                        model=model_name,
                        config=genai_types.GenerateContentConfig(
                            tools=tools,
                            system_instruction=fallback_instruction,
                            max_output_tokens=_fb_max_tokens,
                            automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=False),
                        ),
                        history=gemini_history,
                    )

                    accumulated = ""
                    async for text_part in _async_stream_chunks(
                        chat.send_message_stream(
                            f"now_kst={now_kst}\nssot_available={ssot_available}\n사용자 질문: {query}"
                        )
                    ):
                        accumulated += text_part
                        yield _sse("chunk", {"text": text_part})

                    final_text = accumulated

            # Governance 검증
            if not validate_constitutional_compliance(final_text):
                yield _sse("error", {"message": "⚠️ 시스템 무결성 정책에 의해 답변이 제한되었습니다."})
                return

            # 후처리
            final_text_clean = _remove_think_blocks(final_text)
            final_text_clean = _remove_markdown_tables_fn(final_text_clean)
            final_text_clean = _remove_separator_lines_fn(final_text_clean)

            latency_ms = int((time.time() - start_time) * 1000)
            if latency_ms > 10000:
                logger.warning(f"🐌 [SLOW_REQUEST] {latency_ms}ms | query={query[:80]} | leader={leader_name}")

            # Metrics
            _METRICS["requests"] += 1
            req_count = _METRICS["requests"]
            prev_avg = _METRICS["avg_latency_ms"]
            _METRICS["avg_latency_ms"] = int(((prev_avg * (req_count - 1)) + latency_ms) / max(req_count, 1))

            # Audit
            _audit_fn("ask_stream", {
                "query": query,
                "leader": leader_name,
                "status": "SUCCESS",
                "latency_ms": latency_ms,
                "swarm_mode": swarm_mode,
            })

            # done 이벤트
            yield _sse("done", {
                "leader": leader_name,
                "leader_specialty": leader_specialty,
                "latency_ms": latency_ms,
                "trace_id": trace,
                "swarm_mode": swarm_mode,
                "response": final_text_clean,
                "status": "SUCCESS",
            })

            # 백그라운드 검증/저장
            async def _bg_verify():
                try:
                    verifier_module = _optional_import_fn("engines.response_verifier")
                    if verifier_module:
                        verifier = verifier_module.get_verifier()
                        _loop = asyncio.get_event_loop()
                        await _loop.run_in_executor(
                            None,
                            lambda: verifier.verify_response(
                                user_query=query,
                                gemini_response=final_text_clean,
                                tools_used=[],
                                tool_results=[]
                            )
                        )
                except Exception as e:
                    logger.warning(f"⚠️ [Stream Verification] 실패 (무시): {e}")
                try:
                    db_client_v2 = _optional_import_fn("connectors.db_client_v2")
                    if db_client_v2 and hasattr(db_client_v2, "save_chat_history"):
                        query_category = db_client_v2.classify_query_category(query)
                        _loop = asyncio.get_event_loop()
                        await _loop.run_in_executor(
                            None,
                            lambda: db_client_v2.save_chat_history(
                                user_query=query,
                                ai_response=final_text_clean,
                                leader=leader_name,
                                status="success",
                                latency_ms=latency_ms,
                                visitor_id=visitor_id,
                                swarm_mode=swarm_mode,
                            )
                        )
                except Exception as e:
                    logger.warning(f"⚠️ [Stream ChatHistory] 실패 (무시): {e}")

            asyncio.create_task(_bg_verify())

        except Exception as e:
            _METRICS["errors"] += 1
            ref = datetime.datetime.now().strftime("%H%M%S")
            logger.error(f"💥 스트리밍 에러 (trace={trace}, ref={ref}): {type(e).__name__}: {e}")
            logger.error(traceback.format_exc())
            user_msg = _classify_gemini_error_fn(e, ref)
            yield _sse("error", {"message": user_msg})

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# =============================================================
# ✅ 전문가용 답변 (Claude 검증 + 전문 용어 유지)
# =============================================================

@router.post("/ask-expert")
async def ask_expert(request: Request):
    """전문가용 답변: 5-Stage Legal Pipeline 통합 사용."""
    trace = str(uuid.uuid4())[:8]
    start = time.time()

    try:
        body = await request.json()
        query = str(body.get("query", "")).strip()
        original_response = str(body.get("original_response", "")).strip()
        lang = str(body.get("lang", "")).strip().lower()

        if not query:
            return {"trace_id": trace, "status": "ERROR", "response": "query가 필요합니다."}

        # 질문 분석 (Stage 1)
        analysis = await _claude_analyze_query(query)
        if not analysis:
            analysis = _fallback_tier_classification(query)

        # SSOT/DRF 도구 설정
        ssot_available = _RUNTIME.get("drf_healthy", False)
        tools = _get_drf_tools()

        now_kst = _now_iso()

        # 5-Stage Pipeline 실행 (전문가 모드)
        final_text = await _run_legal_pipeline(
            query, analysis, tools, [], now_kst, ssot_available, lang=lang, mode="expert"
        )

        # 후처리: think 블록 + 표 제거 (구분선은 유지 — 법률 검토서 형식에 필요)
        final_text = _remove_think_blocks(final_text)
        final_text = _remove_markdown_tables_fn(final_text)

        latency_ms = int((time.time() - start) * 1000)
        return {
            "trace_id": trace,
            "response": final_text,
            "status": "SUCCESS",
            "latency_ms": latency_ms,
        }

    except Exception as e:
        logger.error(f"❌ [Expert] 전문가 답변 실패 (trace={trace}): {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        return {"trace_id": trace, "status": "ERROR", "response": f"전문가 답변 생성 중 오류가 발생했습니다: {type(e).__name__}: {str(e)[:200]}"}


# =============================================================
# ✅ search / trending
# =============================================================

@router.get("/search")
async def search(q: str, limit: int = 10, request: Request = None):
    svc = _RUNTIME.get("search_service")
    if not svc:
        return {"status": "ERROR", "message": "SearchService not ready"}
    q = q.strip()[:200]
    if len(q) < 2:
        return {"status": "ERROR", "message": "검색어는 2자 이상 입력해주세요."}
    try:
        return svc.search_law(q)
    except Exception as e:
        logger.error(f"❌ /search 오류: {e}")
        return {"status": "ERROR", "message": "검색 처리 중 오류가 발생했습니다."}


@router.get("/trending")
async def trending(limit: int = 10, request: Request = None):
    svc = _RUNTIME.get("search_service")
    if not svc:
        return {"status": "ERROR", "message": "SearchService not ready"}
    try:
        return svc.search_precedents(limit)
    except Exception as e:
        logger.error(f"❌ /trending 오류: {e}")
        return {"status": "ERROR", "message": "트렌딩 조회 중 오류가 발생했습니다."}
