"""
Lawmadi OS v60.0.0 — Patched Kernel
Based on v60.0.0 main.py

[패치 내역 — 원본 대비 변경사항]
🔴 감사 #2.1  .env.cloudrun 시크릿 노출 → .env.example로 교체 (파일 수준)
🔴 감사 #2.2  CORS allow_origins=["*"] → 도메인 제한
🔴 감사 #2.3  DRF OC 기본값 "choepeter" 하드코딩 → 환경변수 필수
🟡 감사 #3.2  _audit() 시그니처 → db_client_v2.add_audit_log 실제 시그니처 정합
🟡 감사 #3.6  버전 문자열 통일 → OS_VERSION 상수화
🟡 원본버그   DRFConnector(config) → DRFConnector(api_key=...) 실제 시그니처
🟡 원본버그   SearchService(config) → SearchService() 실제 시그니처 (인자 없음)
🟡 원본버그   svc.get_best_law_verified() → svc.search_law() 실제 메서드명
🟡 원본버그   /ask 내 중복 DRF law_search 호출 제거
🟡 원본버그   들여쓰기 오류 (if drf_connector: 블록) 수정
🟡 원본버그   guard.check() 결과에서 CRISIS 처리 누락 → 추가
🟢 ULTRA     Trace ID 도입 (요청별 UUID)
🟢 ULTRA     /metrics, /diagnostics 엔드포인트 추가
🟢 ULTRA     optional_import 패턴 (부팅 실패 방지)
🟢 ULTRA     Rolling average latency 추적
🟢 ULTRA     Global exception handler 추가
🟢 감사 #4.1  GEMINI_MODEL 환경변수화
🟢 감사 #4.2  SOFT_MODE 기본값 true로 변경
"""

# =============================================================
# CORE IMPORTS
# =============================================================

import os
import sys
import json
import uuid
import time
import logging
import datetime
import re
import hashlib
import hmac
import traceback
import threading
from typing import Any, List, Dict, Optional, Union
from importlib import import_module

import asyncio
from google import genai
from google.genai import types as genai_types
from fastapi import FastAPI, Request, Header, HTTPException, File, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import aiofiles
import shutil
from pathlib import Path
import mimetypes
# anthropic 제거: Tier routing/검증을 Gemini로 통합
import httpx      # LawmadiLM API 호출용

# =============================================================
# FAIL-SOFT OPTIONAL IMPORT [ULTRA]
# 원본은 hard import로 모듈 하나 깨지면 서버 전체 부팅 실패.
# optional_import로 변경하여 개별 모듈 실패 시에도 서버 기동 가능.
# =============================================================

def optional_import(module_path: str, attr: Optional[str] = None) -> Optional[Any]:
    """모듈 로딩 실패 시 None 반환. 서버 부팅을 절대 중단시키지 않음."""
    try:
        module = import_module(module_path)
        return getattr(module, attr) if attr else module
    except Exception as e:
        logging.warning(f"[IMPORT FAIL-SOFT] {module_path} -> {e}")
        return None

# 원본 hard import → fail-soft로 교체
timeline_analyze = optional_import("engines.temporal_v2", "timeline_analyze")
SwarmOrchestrator = optional_import("agents.swarm_orchestrator", "SwarmOrchestrator")
resolve_leaders_from_ssot = optional_import("agents.swarm_orchestrator", "resolve_leaders_from_ssot")
CLevelHandler = optional_import("agents.clevel_handler", "CLevelHandler")
SearchService = optional_import("services.search_service", "SearchService")
SafetyGuard = optional_import("core.security", "SafetyGuard")
DRFConnector = optional_import("connectors.drf_client", "DRFConnector")
LawSelector = optional_import("core.law_selector", "LawSelector")
db_client = optional_import("connectors.db_client")

# =============================================================
# [Item 7] 분리된 모듈에서 import (하위 호환 유지)
# =============================================================
from utils.helpers import (
    _now_iso as _now_iso,
    _trace_id as _trace_id,
    _is_low_signal as _is_low_signal,
    _safe_extract_json as _safe_extract_json,
    _extract_best_dict_list as _extract_best_dict_list,
    _collect_texts_by_keys as _collect_texts_by_keys,
    _dedup_keep_order as _dedup_keep_order,
    _safe_extract_gemini_text as _safe_extract_gemini_text,
    _remove_think_blocks as _remove_think_blocks,
    _remove_markdown_headers as _remove_markdown_headers,
    _remove_markdown_tables as _remove_markdown_tables,
)
from core.constitutional import validate_constitutional_compliance as validate_constitutional_compliance
from tools.drf_tools import (
    set_runtime as _set_drf_tools_runtime,
    search_law_drf as search_law_drf,
    search_precedents_drf as search_precedents_drf,
    search_admrul_drf as search_admrul_drf,
    search_expc_drf as search_expc_drf,
    search_constitutional_drf as search_constitutional_drf,
    search_ordinance_drf as search_ordinance_drf,
    search_legal_term_drf as search_legal_term_drf,
    search_admin_appeals_drf as search_admin_appeals_drf,
    search_treaty_drf as search_treaty_drf,
)

# =============================================================
# [Phase 6] Import extracted modules
# =============================================================
from core.constants import OS_VERSION, GEMINI_MODEL, LAWMADILM_API_URL, LAWMADI_OS_API_URL
from core.classifier import (
    set_runtime as _set_classifier_runtime,
    set_leader_registry as _set_classifier_leader_registry,
    _fallback_tier_classification,
    _gemini_analyze_query,
    select_swarm_leader,
)
from core.pipeline import (
    set_runtime as _set_pipeline_runtime,
    set_law_cache as _set_pipeline_law_cache,
    _run_legal_pipeline,
)
from prompts.system_instructions import build_system_instruction as _build_system_instruction

# Route modules
from routes.static import router as static_router
from routes.health import router as health_router, set_dependencies as _set_health_deps
from routes.analytics import router as analytics_router, set_dependencies as _set_analytics_deps
from routes.legal import router as legal_router, set_dependencies as _set_legal_deps, ask as _legal_ask, search as _legal_search
from routes.files import router as files_router, set_dependencies as _set_files_deps
from routes.user import router as user_router, set_dependencies as _set_user_deps
from routes.admin import router as admin_router

# =============================================================
# BOOTSTRAP
# =============================================================

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LawmadiOS.Kernel")

# [v60] 필수 디렉토리 자동 생성 (temp, logs, uploads)
for directory in ["temp", "logs", "uploads"]:
    Path(directory).mkdir(exist_ok=True)
logger.info("✅ 필수 디렉토리 확인 완료: temp/, logs/, uploads/")

# [Phase 6] OS_VERSION, GEMINI_MODEL, LAWMADILM_API_URL
# are now imported from core.constants (see imports above)

