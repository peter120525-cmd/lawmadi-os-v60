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
import threading
from typing import Any, Callable, Dict, List, Optional, Union

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from google.genai import types as genai_types

from core.constants import OS_VERSION, GEMINI_MODEL
from utils.helpers import (
    _safe_extract_gemini_text,
    _remove_think_blocks,
    _now_iso,
    _is_low_signal,
)
from core.constitutional import validate_constitutional_compliance
from core.classifier import (
    _gemini_analyze_query,
    _fallback_tier_classification,
    select_swarm_leader,
)
from core.pipeline import (
    _run_legal_pipeline,
    run_pipeline_stage1,
    run_pipeline_stage2,
    run_pipeline_stage3,
    _apply_fail_closed,
    _drf_verify_law_refs,
    _gemini_fallback_compose,
    VerificationResult,
    RAGContext,
)
from core.constants import FAIL_CLOSED_RESPONSE
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
_METRICS_LOCK = threading.Lock()
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


# ---------------------------------------------------------------------------
# 비법률 질문용 로컬 응답 (유나 CCO) — Gemini 미사용, 즉시 응답
# ---------------------------------------------------------------------------
async def _generate_yuna_response(query: str, lang: str = "") -> str:
    """비법률 질문에 대해 유나(CCO)가 로컬에서 즉시 응답 (API 호출 없음)"""
    return _build_yuna_fallback(lang)