# ─── Gemini 에러 분류 헬퍼 ───
def _classify_gemini_error(e: Exception, ref: str = "") -> str:
    """예외를 분석하여 사용자 친화적 에러 메시지 반환"""
    err_name = type(e).__name__
    err_msg = str(e).lower()

    # 1) genai_client가 None (AttributeError: 'NoneType' ...)
    if isinstance(e, AttributeError) and "'nonetype'" in err_msg:
        return f"⚠️ 엔진이 초기화되지 않았습니다. 서버를 재시작해 주세요. (Ref: {ref})"

    # 2) Gemini API 에러 (google.genai 예외)
    if "quota" in err_msg or "resource_exhausted" in err_msg or "resourceexhausted" in err_msg:
        return f"⚠️ 사용량 한도에 도달했습니다. 잠시 후 다시 시도해 주세요. (Ref: {ref})"
    if "429" in err_msg or "rate" in err_msg:
        return f"⚠️ 요청이 너무 많습니다. 잠시 후 다시 시도해 주세요. (Ref: {ref})"
    if "404" in err_msg or "not_found" in err_msg or "model" in err_msg and "not found" in err_msg:
        return f"⚠️ 모델을 찾을 수 없습니다. 관리자에게 문의해 주세요. (Ref: {ref})"
    if "401" in err_msg or "403" in err_msg or "permission" in err_msg or "unauthenticated" in err_msg:
        return f"⚠️ 인증에 실패했습니다. API 키를 확인해 주세요. (Ref: {ref})"
    if "500" in err_msg or "internal" in err_msg or "unavailable" in err_msg:
        return f"⚠️ 서버가 일시적으로 응답하지 않습니다. 잠시 후 다시 시도해 주세요. (Ref: {ref})"

    # 3) 타임아웃
    if isinstance(e, (TimeoutError, asyncio.TimeoutError)) or "timeout" in err_msg or "timed out" in err_msg:
        return f"⚠️ 응답 시간이 초과되었습니다. 질문을 간결하게 수정 후 다시 시도해 주세요. (Ref: {ref})"

    # 4) 네트워크 오류
    if isinstance(e, (ConnectionError, OSError)) or "connection" in err_msg or "network" in err_msg:
        return f"⚠️ 네트워크 연결 오류가 발생했습니다. 잠시 후 다시 시도해 주세요. (Ref: {ref})"

    # 5) 기본 (알 수 없는 에러)
    return f"⚠️ 시스템 장애가 발생했습니다. 잠시 후 다시 시도해 주세요. (Ref: {ref})"


def _ensure_genai_client(runtime: dict) -> object:
    """RUNTIME에서 genai_client를 가져오고, None이면 예외 발생"""
    gc = runtime.get("genai_client")
    if gc is None:
        raise RuntimeError("Gemini 클라이언트가 초기화되지 않았습니다 (GEMINI_KEY 확인 필요)")
    return gc


# Rate Limiter 설정 (항목 #2)
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Lawmadi OS", version=OS_VERSION)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    # IP 정보를 절대 노출하지 않음
    return JSONResponse(
        status_code=429,
        content={"error": "이용 한도에 도달했습니다. 잠시 후 다시 이용해주세요.", "blocked": True}
    )

# [감사 #2.2] CORS 도메인 제한 (원본: allow_origins=["*"])
# 개발 환경에서 localhost 필요 시 CORS_EXTRA_ORIGINS 환경변수로 추가
_cors_origins = [
    "https://lawmadi.com",
    "https://www.lawmadi.com",
    "https://lawmadi-os.web.app",
    "https://lawmadi-db.web.app",  # Firebase Hosting (current)
    "http://localhost:3000",  # lawmadi-os-pwa 로컬 개발
    "https://lawmadi-os-ee38lfjfg-choe-jainams-projects.vercel.app",  # lawmadi-os-pwa Vercel
]
_extra_cors = os.getenv("CORS_EXTRA_ORIGINS", "")
if _extra_cors:
    _cors_origins.extend([o.strip() for o in _extra_cors.split(",") if o.strip()])
_mcp_cors = os.getenv("MCP_CORS_ORIGINS", "")
if _mcp_cors:
    _cors_origins.extend([o.strip() for o in _mcp_cors.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

RUNTIME: Dict[str, Any] = {}

# [ULTRA] 런타임 메트릭
METRICS: Dict[str, Any] = {
    "requests": 0,
    "errors": 0,
    "avg_latency_ms": 0,
    "boot_time": None,
    "mcp_requests": 0,
}
_METRICS_LOCK = threading.Lock()

@app.middleware("http")
async def body_size_limit_middleware(request: Request, call_next):
    """요청 본문 크기 제한 — 메모리에 읽기 전 Content-Length 검증."""
    _MAX_BODY_SIZE = 2 * 1024 * 1024  # 2MB 기본
    _UPLOAD_MAX = 10 * 1024 * 1024  # 10MB (파일 업로드)
    path = request.url.path
    if path.startswith("/upload"):
        max_size = _UPLOAD_MAX
    else:
        max_size = _MAX_BODY_SIZE
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_size:
        return JSONResponse(
            status_code=413,
            content={"error": f"Request body too large (max {max_size // (1024*1024)}MB)"}
        )
    return await call_next(request)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """보안 헤더 주입 + MCP 모니터링"""
    if request.url.path.startswith("/mcp"):
        with _METRICS_LOCK:
            METRICS["mcp_requests"] += 1
        logger.info(f"[MCP] {request.method} {request.url.path}")
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # CSP: XSS 방어 — 인라인 스크립트/스타일 허용(자체 렌더링), 외부는 화이트리스트만
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://www.googletagmanager.com https://www.google-analytics.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' https: data:; "
        f"connect-src 'self' {LAWMADI_OS_API_URL} https://www.google-analytics.com https://region1.google-analytics.com; "
        "frame-ancestors 'none'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "upgrade-insecure-requests"
    )
    # API 응답 캐시 방지 — 법률 분석 내용이 프록시/브라우저에 캐시되지 않도록
    req_path = request.url.path
    if req_path.startswith("/ask") or req_path.startswith("/api/") or req_path.startswith("/upload") or req_path.startswith("/export") or req_path.startswith("/search"):
        response.headers["Cache-Control"] = "no-store, no-cache, private, max-age=0"
        response.headers["Pragma"] = "no-cache"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# =============================================================
# 🐝 [L2 SWARM DATA] Leader Registry (Hot-Swap JSON SSOT)
# =============================================================
try:
    with open("leaders.json", "r", encoding="utf-8") as f:
        LEADER_REGISTRY = json.load(f)
    logger.info("✅ Leader registry loaded")
except Exception as e:
    logger.warning(f"leaders.json load failed: {e}")
    LEADER_REGISTRY = {}

# =============================================================
# 📦 [LAW_CACHE] SSOT 10종 사전 캐시 — 다중 파일 로딩 (952K QA)
# =============================================================
LAW_CACHE: Dict[str, Any] = {}
_CACHE_FILES = [
    "law_cache_1.json",
    "law_cache_2.json",
    "law_cache_3.json",
    "law_cache_4.json",
    "law_cache_5.json",
    "law_cache_6.json",
    "law_cache_7.json",
]
try:
    _base_dir = os.path.dirname(__file__)
    _loaded_files = 0
    for _cf in _CACHE_FILES:
        _cache_path = os.path.join(_base_dir, _cf)
        if os.path.exists(_cache_path):
            with open(_cache_path, "r", encoding="utf-8") as f:
                _part = json.load(f)
            for _stype, _sdata in _part.items():
                if _stype in LAW_CACHE:
                    # 동일 stype이면 entries 병합
                    LAW_CACHE[_stype]["entries"].update(_sdata.get("entries", {}))
                    LAW_CACHE[_stype]["entry_count"] = len(LAW_CACHE[_stype]["entries"])
                else:
                    LAW_CACHE[_stype] = _sdata
            _loaded_files += 1
    if _loaded_files:
        _total_entries = sum(len(d.get("entries", {})) for d in LAW_CACHE.values())
        _total_qa = sum(
            len(info.get("key_qa", []))
            for d in LAW_CACHE.values()
            for info in d.get("entries", {}).values()
        )
        logger.info(f"✅ LAW_CACHE loaded: {len(LAW_CACHE)} types, {_total_entries} entries, {_total_qa} QA ({_loaded_files} files)")
    else:
        # 레거시 단일 파일 호환
        _cache_path = os.path.join(_base_dir, "law_cache.json")
        if os.path.exists(_cache_path):
            with open(_cache_path, "r", encoding="utf-8") as f:
                LAW_CACHE = json.load(f)
            _total_entries = sum(d.get("entry_count", 0) for d in LAW_CACHE.values())
            logger.info(f"✅ LAW_CACHE loaded (legacy): {len(LAW_CACHE)} types, {_total_entries} entries")
        else:
            logger.warning("⚠️ law_cache 파일 미존재: DRF 실시간 검색만 사용")
except Exception as _e:
    logger.warning(f"⚠️ law_cache 로드 실패: {_e}")

# 역 인덱스: keyword → [(ssot_type, law_name, score)] 빌드
_KEYWORD_INDEX: Dict[str, list] = {}  # keyword -> [(type, law, qa_count)]

def _build_keyword_index():
    """LAW_CACHE에서 역 인덱스 빌드 (startup 시 1회)"""
    global _KEYWORD_INDEX
    _KEYWORD_INDEX.clear()
    for stype, type_data in LAW_CACHE.items():
        entries = type_data.get("entries", {})
        for law_name, law_info in entries.items():
            qa = law_info.get("qa_count", 0)
            for kw in law_info.get("keywords", []):
                _KEYWORD_INDEX.setdefault(kw, []).append((stype, law_name, qa))
            # 법률명 자체도 인덱스
            _KEYWORD_INDEX.setdefault(law_name, []).append((stype, law_name, qa))
    logger.info(f"✅ Keyword index built: {len(_KEYWORD_INDEX)} keywords")

if LAW_CACHE:
    _build_keyword_index()

# =============================================================
# 📦 [RESPONSE_CACHE] 대표 질문 응답 캐시 (리더 매칭 보정용)
# =============================================================
RESPONSE_CACHE: Dict[str, Any] = {}
_RESPONSE_CACHE_LOADED_AT: float = 0.0
_RESPONSE_CACHE_TTL_HOURS: int = 24  # 24시간 후 캐시 무효화
try:
    _rcache_path = os.path.join(os.path.dirname(__file__), "response_cache.json")
    if os.path.exists(_rcache_path):
        with open(_rcache_path, "r", encoding="utf-8") as f:
            RESPONSE_CACHE = json.load(f)
        _RESPONSE_CACHE_LOADED_AT = time.time()
        logger.info(f"✅ RESPONSE_CACHE loaded: {len(RESPONSE_CACHE)} entries")
    else:
        logger.info("ℹ️ response_cache.json 미존재: 캐시 없이 동작")
except Exception as _e:
    logger.warning(f"⚠️ response_cache.json 로드 실패: {_e}")


def _check_response_cache(query: str) -> Optional[Dict]:
    """
    정확 일치 캐시 확인 (TTL + 헌법 적합성 검증 포함).
    Returns cached response dict or None.
    """
    if not RESPONSE_CACHE:
        return None
    # TTL 체크: 캐시 로드 후 24시간 초과 시 무효화
    if _RESPONSE_CACHE_LOADED_AT and (time.time() - _RESPONSE_CACHE_LOADED_AT) > _RESPONSE_CACHE_TTL_HOURS * 3600:
        logger.info("⏰ RESPONSE_CACHE TTL 만료 — 캐시 무시")
        return None
    from core.constitutional import validate_constitutional_compliance
    for leader_id, entry in RESPONSE_CACHE.items():
        if entry.get("query", "").strip() == query.strip():
            # 헌법 적합성 재검증
            resp_text = entry.get("response", "")
            if resp_text and not validate_constitutional_compliance(resp_text):
                logger.warning(f"⚠️ 캐시 응답 헌법 적합성 미통과: {leader_id}")
                return None
            return entry
    return None


def match_ssot_sources(query: str, top_k: int = 8) -> list:
    """
    질문 → 10종 캐시에서 관련 소스 매칭.
    Returns: [{"type": "law", "law": "근로기준법", "label": "현행법령",
               "target": "law", "endpoint": "lawSearch.do",
               "key_articles": [...top5...], "key_article_texts": [...],
               "key_precedents": [...], "key_qa": [...], "score": 150}, ...]
    """
    import re as _re
    import math as _math

    # 1) 토큰 추출: 2~20자 한글 + 접미사 제거
    raw_tokens = _re.findall(r'[가-힣]{2,20}', query)
    _SUFFIXES = ("이란", "에서", "에는", "에서는", "대해", "대한", "관한",
                 "에게", "으로", "에서의", "에는요", "인가요", "인지", "할때",
                 "할수", "하면", "해야", "인데", "이요", "이고")
    tokens = []
    for t in raw_tokens:
        tokens.append(t)
        # 접미사 제거 버전도 추가
        for sfx in _SUFFIXES:
            if t.endswith(sfx) and len(t) > len(sfx) + 1:
                tokens.append(t[:-len(sfx)])
    if not tokens:
        return []

    # 2) IDF 기반 관련성 점수 (키워드가 적은 법률에 매칭될수록 높은 점수)
    total_laws = sum(len(d.get("entries", {})) for d in LAW_CACHE.values()) or 1
    scores: Dict[tuple, float] = {}
    for token in tokens:
        hits = _KEYWORD_INDEX.get(token, [])
        if not hits:
            continue
        # IDF: 매칭 법률 수가 적을수록 높은 가중치
        idf = _math.log(total_laws / (len(hits) + 1)) + 1.0
        for stype, law_name, qa in hits:
            key = (stype, law_name)
            # 법률명과 정확히 일치하면 대폭 부스트
            if token == law_name:
                scores[key] = scores.get(key, 0) + 1000.0
            else:
                scores[key] = scores.get(key, 0) + idf

    if not scores:
        return []

    # 상위 top_k 추출 (중복 법률명 제거)
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    seen_laws = set()
    deduped = []
    for item in ranked:
        law_name = item[0][1]
        if law_name not in seen_laws:
            seen_laws.add(law_name)
            deduped.append(item)
        if len(deduped) >= top_k:
            break
    ranked = deduped
    results = []
    for (stype, law_name), score in ranked:
        type_data = LAW_CACHE.get(stype, {})
        law_info = type_data.get("entries", {}).get(law_name, {})
        results.append({
            "type": stype,
            "law": law_name,
            "label": type_data.get("label", ""),
            "target": type_data.get("target", ""),
            "endpoint": type_data.get("endpoint", ""),
            "key_articles": law_info.get("key_articles", [])[:20],
            "key_article_texts": law_info.get("key_article_texts", [])[:20],
            "key_precedents": law_info.get("key_precedents", [])[:10],
            "key_qa": law_info.get("key_qa", [])[:5],
            "keywords": law_info.get("keywords", [])[:5],
            "score": score,
        })
    return results


def build_cache_context(query: str) -> str:
    """
    질문 → 관련 SSOT 소스 요약 텍스트 (Gemini/Claude에 주입).
    토큰 절약: 핵심 조문만 포함 (전체 법령 대신 관련 3~5개 조문).
    """
    sources = match_ssot_sources(query, top_k=30)
    if not sources:
        return ""

    lines = ["[사전 캐시 매칭 결과 — 관련 SSOT 소스]"]
    for s in sources:
        arts = s.get("key_articles", [])
        art_strs = [f"{a['조문']}({a.get('제목','')})" for a in arts if a.get("조문")]
        lines.append(
            f"• [{s['label']}] {s['law']}: "
            f"핵심 조문={', '.join(art_strs) if art_strs else '없음'} "
            f"(DRF target={s['target']}, endpoint={s['endpoint']})"
        )
    lines.append("[위 캐시를 참고하되, 정확한 조문은 반드시 DRF 도구로 실시간 검증하세요]")
    return "\n".join(lines)


def build_ssot_context(query: str) -> str:
    """관련 SSOT: 법률명+조문원문+판례요지+대표Q&A → Gemini/Claude 전달 (균형 설정)"""
    sources = match_ssot_sources(query, top_k=30)
    if not sources:
        return ""

    lines = ["[SSOT 매칭 결과]"]
    for s in sources:
        lines.append(f"\n■ {s['law']} ({s['label']})")
        # 핵심조문 원문
        for art in s.get("key_article_texts", [])[:20]:
            lines.append(f"  조문: {art}")
        # 판례요지
        for prec in s.get("key_precedents", [])[:10]:
            lines.append(f"  판례: {prec}")
        # 대표 Q&A
        for qa in s.get("key_qa", [])[:5]:
            lines.append(f"  참고Q: {qa.get('q', '')}")
            lines.append(f"  참고A: {qa.get('a', '')}")

    return "\n".join(lines)

# =============================================================
# UTILITIES [ULTRA 추가]
# =============================================================

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""

def _get_client_ip(request: Request) -> str:
    """
    클라이언트 IP 주소 추출 (Cloud Run 환경)
    - Cloud Run LB가 X-Forwarded-For 마지막에 실제 클라이언트 IP 추가
    - 스푸핑 방지: IP 형식 검증 + 마지막(신뢰할 수 있는) 항목 우선
    """
    import ipaddress

    def _is_valid_ip(ip_str: str) -> bool:
        try:
            ipaddress.ip_address(ip_str)
            return True
        except (ValueError, TypeError):
            return False

    # X-Forwarded-For: Cloud Run에서는 마지막 항목이 LB가 추가한 실제 IP
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ips = [ip.strip() for ip in forwarded.split(",")]
        # 마지막(LB 추가) IP 사용, 형식 검증
        for ip in reversed(ips):
            if _is_valid_ip(ip):
                return ip

    # 직접 연결
    if request.client and request.client.host:
        return request.client.host
    return "unknown"

def _now_iso() -> str:
    """한국 시간(KST, UTC+9) 기준 ISO 형식 반환"""
    utc_now = datetime.datetime.utcnow()
    kst_now = utc_now + datetime.timedelta(hours=9)
    return kst_now.replace(microsecond=0).isoformat() + "+09:00"

# =============================================================
# 🕐 플랜별 요청 제한 (IP당, KST 기준)
# =============================================================
PLAN_CONFIG = {
    "free":    {"window_limit": 3, "window_hours": 4, "max_tokens": 3000, "expert_access": True},
    "premium": {"window_limit": 200, "window_hours": 4, "max_tokens": 5000, "expert_access": True},
}

_PREMIUM_KEYS = set(filter(None, os.getenv("PREMIUM_KEYS", "").split(",")))

def _get_user_plan(request: Request) -> str:
    """X-Premium-Key 헤더 확인 → 유효하면 'premium', 아니면 'free'"""
    key = request.headers.get("X-Premium-Key", "").strip()
    if key and _PREMIUM_KEYS:
        if any(hmac.compare_digest(key, pk) for pk in _PREMIUM_KEYS):
            return "premium"
    return "free"

def _check_expert_access(request: Request) -> bool:
    """전문가 모드 접근 권한 확인 (관리자 또는 프리미엄 사용자만 허용)"""
    _admin_key = os.getenv("MCP_API_KEY", "").strip() or os.getenv("INTERNAL_API_KEY", "").strip()
    if _admin_key and len(_admin_key) >= 8:
        req_key = request.headers.get("X-Admin-Key", "").strip()
        if req_key and hmac.compare_digest(req_key, _admin_key):
            return True
    plan = _get_user_plan(request)
    plan_cfg = PLAN_CONFIG.get(plan, PLAN_CONFIG["free"])
    return plan_cfg.get("expert_access", False)

_WINDOW_HOURS = 4
_rate_usage: Dict[str, List[float]] = {}  # {ip_hash: [timestamp1, timestamp2, ...]}

def _check_rate_limit(request: Request) -> Union[bool, dict]:
    """
    4시간 슬라이딩 윈도우 기준 요청 제한.
    통과 시 True, 초과 시 {"blocked": True, "retry_at_kst": "HH:MM"} 반환.
    IP는 해시로만 저장 (원본 비노출).
    관리자 키(X-Admin-Key 헤더)가 유효하면 제한 우회.
    플랜에 따라 window_limit 동적 적용.
    """
    # 관리자 키: 완전 우회 대신 높은 제한 적용 (1000회/4시간)
    _ADMIN_WINDOW_LIMIT = 1000
    _admin_key = os.getenv("MCP_API_KEY", "").strip() or os.getenv("INTERNAL_API_KEY", "").strip()
    is_admin = False
    if _admin_key and len(_admin_key) >= 8:
        req_key = request.headers.get("X-Admin-Key", "").strip()
        if req_key and hmac.compare_digest(req_key, _admin_key):
            is_admin = True

    if is_admin:
        window_limit = _ADMIN_WINDOW_LIMIT
    else:
        plan = _get_user_plan(request)
        plan_cfg = PLAN_CONFIG.get(plan, PLAN_CONFIG["free"])
        window_limit = plan_cfg["window_limit"]

    ip = _get_client_ip(request)
    ip_hash = _sha256(ip)
    now = time.time()
    window = _WINDOW_HOURS * 3600

    timestamps = _rate_usage.get(ip_hash, [])
    # 윈도우 밖의 오래된 기록 제거 + IP당 최대 기록 수 제한
    _MAX_TIMESTAMPS_PER_IP = 200
    timestamps = [t for t in timestamps if now - t < window][-_MAX_TIMESTAMPS_PER_IP:]

    if len(timestamps) >= window_limit:
        _rate_usage[ip_hash] = timestamps
        # 가장 오래된 요청이 윈도우를 벗어나는 KST 시각 계산
        oldest = min(timestamps)
        retry_ts = oldest + window
        retry_kst = datetime.datetime.utcfromtimestamp(retry_ts) + datetime.timedelta(hours=9)
        return {"blocked": True, "retry_at_kst": retry_kst.strftime("%H:%M")}

    timestamps.append(now)
    _rate_usage[ip_hash] = timestamps

    # 메모리 정리: IP 엔트리 수 제한 (5000개 초과 시 오래된 엔트리 정리)
    _MAX_RATE_ENTRIES = 5000
    if len(_rate_usage) > _MAX_RATE_ENTRIES:
        stale_keys = [k for k, v in _rate_usage.items() if not v or max(v) < now - window]
        for k in stale_keys:
            del _rate_usage[k]
        # 여전히 초과 시 가장 오래된 50% 삭제
        if len(_rate_usage) > _MAX_RATE_ENTRIES:
            sorted_keys = sorted(_rate_usage.keys(), key=lambda k: max(_rate_usage[k], default=0))
            for k in sorted_keys[:len(_rate_usage) // 2]:
                del _rate_usage[k]

    return True

def _rate_limit_response(retry_at_kst: str = ""):
    """제한 초과 시 응답 — 다음 이용 가능 시각 안내"""
    msg = f"이용 한도에 도달했습니다. {retry_at_kst} 이후 다시 이용 가능합니다." if retry_at_kst else "이용 한도에 도달했습니다. 잠시 후 다시 이용해주세요."
    return JSONResponse(
        status_code=429,
        content={"error": msg, "blocked": True, "retry_at_kst": retry_at_kst}
    )

def _trace_id() -> str:
    """[ULTRA] 요청별 고유 추적 ID"""
    return str(uuid.uuid4())

# =============================================================
# 🧾 [AUDIT] Best-effort audit wrapper
# [감사 #3.2] db_client_v2.add_audit_log 실제 시그니처에 맞춤:
#   add_audit_log(query, response, leader, status, latency_ms)
# =============================================================

# =============================================================
# Circuit Breaker (항목 #14) — DRF API 장애 전파 차단
# =============================================================

class CircuitBreaker:
    """외부 API 호출용 Circuit Breaker"""
    def __init__(self, failure_threshold: int = 3, reset_timeout_s: int = 30):
        self.failure_threshold = failure_threshold
        self.reset_timeout_s = reset_timeout_s
        self.failures = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def is_open(self) -> bool:
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.reset_timeout_s:
                self.state = "HALF_OPEN"
                return False
            return True
        return False

    def record_success(self):
        self.failures = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"🔴 [CircuitBreaker] OPEN — {self.failures}회 연속 실패")

# DRF API용 Circuit Breaker 인스턴스
_drf_circuit_breaker = CircuitBreaker(failure_threshold=3, reset_timeout_s=30)

def _audit(event_type: str, payload: dict) -> None:
    try:
        if not db_client:
            return
        fn = getattr(db_client, "add_audit_log", None)
        if not fn:
            return
        fn(
            query=str(payload.get("query", ""))[:2000],
            response=str(payload.get("response_sha256", ""))[:500],
            leader=str(payload.get("leader", "SYSTEM"))[:50],
            status=str(payload.get("status", event_type))[:20],
            latency_ms=int(payload.get("latency_ms", 0)),
        )
    except Exception as e:
        logger.warning(f"[AUDIT] logging failed: {e}")

# =============================================================
# 🛠️ [ROBUST HELPERS] 데이터 정밀 추출 및 정규화 계층
# =============================================================

def _safe_extract_json(text: str) -> Optional[Dict[str, Any]]:
    """중첩 JSON을 안전하게 추출하는 brace-counting 파서.

    기존 ``re.search(r'\\{[^{}]+\\}', ...)`` 는 중첩 중괄호가 있으면 실패한다.
    여기서는 첫 번째 ``{`` 를 찾은 뒤 depth 카운팅으로 매칭되는 ``}`` 를 찾아
    올바른 JSON 조각을 추출한다.
    """
    # 코드블록 안에 JSON이 감싸져 있을 수 있으므로 먼저 벗긴다
    stripped = text.strip()
    if "```" in stripped:
        # ```json ... ``` 또는 ``` ... ``` 패턴
        m = re.search(r'```(?:json)?\s*\n?([\s\S]*?)```', stripped)
        if m:
            stripped = m.group(1).strip()

    start = stripped.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(stripped)):
        ch = stripped[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = stripped[start:i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return None
    return None


def _is_low_signal(query: str) -> bool:
    q = (query or "").strip()
    if len(q) < 3:
        return True
    low = {"테스트", "test", "안녕", "hello", "hi", "ㅎ", "ㅋㅋ", "ㅇㅇ"}
    return q.lower() in low

def _extract_best_dict_list(obj: Any) -> List[Dict[str, Any]]:
    candidates = []
    def walk(o: Any):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            if o and all(isinstance(x, dict) for x in o):
                candidates.append(o)
            for v in o:
                walk(v)
    walk(obj)
    if not candidates:
        return []

    best_list, max_score = [], -1
    score_keys = ["판례일련번호", "법령ID", "사건번호", "caseNo", "lawId", "MST", "법령명", "조문내용"]

    for cand in candidates:
        current_score = 0
        sample = cand[0] if cand else {}
        for k in sample.keys():
            if any(sk in k for sk in score_keys):
                current_score += 1
        if current_score > max_score:
            max_score = current_score
            best_list = cand

    return best_list if best_list else (candidates[0] if candidates else [])

def _collect_texts_by_keys(obj: Any, wanted_keys: List[str]) -> List[str]:
    out: List[str] = []
    def walk(o: Any):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in wanted_keys and isinstance(v, str) and v.strip():
                    out.append(v.strip())
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(obj)
    return out

def _dedup_keep_order(texts: List[str]) -> List[str]:
    seen, out = set(), []
    for t in texts:
        key = t.strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out

# =============================================================
# 🛡️ [L6 GOVERNANCE] 헌법 준수 루프 (Constitutional Loop)
# =============================================================

def _safe_extract_gemini_text(response) -> str:
    """
    Gemini 응답에서 안전하게 텍스트 추출
    빈 응답이나 오류 시 빈 문자열 반환
    """
    try:
        if hasattr(response, 'text') and response.text:
            return response.text.strip()
    except Exception as e:
        logger.warning(f"⚠️ Gemini 응답 추출 실패: {e}")

        # finish_reason 로깅
        try:
            if hasattr(response, 'candidates') and response.candidates:
                finish_reason = response.candidates[0].finish_reason
                safety_ratings = getattr(response.candidates[0], 'safety_ratings', None)
                logger.warning(f"finish_reason: {finish_reason}, safety_ratings: {safety_ratings}")
        except (AttributeError, IndexError, TypeError) as inner_e:
            logger.debug(f"finish_reason 추출 실패: {inner_e}")

    return ""

def _remove_markdown_tables(text: str) -> str:
    """
    마크다운 표 형식을 글머리 기호 형식으로 변환

    예: | 항목 | 설명 | → • **항목** - 설명
    """
    import re

    lines = text.split('\n')
    result = []
    in_table = False
    table_headers = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # 표 시작 감지 (| 로 시작하고 | 로 끝남)
        if line.startswith('|') and line.endswith('|'):
            # 표 구분선인지 확인 (| :--- | :--- | 형식)
            if re.match(r'^\|\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|$', line):
                # 구분선은 건너뜀
                i += 1
                in_table = True
                continue

            # 표 행 파싱
            cells = [cell.strip() for cell in line.split('|')[1:-1]]  # 양 끝 빈 셀 제거

            if not in_table:
                # 첫 번째 행 (헤더)
                table_headers = cells
                in_table = True
            else:
                # 데이터 행 - 글머리 기호로 변환
                if len(cells) >= 2:
                    # 첫 번째 셀을 제목, 나머지를 설명으로
                    title = cells[0].replace('**', '').strip()
                    description = ' - '.join(cells[1:]).strip()
                    result.append(f"• **{title}** - {description}")
                elif len(cells) == 1:
                    result.append(f"• {cells[0]}")
        else:
            # 표가 아닌 일반 텍스트
            if in_table:
                # 표 종료 - 빈 줄 추가
                result.append('')
                in_table = False
                table_headers = []

            result.append(lines[i])

        i += 1

    return '\n'.join(result)

def _remove_separator_lines(text: str) -> str:
    """응답에서 ━━━, ───, === 등 구분선만으로 된 줄 제거"""
    import re
    lines = text.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        # 구분선만으로 이루어진 줄 (━, ─, ═, - 가 3개 이상 연속)
        if re.match(r'^[━─═\-]{3,}$', stripped):
            continue
        result.append(line)
    return '\n'.join(result)


def _compute_quality_meta(text: str, matched_sources: list) -> dict:
    """응답 품질 메타데이터 계산"""
    has_law_name = bool(re.search(r'[가-힣]+법', text))
    has_article = bool(re.search(r'제\d+조', text))
    has_action_guide = any(kw in text for kw in ["즉시", "1단계", "▶", "□", "체크리스트", "준비물"])
    has_precedent = bool(re.search(r'(대법원|헌법재판소|판결|선고)\s*\d', text))
    ssot_verified = len(matched_sources) > 0

    score = sum([has_law_name, has_article, has_action_guide, has_precedent, ssot_verified])
    return {
        "has_law_name": has_law_name,
        "has_article": has_article,
        "has_action_guide": has_action_guide,
        "has_precedent": has_precedent,
        "ssot_verified": ssot_verified,
        "quality_score": score,
    }


def _remove_think_blocks(text: str) -> str:
    """Gemini <think>...</think> 내부 추론 블록 제거"""
    import re
    # <think>...</think> 태그 블록 제거 (멀티라인)
    text = re.sub(r'<think>[\s\S]*?</think>', '', text)
    # 태그 없이 'think\n' 으로 시작하는 영문 추론 블록 제거
    # (첫 줄이 'think'이고 그 뒤 영문+줄바꿈이 이어지는 패턴)
    text = re.sub(r'^think\n(?:[A-Za-z*].*\n)*', '', text)
    # 선두 빈 줄 정리
    text = text.lstrip('\n')
    return text


def _remove_markdown_headers(text: str) -> str:
    """마크다운 # 헤더를 볼드(**) 텍스트로 변환"""
    import re
    lines = text.split('\n')
    result = []
    for line in lines:
        # ## 또는 ### 등 → 볼드 텍스트로 변환 (# 기호 제거)
        m = re.match(r'^(#{1,4})\s+(.+)$', line)
        if m:
            content = m.group(2).strip()
            result.append(f'**{content}**')
        else:
            result.append(line)
    return '\n'.join(result)


def validate_constitutional_compliance(response_text: str) -> bool:
    if not response_text or len(response_text.strip()) < 10:
        return False

    t = response_text

    # 1) 변호사 사칭 금지
    if "변호사입니다" in t or "변호사로서" in t:
        return False

    # 2) placeholder 날짜/타임라인 금지
    banned_patterns = [
        r"2024-MM-DD",
        r"YYYY-MM-DD",
        r"HH:MM:SS",
        r"ASCII_TIMELINE_V2\(SYSTEM_CORE_CHECK\)",
    ]
    for p in banned_patterns:
        if re.search(p, t):
            return False

    # 3) 근거 없는 상태 단정 차단
    banned_phrases = [
        "Ready and Verified",
        "완벽하게 작동",
        "모듈이 모두 활성화",
        "즉각적인 접근이 가능",
    ]
    if any(x in t for x in banned_phrases):
        return False

    # 4) 법조문 참조 없는 단정적 법률 주장 차단
    #    "~해야 합니다", "~됩니다" 등 법적 단정이 있는데
    #    "제N조", "법 제", "판례" 등 근거가 전혀 없으면 차단
    legal_assertion_patterns = [
        r"(?:위법|불법|합법|적법)(?:입니다|합니다|이다)",
        r"(?:의무|권리)가\s*(?:있습니다|없습니다|발생합니다)",
        r"(?:처벌|처분|제재)(?:을\s*)?(?:받습니다|됩니다|받게\s*됩니다)",
    ]
    has_legal_assertion = any(re.search(p, t) for p in legal_assertion_patterns)
    has_legal_source = bool(re.search(r'제\s?\d+\s?조|판례|대법원|헌법재판소|법령|법률\s+제\d+호', t))
    if has_legal_assertion and not has_legal_source:
        return False

    # 5) 불법 행위 조장 차단
    illegal_incitement = [
        "증거를 인멸",
        "증거를 없애",
        "증거 인멸",
        "증거를 숨기",
        "뇌물을 제공",
        "뇌물을 주",
        "허위 진술",
        "위증을 하",
        "위조하",
        "문서를 조작",
        "탈세 방법",
        "세금을 탈루",
    ]
    if any(phrase in t for phrase in illegal_incitement):
        return False

    # 6) 결과 보장 차단
    guarantee_patterns = [
        r"반드시\s*승소",
        r"100\s*%\s*(?:이길|승소|성공|확실)",
        r"무조건\s*(?:이길|승소|성공)",
        r"확실히\s*(?:이길|승소|이깁니다)",
        r"틀림없이\s*(?:이길|승소|이깁니다)",
        r"보장합니다",
        r"장담합니다",
    ]
    if any(re.search(p, t) for p in guarantee_patterns):
        return False

    return True

# =============================================================
# 🛠️ [L3 SHORT_SYNC] DRF 도구 — tools/drf_tools.py에서 import 완료
# 인라인 복사본 제거 (Phase 6). setter 주입으로 RUNTIME 참조.
# =============================================================
# (removed: 9 inline DRF tool functions — now in tools/drf_tools.py)

INLINE_DRF_REMOVED = True  # marker for verification


def _resolve_leader_from_ssot(matched_sources: list) -> Optional[Dict[str, str]]:
    """
    SSOT 매칭 결과로부터 최적 리더를 결정.
    resolve_leaders_from_ssot() 가 반환하는 leader_id→score 맵에서
    최고 점수 리더를 찾아 LEADER_REGISTRY에서 이름/전문분야를 조회.
    Returns: {"id": "L08", "name": "온유", "specialty": "임대차"} or None
    """
    if not matched_sources or not resolve_leaders_from_ssot:
        return None
    leader_boost = resolve_leaders_from_ssot(matched_sources)
    if not leader_boost:
        return None
    # 최고 부스트 리더 선택 (최소 30점 이상일 때만 override)
    best_id = max(leader_boost, key=leader_boost.get)
    best_score = leader_boost[best_id]
    if best_score < 30:
        return None
    leader_info = LEADER_REGISTRY.get(best_id, {})
    if not leader_info:
        return None
    return {
        "id": best_id,
        "name": leader_info.get("name", "마디"),
        "specialty": leader_info.get("specialty", "통합"),
    }

# =============================================================
# ⚙️ [CONFIG] load
# =============================================================

def load_integrated_config() -> Dict[str, Any]:
    if os.path.exists("config.json"):
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# =============================================================
# 🚀 STARTUP
# =============================================================

def _cleanup_expired_uploads():
    """만료된 업로드 파일 정리 (7일 경과)"""
    uploads_dir = Path("uploads")
    if not uploads_dir.exists():
        return
    now = time.time()
    max_age = 7 * 24 * 3600  # 7일
    cleaned = 0
    for f in uploads_dir.iterdir():
        if f.is_file() and (now - f.stat().st_mtime) > max_age:
            f.unlink(missing_ok=True)
            cleaned += 1
    if cleaned:
        logger.info(f"🧹 만료 업로드 파일 {cleaned}개 삭제")

@app.on_event("startup")
async def startup():

    logger.info(f"🚀 Lawmadi OS {OS_VERSION} starting...")

    # 스레드 풀 확대: 기본 6개(cpu=2) → 40개
    # asyncio.to_thread/run_in_executor 동기 Gemini/DRF 호출 병렬 처리용
    import concurrent.futures
    _executor = concurrent.futures.ThreadPoolExecutor(max_workers=40)
    asyncio.get_running_loop().set_default_executor(_executor)
    logger.info("✅ ThreadPoolExecutor: max_workers=40")

    # 만료된 업로드 파일 정리
    try:
        _cleanup_expired_uploads()
    except Exception:
        pass

    # [감사 #4.2] SOFT_MODE 기본값을 true로 변경 (Cloud Run 일시 장애 대비)
    soft_mode = os.getenv("SOFT_MODE", "true").lower() == "true"
    db_disabled = os.getenv("DB_DISABLED", "0") == "1"

    # --------------------------------------------------
    # 1️⃣ DB 초기화 (Fail-Soft)
    # --------------------------------------------------
    if not db_disabled:
        if db_client:
            try:
                init_fn = getattr(db_client, "init_tables", None)
                if init_fn:
                    init_fn()
                    logger.info("✅ DB init complete")

                # 채팅 기록 테이블 초기화
                db_client_v2 = optional_import("connectors.db_client_v2")
                if db_client_v2 and hasattr(db_client_v2, "init_chat_history_table"):
                    db_client_v2.init_chat_history_table()

                # 방문자 통계 테이블 초기화
                if db_client_v2 and hasattr(db_client_v2, "init_visitor_stats_table"):
                    db_client_v2.init_visitor_stats_table()

                # 응답 검증 테이블 초기화
                if db_client_v2 and hasattr(db_client_v2, "init_verification_table"):
                    db_client_v2.init_verification_table()
                    logger.info("✅ [Verification] 검증 시스템 활성화")

                # 프론트엔드 로그 테이블 초기화
                if db_client_v2 and hasattr(db_client_v2, "init_frontend_logs_table"):
                    db_client_v2.init_frontend_logs_table()

            except Exception as e:
                logger.warning(f"🟡 DB init failed: {e}")
                if not soft_mode:
                    raise
        else:
            logger.warning("🟡 db_client module unavailable")

    # --------------------------------------------------
    # 2️⃣ Config 로드
    # --------------------------------------------------
    try:
        config = load_integrated_config()
        logger.info("✅ Config loaded")
    except Exception as e:
        logger.error(f"❌ Config load failed: {e}")
        if not soft_mode:
            raise
        config = {}

    # --------------------------------------------------
    # 3️⃣ SwarmOrchestrator (60 Leader 도메인 라우팅)
    # --------------------------------------------------
    swarm_orchestrator = None
    if SwarmOrchestrator:
        try:
            # leaders.json에서 로드된 leader_registry 사용
            # config.json의 swarm_engine_config가 있으면 그것을 사용, 없으면 별도 파일에서 로드
            leader_reg = config.get("swarm_engine_config", {}).get("leader_registry", {})

            # 별도 leaders.json 파일이 있는 경우 그것 우선 사용
            if os.path.exists("leaders.json"):
                try:
                    with open("leaders.json", "r", encoding="utf-8") as f:
                        leaders_data = json.load(f)
                        leader_reg = leaders_data.get("swarm_engine_config", {}).get("leader_registry", leader_reg)
                except Exception as e:
                    logger.warning(f"leaders.json 로드 실패: {e}")

            swarm_orchestrator = SwarmOrchestrator(leader_reg, config, genai_client=None)
            logger.info(f"✅ SwarmOrchestrator initialized ({len(leader_reg)} leaders)")
        except Exception as e:
            logger.warning(f"🟡 SwarmOrchestrator degraded: {e}")

    # --------------------------------------------------
    # 3.6️⃣ CLevelHandler (C-Level 임원 호출)
    # --------------------------------------------------
    clevel_handler = None
    if CLevelHandler:
        try:
            # leaders.json에서 core_registry 로드
            core_reg = {}
            if os.path.exists("leaders.json"):
                try:
                    with open("leaders.json", "r", encoding="utf-8") as f:
                        leaders_data = json.load(f)
                        core_reg = leaders_data.get("core_registry", {})
                except Exception as e:
                    logger.warning(f"core_registry 로드 실패: {e}")

            clevel_handler = CLevelHandler(core_reg)
            logger.info(f"✅ CLevelHandler initialized ({len(core_reg)} executives)")
        except Exception as e:
            logger.warning(f"🟡 CLevelHandler degraded: {e}")

    # --------------------------------------------------
    # 4️⃣ Gemini 설정
    # [감사 #4.1] 모델명 환경변수화
    # Vertex AI 모드: Cloud Run ADC 자동 인증 (USE_VERTEX_AI=true)
    # API key fallback: GEMINI_KEY 환경변수 (USE_VERTEX_AI=false 또는 Vertex AI 실패 시)
    # --------------------------------------------------
    from core.constants import USE_VERTEX_AI, VERTEX_PROJECT, VERTEX_LOCATION

    genai_client = None
    if USE_VERTEX_AI:
        try:
            genai_client = genai.Client(
                vertexai=True,
                project=VERTEX_PROJECT,
                location=VERTEX_LOCATION,
            )
            logger.info(f"✅ Gemini client (Vertex AI, {VERTEX_PROJECT}/{VERTEX_LOCATION})")
        except Exception as e:
            logger.error(f"❌ Vertex AI init 실패: {e}")
            gemini_key = os.getenv("GEMINI_KEY")
            if gemini_key:
                genai_client = genai.Client(api_key=gemini_key)
                logger.warning("⚠️ Vertex AI 실패 → API key fallback")

    if genai_client is None:
        gemini_key = os.getenv("GEMINI_KEY")
        if gemini_key:
            genai_client = genai.Client(api_key=gemini_key)
            logger.info("✅ Gemini client initialized (API key mode)")
        else:
            logger.warning("⚠️ GEMINI_KEY 누락 (FAIL_CLOSED)")

    if genai_client and swarm_orchestrator:
        # SwarmOrchestrator에 genai_client 주입 (초기화 순서 이슈 해결)
        swarm_orchestrator.genai_client = genai_client

    # --------------------------------------------------
    # 5️⃣ DRF Connector (Fail-Soft)
    # [원본버그 수정] DRFConnector(config) → DRFConnector(api_key=...)
    #   실제 시그니처: __init__(self, api_key, timeout_ms, endpoints, ...)
    # [감사 #2.3] DRF OC 기본값 "choepeter" 하드코딩 제거
    # --------------------------------------------------
    drf_conn = None
    if DRFConnector:
        drf_oc = os.getenv("LAWGO_DRF_OC", "").strip()
        if drf_oc:
            try:
                drf_conn = DRFConnector(
                    api_key=drf_oc,
                    timeout_ms=int(os.getenv("DRF_TIMEOUT_MS", "5000")),
                )
                logger.info("✅ DRFConnector initialized")
                # startup 시 DRF 가용성 1회 확인 (매 요청 검사 제거 → ~2초 절약)
                try:
                    _test = drf_conn.law_search("민법")
                    RUNTIME["drf_healthy"] = bool(_test)
                    logger.info(f"✅ DRF SSOT 가용: {RUNTIME['drf_healthy']}")
                except Exception:
                    RUNTIME["drf_healthy"] = False
                    logger.warning("⚠️ DRF SSOT 비가용 (startup 점검 실패)")
            except Exception as e:
                logger.warning(f"🟡 DRFConnector degraded: {e}")
        else:
            logger.warning("⚠️ LAWGO_DRF_OC 미설정: DRF 비활성화")

    # --------------------------------------------------
    # 6️⃣ SearchService (DRF 기반)
    # [원본버그 수정] SearchService(config) → SearchService()
    #   실제 시그니처: __init__(self) — 인자 없음, 내부에서 DRF 직접 생성
    # --------------------------------------------------
    search_service = None
    if SearchService:
        try:
            search_service = SearchService()
            logger.info("✅ SearchService initialized")
        except Exception as e:
            logger.warning(f"🟡 SearchService degraded: {e}")

    # --------------------------------------------------
    # 7️⃣ SafetyGuard (Fail-Soft)
    # --------------------------------------------------
    guard = None
    if SafetyGuard:
        try:
            safety_config = config.get("security_layer", {}).get("safety", {})
            guard = SafetyGuard(
                policy=True,
                restricted_keywords=[],
                safety_config=safety_config,
            )
            logger.info("✅ SafetyGuard initialized")
        except Exception as e:
            logger.warning(f"🟡 SafetyGuard degraded: {e}")

    # --------------------------------------------------
    # 8️⃣ LawSelector (Fail-Soft)
    # --------------------------------------------------
    selector = None
    if LawSelector:
        try:
            selector = LawSelector()
        except Exception as e:
            logger.warning(f"🟡 LawSelector degraded: {e}")

    # --------------------------------------------------
    # 9️⃣ RUNTIME SSOT 등록
    # --------------------------------------------------
    # --------------------------------------------------
    # 9.5️⃣ Tier Router/검증은 Gemini로 통합, 4-Stage Hybrid Pipeline
    # --------------------------------------------------
    logger.info("✅ Tier Router/검증 엔진: Gemini 통합 사용")
    _rag_url = os.getenv("LAWMADILM_RAG_URL", "")
    if _rag_url:
        logger.info(f"✅ LawmadiLM RAG 서비스: {_rag_url}")
    else:
        logger.info("ℹ️ LawmadiLM RAG 미설정 (law_cache 폴백 사용)")
    logger.info("✅ 4-Stage Hybrid Pipeline: RAG → LawmadiLM(3000) → DRF전수검증 → Gemini검증보강")

    RUNTIME.update({
        "config": config,
        "drf": drf_conn,
        "selector": selector,
        "guard": guard,
        "search_service": search_service,
        "swarm_orchestrator": swarm_orchestrator,
        "clevel_handler": clevel_handler,
        "genai_client": genai_client,
    })

    # [Item 7] 분리된 DRF 도구 모듈에 RUNTIME 주입
    _set_drf_tools_runtime(RUNTIME)

    # [Phase 6] Wire extracted module setters
    _set_classifier_runtime(RUNTIME)
    _set_classifier_leader_registry(LEADER_REGISTRY)
    _set_pipeline_runtime(RUNTIME)
    _set_pipeline_law_cache(LAW_CACHE, build_cache_context, match_ssot_sources, build_ssot_context)

    # Wire route module dependencies
    _set_health_deps(RUNTIME, METRICS, LAW_CACHE, _KEYWORD_INDEX, optional_import("connectors.db_client_v2"))
    _set_analytics_deps(rate_limiter=limiter, get_client_ip_fn=_get_client_ip)
    _set_legal_deps(
        RUNTIME, METRICS, LEADER_REGISTRY, limiter,
        check_rate_limit=_check_rate_limit,
        rate_limit_response=_rate_limit_response,
        check_response_cache=_check_response_cache,
        match_ssot_sources=match_ssot_sources,
        resolve_leader_from_ssot=_resolve_leader_from_ssot,
        ensure_genai_client=_ensure_genai_client,
        classify_gemini_error=_classify_gemini_error,
        remove_markdown_tables=_remove_markdown_tables,
        remove_separator_lines=_remove_separator_lines,
        compute_quality_meta=_compute_quality_meta,
        audit_fn=_audit,
        get_client_ip=_get_client_ip,
        sha256_fn=_sha256,
        optional_import_fn=optional_import,
        check_expert_access=_check_expert_access,
    )
    _set_files_deps(RUNTIME, rate_limiter=limiter)
    _set_user_deps(RUNTIME, rate_limiter=limiter, ask_fn=_legal_ask, search_fn=_legal_search)

    # Admin tables init
    db_v2 = optional_import("connectors.db_client_v2")
    if db_v2 and hasattr(db_v2, "init_admin_tables"):
        try:
            db_v2.init_admin_tables()
        except Exception as e:
            logger.warning(f"🟡 Admin tables init failed: {e}")

    METRICS["boot_time"] = _now_iso()
    logger.info(f"✅ Lawmadi OS {OS_VERSION} Online")

# =============================================================
# 🏠 Frontend Serving (Homepage)
# =============================================================

# Static files (v60 structure) - must be before root route
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
if os.path.exists("frontend/public"):
    app.mount("/frontend", StaticFiles(directory="frontend/public"), name="frontend")

# =============================================================
# [Phase 6] Register extracted route modules
# =============================================================
app.include_router(static_router)
app.include_router(health_router)
app.include_router(analytics_router)
app.include_router(legal_router)
app.include_router(files_router)
app.include_router(user_router)
app.include_router(admin_router)

# =============================================================
# [ULTRA] GLOBAL EXCEPTION HANDLER
# =============================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    with _METRICS_LOCK:
        METRICS["errors"] += 1
    logger.error(f"[GLOBAL] {exc}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"error": "Kernel-Level Exception", "timestamp": _now_iso()},
    )

# =============================================================
# SHUTDOWN
# =============================================================

@app.on_event("shutdown")
async def shutdown():
    drf = RUNTIME.get("drf")
    if drf:
        try:
            await drf.close_async()
            drf.close()
        except Exception:
            pass
    logger.info(f"🛑 Lawmadi OS {OS_VERSION} Shutdown")

# =============================================================
# MCP (Model Context Protocol) 서버 — 모든 라우트 등록 후 마운트
# =============================================================
from fastapi_mcp import FastApiMCP, AuthConfig

from core.auth import verify_mcp_key as _verify_mcp_auth

mcp = FastApiMCP(
    app,
    name="Lawmadi OS",
    description="한국 법률 분석 시스템. 60명의 전문 리더와 3명의 C-Level 임원이 법률 질문에 답변합니다.",
    describe_all_responses=True,
    describe_full_response_schema=True,
    auth_config=AuthConfig(
        dependencies=[Depends(_verify_mcp_auth)],
    ),
)
mcp.mount_http()

# =============================================================
# MAIN
# =============================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)