def _build_yuna_fallback(lang: str = "") -> str:
    """비법률 질문 시 유나 로컬 응답 (시스템 안내)"""
    if lang == "en":
        return (
            "**Lawmadi OS — Korea's Legal Analysis System**\n\n"
            "Your question appears to be a general inquiry rather than a legal matter.\n\n"
            "Lawmadi OS specializes in **Korean legal analysis** with 60 expert leaders "
            "and real-time verification through the National Law Information Center.\n\n"
            "**We can help with:**\n"
            "- Lease disputes & deposit recovery\n"
            "- Divorce, custody & property division\n"
            "- Unfair dismissal & wage issues\n"
            "- Traffic accidents & insurance claims\n"
            "- Fraud, defamation & criminal matters\n"
            "- Inheritance, bankruptcy & corporate law\n\n"
            "If you have a legal concern, describe your situation in detail!\n"
            "For example: \"My landlord won't return my deposit\""
        )
    return (
        "**Lawmadi OS — 대한민국 법률 분석 시스템**\n\n"
        "말씀하신 내용은 법률 분야가 아닌 일반 질문으로 판단됩니다.\n\n"
        "Lawmadi OS는 **60명의 전문 리더**가 국가법령정보센터(SSOT) 실시간 검증을 통해 "
        "정확한 법률 분석을 제공하는 시스템입니다.\n\n"
        "**도움받을 수 있는 분야:**\n"
        "- 전세·임대차 분쟁, 보증금 반환\n"
        "- 이혼, 양육권, 재산분할\n"
        "- 부당해고, 임금체불, 퇴직금\n"
        "- 교통사고, 보험금 분쟁\n"
        "- 사기, 명예훼손, 형사 사건\n"
        "- 상속, 개인회생, 창업·법인\n\n"
        "법률 관련 고민이 있으시다면 구체적으로 질문해 주세요!\n"
        "예: \"전세 보증금을 돌려받지 못하고 있어요\""
    )


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
        import hashlib
        _masked_ip = hashlib.sha256(visitor_id.encode()).hexdigest()[:12]
        logger.info(f"🔍 Request from visitor: {_masked_ip}")

        config = _RUNTIME.get("config", {})

        # -------------------------------------------------
        # 0) Low Signal 차단
        # -------------------------------------------------
        if _is_low_signal(query):
            if lang == "en":
                msg = (
                    "**Lawmadi OS — Korea's Legal Analysis System**\n\n"
                    "Welcome! Lawmadi OS provides **real-time legal analysis** powered by 60 specialized leaders "
                    "and verified through the National Law Information Center (SSOT).\n\n"
                    "**What we can help with:**\n"
                    "- Lease disputes & deposit recovery\n"
                    "- Divorce, custody & property division\n"
                    "- Unfair dismissal & wage issues\n"
                    "- Traffic accidents & insurance claims\n"
                    "- Fraud, defamation & criminal matters\n"
                    "- Inheritance, bankruptcy & corporate law\n\n"
                    "**How to get started:**\n"
                    "Simply describe your situation in detail. For example:\n"
                    "\"My landlord won't return my deposit\" or \"I was unfairly fired from my job\"\n\n"
                    "The more details you provide, the more precise our analysis will be."
                )
            else:
                msg = (
                    "**Lawmadi OS — 대한민국 법률 분석 시스템**\n\n"
                    "반갑습니다! Lawmadi OS는 **60명의 전문 리더**가 국가법령정보센터(SSOT) 실시간 검증을 통해 "
                    "정확한 법률 분석을 제공하는 시스템입니다.\n\n"
                    "**도움받을 수 있는 분야:**\n"
                    "- 전세·임대차 분쟁, 보증금 반환\n"
                    "- 이혼, 양육권, 재산분할\n"
                    "- 부당해고, 임금체불, 퇴직금\n"
                    "- 교통사고, 보험금 분쟁\n"
                    "- 사기, 명예훼손, 형사 사건\n"
                    "- 상속, 개인회생, 창업·법인\n\n"
                    "**이용 방법:**\n"
                    "겪고 계신 상황을 구체적으로 말씀해 주세요. 예를 들어:\n"
                    "\"전세 보증금을 돌려받지 못하고 있어요\" 또는 \"직장에서 부당해고를 당했습니다\"\n\n"
                    "상황을 자세히 알려주실수록 더 정확한 분석이 가능합니다."
                )
            _audit_fn("ask_greeting", {"query": query, "status": "SYSTEM_INTRO", "latency_ms": 0})
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
        # 2) 🎯 TIER ROUTER: Gemini 분석 → 티어 분류 → 리더 배정
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
        # 4) 📦 SSOT 캐시 매칭 → S0(분류) + S1(RAG) 병렬 실행 → 리더 배정
        # -------------------------------------------------
        matched_sources = _match_ssot_sources_fn(query, top_k=5)
        if matched_sources:
            _src_strs = [s["type"] + ":" + s["law"] for s in matched_sources[:3]]
            logger.info(f"📦 [Cache] 매칭: {', '.join(_src_strs)}")

        # S0(Gemini 분류) + S1(RAG 검색) 병렬 실행
        analysis_result, rag_context = await asyncio.gather(
            _gemini_analyze_query(query),
            run_pipeline_stage1(query),
        )
        analysis = analysis_result
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
        # 4.1) 비법률 질문: 유나(CCO) Gemini 응답
        # -------------------------------------------------
        if not is_legal:
            instant_msg = await _generate_yuna_response(query, lang)
            latency = int((time.time() - start_time) * 1000)
            with _METRICS_LOCK:
                _METRICS["requests"] += 1
            _audit_fn("ask_non_legal", {"query": query, "status": "SUCCESS_NON_LEGAL", "leader": "유나", "latency_ms": latency})
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
            model_name = GEMINI_MODEL
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
            drf_result = VerificationResult()
            leader_name = clevel.executives.get(exec_id, {}).get("name", exec_id)
            leader_specialty = clevel.executives.get(exec_id, {}).get("role", exec_id)

        # -------------------------------------------------
        # 5) 🎯 3-Stage Legal Pipeline (S0+S1 병렬화 적용)
        # -------------------------------------------------
        else:
            final_text, drf_result = await _run_legal_pipeline(
                query, analysis, tools, gemini_history, now_kst, ssot_available,
                lang=lang, mode="general", rag_context=rag_context,
            )

        # -------------------------------------------------
        # 5.5) FAIL_CLOSED 감지 + 담당 리더 정보 헤더 삽입
        # -------------------------------------------------
        _is_fail_closed = (FAIL_CLOSED_RESPONSE in final_text) or (final_text.strip() == FAIL_CLOSED_RESPONSE.strip())

        if lang == "en":
            leader_header = f"**Assigned: {leader_name} ({leader_specialty} Expert)**\n\n"
        else:
            leader_header = f"**담당: {leader_name} ({leader_specialty} 전문)**\n\n"
        if not final_text.startswith(f"[{leader_name}") and not final_text.startswith(f"**담당:") and not final_text.startswith(f"**Assigned:"):
            final_text = leader_header + final_text

        # -------------------------------------------------
        # 6) 규칙 기반 헌법 준수 검증 (FAIL_CLOSED 응답은 스킵)
        # -------------------------------------------------
        if not _is_fail_closed and not validate_constitutional_compliance(final_text):
            gov_msg = "⚠️ Response restricted by system integrity policy." if lang == "en" else "⚠️ 시스템 무결성 정책에 의해 답변이 제한되었습니다."
            _audit_fn("ask_fail_closed", {"query": query, "status": "GOVERNANCE", "leader": leader_name})
            return {"trace_id": trace, "response": gov_msg, "leader": leader_name, "leader_specialty": leader_specialty, "status": "FAIL_CLOSED"}

        const_check = {"passed": True}  # Stage 3 DRF 검증에서 이미 처리됨

        latency_ms = int((time.time() - start_time) * 1000)

        # 느린 쿼리 로깅
        if latency_ms > 10000:
            logger.warning(f"🐌 [SLOW_REQUEST] {latency_ms}ms | tier={tier} | query={query[:80]} | leader={leader_name}")

        # -------------------------------------------------
        # 7) Metrics
        # -------------------------------------------------
        with _METRICS_LOCK:
            _METRICS["requests"] += 1
            req_count = _METRICS["requests"]
            prev_avg = _METRICS["avg_latency_ms"]
            _METRICS["avg_latency_ms"] = int(((prev_avg * (req_count - 1)) + latency_ms) / max(req_count, 1))

        # -------------------------------------------------
        # 8) Audit
        # -------------------------------------------------
        _response_status = "FAIL_CLOSED" if _is_fail_closed else "SUCCESS"
        _audit_fn("ask", {
            "query": query,
            "leader": leader_name,
            "tier": tier,
            "complexity": analysis.get("complexity", ""),
            "is_document": is_document,
            "status": _response_status,
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
                # DRF Stage 4 결과를 tool_results 형식으로 변환
                _tools_used = []
                _tool_results = []
                if drf_result and drf_result.total_refs > 0:
                    _tools_used = [{"name": "DRF_Stage4_전수검증", "args": {"total": drf_result.total_refs}}]
                    for ref in drf_result.verified_refs:
                        _tool_results.append({"result": "FOUND", "source": "DRF", "ref": ref.get("ref", ""), "verified": True})
                    for ref in drf_result.unverified_refs:
                        _tool_results.append({"result": "NO_DATA", "source": "DRF", "ref": ref.get("ref", ""), "verified": False, "reason": ref.get("reason", "")})

                verifier_module = _optional_import_fn("engines.response_verifier")
                if verifier_module:
                    verifier = verifier_module.get_verifier()
                    loop = asyncio.get_event_loop()
                    verification_result = await loop.run_in_executor(
                        None,
                        lambda: verifier.verify_response(
                            user_query=query,
                            gemini_response=final_text,
                            tools_used=_tools_used,
                            tool_results=_tool_results
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
                                tools_used=_tools_used, tool_results=_tool_results,
                                verification_result=v_result, ssot_compliance_score=v_score,
                                issues_found=v_issues, verification_feedback=verification_result.get("feedback", "")
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
            "status": _response_status,
            "latency_ms": latency_ms,
            "swarm_mode": False,
            "constitutional_check": "PASS" if const_check.get("passed", True) else "WARNING",
            "ssot_sources": [f"{s['type']}:{s['law']}" for s in matched_sources[:3]] if matched_sources else [],
            "meta": _compute_quality_meta_fn(final_text_clean, matched_sources),
        }

    except Exception as e:
        with _METRICS_LOCK:
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
            # 0) Low Signal → 시스템 소개
            if _is_low_signal(query):
                if lang == "en":
                    msg = (
                        "**Lawmadi OS — Korea's Legal Analysis System**\n\n"
                        "Welcome! Lawmadi OS provides **real-time legal analysis** powered by 60 specialized leaders "
                        "and verified through the National Law Information Center (SSOT).\n\n"
                        "**What we can help with:**\n"
                        "- Lease disputes & deposit recovery\n"
                        "- Divorce, custody & property division\n"
                        "- Unfair dismissal & wage issues\n"
                        "- Traffic accidents & insurance claims\n"
                        "- Fraud, defamation & criminal matters\n"
                        "- Inheritance, bankruptcy & corporate law\n\n"
                        "**How to get started:**\n"
                        "Simply describe your situation in detail. For example:\n"
                        "\"My landlord won't return my deposit\" or \"I was unfairly fired from my job\"\n\n"
                        "The more details you provide, the more precise our analysis will be."
                    )
                else:
                    msg = (
                        "**Lawmadi OS — 대한민국 법률 분석 시스템**\n\n"
                        "반갑습니다! Lawmadi OS는 **60명의 전문 리더**가 국가법령정보센터(SSOT) 실시간 검증을 통해 "
                        "정확한 법률 분석을 제공하는 시스템입니다.\n\n"
                        "**도움받을 수 있는 분야:**\n"
                        "- 전세·임대차 분쟁, 보증금 반환\n"
                        "- 이혼, 양육권, 재산분할\n"
                        "- 부당해고, 임금체불, 퇴직금\n"
                        "- 교통사고, 보험금 분쟁\n"
                        "- 사기, 명예훼손, 형사 사건\n"
                        "- 상속, 개인회생, 창업·법인\n\n"
                        "**이용 방법:**\n"
                        "겪고 계신 상황을 구체적으로 말씀해 주세요. 예를 들어:\n"
                        "\"전세 보증금을 돌려받지 못하고 있어요\" 또는 \"직장에서 부당해고를 당했습니다\"\n\n"
                        "상황을 자세히 알려주실수록 더 정확한 분석이 가능합니다."
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
            model_name = GEMINI_MODEL
            gc = _ensure_genai_client_fn(_RUNTIME)

            # 4) S0(분류) + S1(RAG) 병렬 실행
            from core.classifier import _gemini_analyze_query, _fallback_tier_classification
            analysis_result, rag_context_pre = await asyncio.gather(
                _gemini_analyze_query(query),
                run_pipeline_stage1(query),
            )
            analysis = analysis_result
            if not analysis:
                analysis = _fallback_tier_classification(query)
            is_legal = analysis.get("is_legal", True)

            # ─── 비법률 질문: 유나(CCO) Gemini 응답 ───
            if not is_legal:
                msg = await _generate_yuna_response(query, lang)
                yield _sse("chunk", {"text": msg})
                final_text = msg
                leader_name = "유나"
                leader_specialty = "콘텐츠 설계"
                latency_ms = int((time.time() - start_time) * 1000)
                with _METRICS_LOCK:
                    _METRICS["requests"] += 1
                yield _sse("done", {
                    "leader": "유나", "leader_specialty": "콘텐츠 설계",
                    "latency_ms": latency_ms, "trace_id": trace,
                    "swarm_mode": False, "response": msg, "status": "SUCCESS",
                })
                _audit_fn("ask_stream", {"query": query, "leader": "유나", "status": "SUCCESS_NON_LEGAL", "latency_ms": latency_ms, "swarm_mode": False})
                return

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

            # ─── 경로 B: 3-Stage Pipeline (스트리밍, Stage 4 제거) ───
            else:
                leader_name = analysis.get("leader_name", "마디")
                leader_specialty = analysis.get("leader_specialty", "통합")

                # Stage 1: 이미 S0+S1 병렬 완료 (rag_context_pre 사용)
                yield _sse("status", {"step": "searching_laws", "leader": leader_name})

                # Stage 2: LawmadiLM 초안 (5초 타임아웃)
                yield _sse("status", {"step": "analyzing", "leader": leader_name})
                lm_draft = await run_pipeline_stage2(
                    query, analysis, rag_context_pre,
                    lang=lang, mode=stream_mode,
                )

                # Stage 3: Gemini Flash 완성 답변
                yield _sse("status", {"step": "composing", "leader": leader_name})
                gemini_answer = ""
                try:
                    now_kst = _now_iso()
                    ssot_available = _RUNTIME.get("drf_healthy", False)
                    gemini_answer = await _gemini_fallback_compose(
                        query, analysis, rag_context_pre, tools, gemini_history,
                        now_kst, ssot_available, lang=lang, mode=stream_mode,
                        lm_draft=lm_draft or "",
                    )
                except Exception as gemini_err:
                    logger.error(f"[Stream] Gemini 답변 생성 실패: {gemini_err}")
                    if lm_draft:
                        gemini_answer = lm_draft

                # Stage 4: DRF 전수 검증 (async — run_in_executor 불필요)
                drf_verification = VerificationResult()
                if gemini_answer:
                    yield _sse("status", {"step": "verifying", "leader": leader_name})
                    drf_verification = await run_pipeline_stage3(gemini_answer)

                # FAIL_CLOSED 적용 (5% 초과 미검증 또는 DRF 오류 시 차단)
                final_text = _apply_fail_closed(gemini_answer, drf_verification) if gemini_answer else ""

                if final_text == FAIL_CLOSED_RESPONSE:
                    logger.warning("[Stream FAIL_CLOSED] 응답 차단됨")
                    yield _sse("chunk", {"text": FAIL_CLOSED_RESPONSE})
                    latency_ms = int((time.time() - start_time) * 1000)
                    with _METRICS_LOCK:
                        _METRICS["requests"] += 1
                    yield _sse("done", {
                        "leader": leader_name, "leader_specialty": leader_specialty,
                        "latency_ms": latency_ms, "trace_id": trace,
                        "swarm_mode": False, "response": FAIL_CLOSED_RESPONSE, "status": "FAIL_CLOSED",
                    })
                    return

                # 청크 단위로 스트리밍 (문단 기준 분할)
                if final_text:
                    chunks = final_text.split("\n\n")
                    for i, chunk in enumerate(chunks):
                        text_part = chunk if i == len(chunks) - 1 else chunk + "\n\n"
                        yield _sse("chunk", {"text": text_part})

                swarm_mode = False

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
            with _METRICS_LOCK:
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
                    # DRF 검증 결과를 tool_results 형식으로 변환
                    _bg_tools_used = []
                    _bg_tool_results = []
                    if drf_verification and drf_verification.total_refs > 0:
                        _bg_tools_used = [{"name": "DRF_Stage4_전수검증", "args": {"total": drf_verification.total_refs}}]
                        for ref in drf_verification.verified_refs:
                            _bg_tool_results.append({"result": "FOUND", "source": "DRF", "ref": ref.get("ref", ""), "verified": True})
                        for ref in drf_verification.unverified_refs:
                            _bg_tool_results.append({"result": "NO_DATA", "source": "DRF", "ref": ref.get("ref", ""), "verified": False, "reason": ref.get("reason", "")})

                    verifier_module = _optional_import_fn("engines.response_verifier")
                    if verifier_module:
                        verifier = verifier_module.get_verifier()
                        _loop = asyncio.get_event_loop()
                        await _loop.run_in_executor(
                            None,
                            lambda: verifier.verify_response(
                                user_query=query,
                                gemini_response=final_text_clean,
                                tools_used=_bg_tools_used,
                                tool_results=_bg_tool_results
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
            with _METRICS_LOCK:
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
# ✅ 전문가용 답변 (Gemini 검증 + 전문 용어 유지)
# =============================================================

@router.post("/ask-expert")
async def ask_expert(request: Request):
    """전문가용 답변: 4-Stage Legal Pipeline 통합 사용."""
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
        analysis = await _gemini_analyze_query(query)
        if not analysis:
            analysis = _fallback_tier_classification(query)

        leader_name = analysis.get("leader_name", "마디")
        leader_specialty = analysis.get("leader_specialty", "통합")

        # SSOT/DRF 도구 설정
        ssot_available = _RUNTIME.get("drf_healthy", False)
        tools = _get_drf_tools()

        now_kst = _now_iso()

        # 4-Stage Pipeline 실행 (전문가 모드)
        final_text, drf_result = await _run_legal_pipeline(
            query, analysis, tools, [], now_kst, ssot_available, lang=lang, mode="expert"
        )

        # 후처리: think 블록 + 표 제거 (구분선은 유지 — 법률 검토서 형식에 필요)
        final_text = _remove_think_blocks(final_text)
        final_text = _remove_markdown_tables_fn(final_text)

        # FAIL_CLOSED 상태 확인
        _is_fail_closed = (FAIL_CLOSED_RESPONSE in final_text) or (final_text.strip() == FAIL_CLOSED_RESPONSE.strip())
        _response_status = "FAIL_CLOSED" if _is_fail_closed else "SUCCESS"

        # 헌법 적합성 검증 (FAIL_CLOSED 아닌 경우만)
        if not _is_fail_closed and not validate_constitutional_compliance(final_text):
            logger.warning(f"[Expert] 헌법 적합성 검증 실패 (trace={trace})")
            _response_status = "FAIL_CLOSED"

        latency_ms = int((time.time() - start) * 1000)
        return {
            "trace_id": trace,
            "response": final_text,
            "leader": {"name": leader_name, "specialty": leader_specialty},
            "leader_specialty": leader_specialty,
            "status": _response_status,
            "latency_ms": latency_ms,
        }

    except Exception as e:
        logger.error(f"❌ [Expert] 전문가 답변 실패 (trace={trace}): {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        latency_ms = int((time.time() - start) * 1000)
        return {"trace_id": trace, "status": "ERROR", "response": f"전문가 답변 생성 중 오류가 발생했습니다: {type(e).__name__}: {str(e)[:200]}", "latency_ms": latency_ms}


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
