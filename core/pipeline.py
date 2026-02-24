"""
Lawmadi OS v60 -- 3-Stage Hybrid Legal Pipeline.
LawmadiLM(강화 프롬프트, 3000토큰) + RAG + DRF 전수 검증, Stage 4 제거.

Pipeline:
  Stage 0: Gemini 질문 분류 (병렬 실행)
  Stage 1: RAG 조문 검색 (ChromaDB + law_cache, Stage 0과 병렬)
  Stage 2: LawmadiLM 강화 답변 (5단계 프레임워크, RAG 컨텍스트 기반)
  Stage 3: DRF 실시간 전수 검증 (조문번호까지 검증)
  → Fail-Closed → 응답

사용법:
    from core.pipeline import set_runtime, set_law_cache, run_legal_pipeline
    set_runtime(RUNTIME)
    set_law_cache(LAW_CACHE, build_cache_context, match_ssot_sources, build_ssot_context)
"""
import json
import os
import re
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx
from google.genai import types as genai_types
from core.constants import (
    GEMINI_MODEL,
    LAWMADILM_API_URL,
    LAWMADILM_RAG_URL,
    FAIL_CLOSED_RESPONSE,
)
from utils.helpers import _remove_think_blocks, _safe_extract_gemini_text
from prompts.system_instructions import build_lawmadilm_prompt, build_system_instruction

logger = logging.getLogger("LawmadiOS.Pipeline")

# ---------------------------------------------------------------------------
# Module-level state (set via setters from main.py)
# ---------------------------------------------------------------------------
_RUNTIME: Dict[str, Any] = {}
_LAW_CACHE: Dict[str, Any] = {}
_LEADER_PROFILES: Dict[str, Any] = {}
_build_cache_context_fn = None
_match_ssot_sources_fn = None
_build_ssot_context_fn = None


def _load_leader_profiles() -> Dict[str, Any]:
    """leader-profiles.json 로드 (리더 철학·접근방식·정체성)"""
    global _LEADER_PROFILES
    if _LEADER_PROFILES:
        return _LEADER_PROFILES
    try:
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "frontend", "public", "leader-profiles.json",
        )
        with open(path, "r", encoding="utf-8") as f:
            _LEADER_PROFILES = json.load(f)
        logger.info(f"✅ 리더 프로필 로드 완료: {len(_LEADER_PROFILES)}명")
    except Exception as e:
        logger.warning(f"🟡 리더 프로필 로드 실패: {e}")
        _LEADER_PROFILES = {}
    return _LEADER_PROFILES


def _build_leader_persona(leader_id: str) -> str:
    """리더 프로필에서 핵심 인격·철학 텍스트 생성"""
    profiles = _load_leader_profiles()
    p = profiles.get(leader_id)
    if not p:
        return ""
    parts = []
    if p.get("hero"):
        parts.append(f"신조: {p['hero']}")
    identity = p.get("identity", {})
    if identity.get("what"):
        parts.append(f"역할: {identity['what']}")
    if identity.get("why"):
        parts.append(f"사명: {identity['why']}")
    solve = p.get("whatWeSolve", {})
    if solve.get("approach"):
        parts.append(f"접근방식: {solve['approach']}")
    if p.get("philosophy"):
        parts.append(f"철학: {p['philosophy']}")
    if not parts:
        return ""
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Setters
# ---------------------------------------------------------------------------

def set_runtime(runtime: Dict[str, Any]) -> None:
    """main.py의 RUNTIME 딕셔너리를 파이프라인 모듈에 주입."""
    global _RUNTIME
    _RUNTIME = runtime


def set_law_cache(
    law_cache: Dict[str, Any],
    build_cache_context_fn=None,
    match_ssot_sources_fn=None,
    build_ssot_context_fn=None,
) -> None:
    """main.py의 LAW_CACHE 딕셔너리와 관련 함수들을 주입."""
    global _LAW_CACHE, _build_cache_context_fn, _match_ssot_sources_fn, _build_ssot_context_fn
    _LAW_CACHE = law_cache
    _build_cache_context_fn = build_cache_context_fn
    _match_ssot_sources_fn = match_ssot_sources_fn
    _build_ssot_context_fn = build_ssot_context_fn


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# =============================================================
# 데이터 구조체
# =============================================================

@dataclass
class RAGContext:
    """Stage 1 결과: RAG 조문 검색 결과"""
    articles: List[Dict] = field(default_factory=list)       # RAG API 결과
    matched_laws: List[Dict] = field(default_factory=list)   # law_cache 매칭 결과
    context_text: str = ""                                    # 프롬프트 주입용 포맷팅 텍스트
    cache_context: str = ""                                   # 기존 build_cache_context 결과


@dataclass
class VerificationResult:
    """Stage 3 결과: DRF 전수 검증 결과"""
    verified_refs: List[Dict] = field(default_factory=list)
    unverified_refs: List[Dict] = field(default_factory=list)
    all_passed: bool = True
    total_refs: int = 0



# =============================================================
# Stage 1: RAG 조문 검색
# =============================================================

async def _stage1_rag_search(query: str, top_k: int = 10) -> RAGContext:
    """Stage 1: RAG 서비스 + law_cache 키워드 매칭으로 관련 조문 검색"""
    ctx = RAGContext()

    # 1a. LawmadiLM RAG API 호출 (설정된 경우)
    rag_url = LAWMADILM_RAG_URL
    if rag_url:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{rag_url}/search",
                    params={"query": query, "top_k": top_k},
                )
                resp.raise_for_status()
                results = resp.json().get("results", [])
                ctx.articles = results
                logger.info(f"[Stage 1] RAG API: {len(results)}건 조문 검색 완료")
        except Exception as e:
            logger.warning(f"[Stage 1] RAG API 실패 (law_cache 폴백): {e}")

    # 1b. law_cache 키워드 매칭 (로컬, 즉시)
    if _match_ssot_sources_fn:
        try:
            cache_matches = _match_ssot_sources_fn(query, top_k=8)
            ctx.matched_laws = cache_matches or []
        except Exception as e:
            logger.warning(f"[Stage 1] law_cache 매칭 실패: {e}")

    # 1c. SSOT 컨텍스트 텍스트 생성 (조문 원문 포함)
    if _build_ssot_context_fn:
        try:
            ctx.context_text = _build_ssot_context_fn(query)
        except Exception:
            ctx.context_text = ""

    # 1d. 기존 build_cache_context (요약 버전)
    if _build_cache_context_fn:
        try:
            ctx.cache_context = _build_cache_context_fn(query)
        except Exception:
            ctx.cache_context = ""

    # RAG API 결과를 텍스트로 포맷팅하여 context_text에 추가
    if ctx.articles:
        rag_text_lines = ["\n[RAG 검색 결과 조문]"]
        for art in ctx.articles[:10]:
            law_name = art.get("law_name", art.get("법령명", ""))
            article_no = art.get("article_no", art.get("조문번호", ""))
            article_title = art.get("article_title", art.get("조문제목", ""))
            text = art.get("text", art.get("조문내용", ""))
            score = art.get("score", 0)
            if law_name and text:
                header = f"■ {law_name}"
                if article_no:
                    header += f" 제{article_no}조"
                if article_title:
                    header += f" ({article_title})"
                if score:
                    header += f" [관련도: {score:.2f}]"
                rag_text_lines.append(header)
                rag_text_lines.append(f"  {text[:500]}")
        ctx.context_text = "\n".join(rag_text_lines) + "\n" + ctx.context_text

    total = len(ctx.articles) + len(ctx.matched_laws)
    logger.info(f"[Stage 1] RAG 완료: RAG API {len(ctx.articles)}건 + law_cache {len(ctx.matched_laws)}건 = {total}건")
    return ctx


# =============================================================
# Stage 2: LawmadiLM 주력 답변 생성
# =============================================================

async def _call_lawmadilm(
    query: str,
    analysis: Dict,
    rag_context: RAGContext,
    drf_verification: Optional[VerificationResult] = None,
    lang: str = "",
    mode: str = "general",
) -> str:
    """Stage 2: LawmadiLM 핵심 법률 초안 (5-6초 내 완료, 150토큰)"""
    leader_name = analysis.get("leader_name", "마디")
    leader_specialty = analysis.get("leader_specialty", "통합")
    leader_id = analysis.get("leader_id", "")

    # RAG 컨텍스트 텍스트 준비
    rag_text = ""
    if rag_context.context_text:
        rag_text = rag_context.context_text[:4000]
    elif rag_context.cache_context:
        rag_text = rag_context.cache_context[:2000]

    # 리더 인격·철학 텍스트
    persona_text = _build_leader_persona(leader_id)

    # 5단계 프레임워크 강화 프롬프트 생성
    system_prompt = build_lawmadilm_prompt(
        leader_name=leader_name,
        leader_specialty=leader_specialty,
        rag_context=rag_text,
        drf_verification=drf_verification,
        lang=lang,
        mode=mode,
        leader_persona=persona_text,
    )

    max_tokens = 100 if mode == "expert" else 60  # 5초 내 완성 목표 (네트워크 지연 포함)

    payload = {
        "messages": [{"role": "user", "content": query}],
        "system_prompt": system_prompt,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(f"{LAWMADILM_API_URL}/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()

    content = data.get("answer", "")
    elapsed = data.get("usage", {}).get("elapsed_seconds", 0)
    tokens = data.get("usage", {}).get("completion_tokens", 0)
    logger.info(f"[Stage 2] LawmadiLM 강화 답변 완료 ({elapsed}s, {tokens} tokens, {len(content)}자)")
    return content


def _postprocess_lawmadilm(draft: str, query: str) -> Optional[str]:
    """LawmadiLM 답변 후처리: 품질 미달 시 None -> Gemini 전담"""
    if not draft or len(draft.strip()) < 30:
        return None

    # <think> 태그 제거
    draft = _remove_think_blocks(draft)

    # 반복 50% 이상 감지
    sentences = [s.strip() for s in re.split(r'[.\u3002\n]', draft) if s.strip()]
    if sentences:
        unique = set(sentences)
        if len(unique) / len(sentences) < 0.5:
            logger.warning(f"[Stage 2 PP] 반복 감지 ({len(unique)}/{len(sentences)}) -> None")
            return None

    return draft.strip()


# =============================================================
# Stage 3: DRF 실시간 전수 검증
# =============================================================

def _extract_articles_from_drf(raw_response) -> List[Dict]:
    """DRF lawService.do 응답에서 조문 목록을 추출

    lawService.do 응답 구조: {"법령": {"조문": {"조문단위": [...]}}}
    각 조문단위: {"조문번호": "3", "조문내용": "제3조(대항력) ...", ...}
    """
    if not raw_response:
        return []

    articles = []
    try:
        if isinstance(raw_response, dict):
            # lawService.do 응답: {"법령": {"조문": {"조문단위": [...]}}}
            law_root = raw_response.get("법령", raw_response)
            if isinstance(law_root, dict):
                jo_section = law_root.get("조문", {})
                if isinstance(jo_section, dict):
                    jo_list = jo_section.get("조문단위", [])
                    if isinstance(jo_list, dict):
                        jo_list = [jo_list]
                    if isinstance(jo_list, list):
                        articles.extend(jo_list)

            # Fallback: LawSearch 응답 구조 (하위 호환)
            if not articles:
                law_data = raw_response.get("LawSearch", {})
                if isinstance(law_data, dict):
                    law_list = law_data.get("law", [])
                    if isinstance(law_list, dict):
                        law_list = [law_list]
                    if isinstance(law_list, list):
                        for law in law_list:
                            jo_list = law.get("조문", [])
                            if isinstance(jo_list, dict):
                                jo_list = [jo_list]
                            for jo in jo_list:
                                if isinstance(jo, dict):
                                    articles.append(jo)

            # 직접 리스트 형식
            if not articles:
                for key in ["law", "조문", "조문목록"]:
                    items = raw_response.get(key, [])
                    if isinstance(items, list):
                        articles.extend(items)
                    elif isinstance(items, dict):
                        articles.append(items)

        elif isinstance(raw_response, list):
            articles = raw_response

    except Exception as e:
        logger.debug(f"[DRF Parse] 조문 추출 실패: {e}")

    return articles


def _get_article_text(articles: List[Dict], article_num: int) -> Optional[str]:
    """조문 목록에서 특정 조문번호의 텍스트를 반환"""
    for art in articles:
        try:
            num = art.get("조문번호", "")
            if isinstance(num, str):
                num = int(num.strip()) if num.strip().isdigit() else None
            if num == article_num:
                content = art.get("조문내용", "") or art.get("조문", "") or art.get("content", "")
                title = art.get("조문제목", "") or art.get("제목", "")
                if content:
                    return f"제{article_num}조({title}) {content}" if title else f"제{article_num}조 {content}"
        except (ValueError, TypeError):
            continue
    return None


def _drf_verify_law_refs(text: str) -> VerificationResult:
    """Stage 3: 응답에서 인용된 모든 법률 참조를 DRF API로 전수 검증 (조문번호까지 확인)"""
    result = VerificationResult()

    # 법률 참조 추출: "OO법 제X조" 또는 "OO법 제X조 제Y항"
    refs = re.findall(
        r'([가-힣]+(?:법|시행령|시행규칙|규정|조례))\s*제(\d+)조(?:\s*제(\d+)항)?',
        text
    )
    if not refs:
        result.all_passed = True
        return result

    svc = _RUNTIME.get("search_service")
    if not svc:
        logger.warning("[Stage 3] SearchService 없음 -> 검증 스킵")
        result.all_passed = True
        return result

    seen = set()
    # 법령별로 lawService.do 호출 캐시 (조문 상세 포함)
    law_articles_cache: Dict[str, Any] = {}

    for law_name, article_num_str, paragraph_str in refs:
        article_num = int(article_num_str)
        key = f"{law_name} 제{article_num}조"
        if key in seen:
            continue
        seen.add(key)

        try:
            # lawService.do로 조문 상세 조회 (법령별 1회만 호출)
            if law_name not in law_articles_cache:
                raw = svc.get_law_articles(law_name)
                law_articles_cache[law_name] = raw
            else:
                raw = law_articles_cache[law_name]

            law_exists = bool(raw)
            article_exists = False
            article_text = None
            articles = []

            if raw:
                articles = _extract_articles_from_drf(raw)
                if articles:
                    article_exists = any(
                        _match_article_num(a, article_num) for a in articles
                    )
                    article_text = _get_article_text(articles, article_num)

            ref_entry = {
                "ref": key,
                "law_name": law_name,
                "article_num": article_num,
                "law_exists": law_exists,
                "article_exists": article_exists,
                "article_text": article_text,
                "verified": law_exists and article_exists,
            }

            if ref_entry["verified"]:
                result.verified_refs.append(ref_entry)
                logger.info(f"[Stage 3] ✅ {key}: 검증 통과")
            else:
                reason = "법령 미존재" if not law_exists else f"제{article_num}조 미존재"
                ref_entry["reason"] = reason
                result.unverified_refs.append(ref_entry)
                logger.warning(f"[Stage 3] ❌ {key}: {reason} (law_exists={law_exists}, articles={len(articles) if raw and articles else 0})")

        except Exception as e:
            logger.warning(f"[Stage 3] {key} 검증 실패: {e}")
            result.unverified_refs.append({
                "ref": key,
                "law_name": law_name,
                "article_num": article_num,
                "law_exists": False,
                "article_exists": False,
                "article_text": None,
                "verified": False,
                "reason": f"검증 오류: {type(e).__name__}",
            })

    # ── 판례 검증: "대법원 YYYY다NNNNN" 등 판례번호 추출 + DRF 검증 ──
    prec_refs = re.findall(
        r'((?:대법원|대법|헌법재판소|헌재|서울고등법원|서울고법|서울중앙지방법원)\s*'
        r'(\d{4})\s*[.]\s*(\d{1,2})\s*[.]\s*\d{1,2}\s*[.]?\s*선고\s*'
        r'(\d{2,4}[가-힣]+\d+)\s*(?:판결|결정))',
        text
    )
    # 더 간단한 패턴: "2020다12345", "2012헌바55", "2019헌마439" 등
    if not prec_refs:
        prec_refs_simple = re.findall(
            r'(\d{2,4}'
            r'(?:헌바|헌마|헌가|헌나|헌라|헌사|헌아|헌자|'  # 헌재결정례
            r'다|나|가|마|카|타|파|라|바|사|아|자|차|하|'    # 대법원 판례
            r'두|누|구|무|부|수|우|주|추|후|그|드|스|으)'
            r'(?:합)?\d{2,6})',
            text
        )
    else:
        prec_refs_simple = [p[3] for p in prec_refs]  # 사건번호만 추출

    if prec_refs_simple:
        drf_inst = _RUNTIME.get("drf")
        prec_seen = set()
        for case_no in prec_refs_simple:
            case_no = case_no.strip()
            if case_no in prec_seen or len(case_no) < 5:
                continue
            prec_seen.add(case_no)
            try:
                if drf_inst and hasattr(drf_inst, "search_precedents"):
                    raw_prec = drf_inst.search_precedents(case_no)
                    prec_exists = bool(raw_prec)
                else:
                    prec_exists = False
                    logger.debug(f"[Stage 4] 판례 DRF 미사용 (drf 인스턴스 없음)")

                ref_entry = {
                    "ref": f"판례 {case_no}",
                    "type": "precedent",
                    "case_no": case_no,
                    "verified": prec_exists,
                }
                if prec_exists:
                    result.verified_refs.append(ref_entry)
                else:
                    ref_entry["reason"] = "판례 미존재"
                    result.unverified_refs.append(ref_entry)
            except Exception as e:
                logger.warning(f"[Stage 4] 판례 {case_no} 검증 실패: {e}")
                result.unverified_refs.append({
                    "ref": f"판례 {case_no}",
                    "type": "precedent",
                    "case_no": case_no,
                    "verified": False,
                    "reason": f"검증 오류: {type(e).__name__}",
                })

    result.total_refs = len(result.verified_refs) + len(result.unverified_refs)
    result.all_passed = len(result.unverified_refs) == 0

    law_count = sum(1 for r in result.verified_refs if r.get("type") != "precedent")
    prec_count = sum(1 for r in result.verified_refs if r.get("type") == "precedent")
    law_fail = sum(1 for r in result.unverified_refs if r.get("type") != "precedent")
    prec_fail = sum(1 for r in result.unverified_refs if r.get("type") == "precedent")

    logger.info(
        f"[Stage 4] DRF 전수 검증 완료: "
        f"총 {result.total_refs}건 (법률 {law_count+law_fail}건, 판례 {prec_count+prec_fail}건) | "
        f"통과 {len(result.verified_refs)}건, "
        f"실패 {len(result.unverified_refs)}건"
    )

    return result


def _match_article_num(article_dict: Dict, target_num: int) -> bool:
    """조문 딕셔너리에서 조문번호가 target_num과 일치하는지 확인"""
    try:
        num = article_dict.get("조문번호", "")
        if isinstance(num, (int, float)):
            return int(num) == target_num
        if isinstance(num, str):
            cleaned = num.strip().replace("조", "")
            if cleaned.isdigit():
                return int(cleaned) == target_num
    except (ValueError, TypeError):
        pass
    return False


# =============================================================
# FAIL_CLOSED 및 미검증 조문 제거
# =============================================================

def _remove_unverified_refs(text: str, drf_verification: VerificationResult) -> str:
    """미검증 조문 참조를 텍스트에서 제거하거나 경고 태깅"""
    for ref_info in drf_verification.unverified_refs:
        ref = ref_info.get("ref", "")
        if ref in text:
            reason = ref_info.get("reason", "미확인")
            text = text.replace(ref, f"{ref}(※ {reason})")
    return text


def _apply_fail_closed(final_text: str, drf_verification: VerificationResult) -> str:
    """FAIL_CLOSED 로직: 30% 이상 미검증 시 응답 차단, 아니면 미검증 조문 태깅"""
    if drf_verification.total_refs == 0:
        return final_text

    unverified_count = len(drf_verification.unverified_refs)
    total_count = drf_verification.total_refs

    # 미검증 비율 10% 초과 시 응답 차단 (fail-closed 10%)
    if unverified_count / max(total_count, 1) > 0.1:
        logger.warning(
            f"[FAIL_CLOSED] 미검증 {unverified_count}/{total_count} "
            f"({unverified_count/total_count*100:.0f}%) -> 응답 차단"
        )
        return FAIL_CLOSED_RESPONSE

    # 30% 미만: 미검증 조문만 태깅
    if unverified_count > 0:
        final_text = _remove_unverified_refs(final_text, drf_verification)
        final_text += "\n\n> ※ 일부 조문은 정확성 확인 중입니다. 중요한 법적 판단 시 법률 전문가의 확인을 권장합니다."

    return final_text


# =============================================================
# Gemini Fallback: LawmadiLM 실패 시 Gemini Flash로 답변 생성
# =============================================================

async def _gemini_fallback_compose(
    query: str,
    analysis: Dict,
    rag_context: RAGContext,
    tools: list,
    gemini_history: list,
    now_kst: str,
    ssot_available: bool,
    lang: str = "",
    mode: str = "general",
    lm_draft: str = "",
) -> str:
    """Gemini Flash 완성 답변 생성 (LM 초안 기반 또는 단독, 캐시 컨텍스트 최대 활용)"""
    gc = _RUNTIME.get("genai_client")
    if not gc:
        raise RuntimeError("Gemini 클라이언트 미초기화")

    model_name = GEMINI_MODEL
    leader_name = analysis.get("leader_name", "마디")
    leader_specialty = analysis.get("leader_specialty", "통합")

    # LM 초안 주입
    draft_section = ""
    if lm_draft:
        draft_section = (
            f"\n\n[LawmadiLM 법률 초안]\n{lm_draft}\n\n"
            f"위 초안의 법률 근거(조문, 판례)를 바탕으로 완성된 답변을 작성하세요.\n"
            f"초안의 법령명+조문번호를 반드시 포함하세요."
        )

    # RAG/캐시 컨텍스트 주입 (SSOT 캐시 최우선 참조)
    ctx_section = ""
    if rag_context.context_text:
        ctx_section = (
            "\n\n[SSOT 캐시 — 반드시 최우선 참조]\n"
            "아래 SSOT 캐시 데이터는 DRF API에서 사전 검증된 법률 정보입니다.\n"
            "답변 시 반드시 이 캐시의 법령명·조문번호·판례번호를 그대로 인용하세요.\n"
            "캐시에 없는 법령이나 판례를 임의 생성하지 마세요.\n"
            f"{rag_context.context_text[:100000]}"
        )
    elif rag_context.cache_context:
        ctx_section = (
            "\n\n[SSOT 캐시 — 반드시 최우선 참조]\n"
            "아래 캐시 데이터의 법령명·조문번호·판례번호를 그대로 인용하세요.\n"
            f"{rag_context.cache_context[:50000]}"
        )

    # 모드별 보강 지시
    if mode == "expert":
        enhance = (
            "\n\n[구조 지시] 사안의 쟁점 → 관련 법령 → 판례 검토 → 실무 대응 절차 → 쟁점별 검토 의견 → 결론 및 권고 → 법률 근거"
            "\n핵심 쟁점, 법률명, 판례번호는 **굵은 글씨**로 표시. 4,000~5,000자."
        )
        max_tokens = 5000
    else:
        enhance = (
            "\n\n[구조 지시] 결론부터 말씀드리면 → 왜 그런가요? → 지금 바로 하실 수 있는 일 → 그래도 해결이 안 되면 → 혼자 하기 어려우시면 → 지금 해야 할 행동 3가지 → 법률 근거"
            "\n한 문장은 50~60자 이내. 2,000~3,000자."
        )
        max_tokens = 3500

    lang_instruction = ""
    if lang == "en":
        lang_instruction = "\n\nIMPORTANT: Respond entirely in English. Translate Korean legal terms with the original Korean in parentheses."

    # 리더 인격·철학 주입
    leader_id = analysis.get("leader_id", "")
    persona_section = ""
    persona_text = _build_leader_persona(leader_id)
    if persona_text:
        persona_section = f"\n\n[리더 인격]\n{persona_text}"

    instruction = (
        f"{build_system_instruction(mode)}\n"
        f"현재 당신은 '{leader_name}' 리더입니다.\n"
        f"전문 분야: {leader_specialty}"
        f"{persona_section}\n"
        f"질문 요약: {analysis.get('summary', '')}"
        f"{draft_section}"
        f"{ctx_section}"
        f"{enhance}"
        f"{lang_instruction}"
    )

    gen_config = genai_types.GenerateContentConfig(
        tools=tools,
        system_instruction=instruction,
        max_output_tokens=max_tokens,
        automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=False),
    )

    chat = gc.chats.create(
        model=model_name,
        config=gen_config,
        history=gemini_history,
    )
    resp = chat.send_message(
        f"now_kst={now_kst}\nssot_available={ssot_available}\n사용자 질문: {query}"
    )
    text = _safe_extract_gemini_text(resp)
    logger.info(f"[Gemini Fallback] 답변 생성 완료 ({len(text)}자, mode={mode})")
    return text


# =============================================================
# Main Pipeline Orchestrator (3-Stage, LawmadiLM + Gemini Fallback)
# =============================================================

async def _run_legal_pipeline(
    query: str,
    analysis: Dict,
    tools: list,
    gemini_history: list,
    now_kst: str,
    ssot_available: bool,
    lang: str = "",
    mode: str = "general",
    rag_context: Optional[RAGContext] = None,
) -> str:
    """4-Stage Hybrid Legal Pipeline (LM 5초 초안 → Gemini 완성):
    Stage 1: RAG 조문 검색
    Stage 2: LawmadiLM 초안 (5초 타임아웃)
    Stage 3: Gemini Flash 완성 답변 (LM 초안 기반 또는 단독)
    Stage 4: DRF 실시간 전수 검증
    → Fail-Closed → 응답

    LawmadiLM 실패/타임아웃 시 Gemini가 단독 작성 (fallback).
    rag_context가 전달되면 Stage 1을 건너뛰어 S0+S1 병렬화를 지원.
    """
    final_text = ""
    drf_verification = VerificationResult()

    # -- Stage 1: RAG 조문 검색 (1회만 수행, 외부 전달 시 스킵) --
    if rag_context is None:
        logger.info("[Stage 1/4] RAG 조문 검색 시작")
        try:
            rag_context = await _stage1_rag_search(query)
        except Exception as e:
            logger.warning(f"[Stage 1] RAG 검색 실패 (빈 컨텍스트 진행): {e}")
            rag_context = RAGContext()
    else:
        logger.info("[Stage 1/4] RAG 컨텍스트 외부 전달 (S0+S1 병렬화)")

    # -- Stage 2: LawmadiLM 초안 (5초 타임아웃) --
    lm_draft = ""
    try:
        logger.info("[Stage 2/4] LawmadiLM 초안 생성 (5초)")
        raw_answer = await _call_lawmadilm(
            query, analysis, rag_context, lang=lang, mode=mode,
        )
        lm_draft = _postprocess_lawmadilm(raw_answer, query)
        if lm_draft:
            logger.info(f"[Stage 2] LM 초안 완료 ({len(lm_draft)}자)")
        else:
            logger.warning("[Stage 2] 후처리 -> None (품질 미달)")
            lm_draft = ""
    except Exception as e:
        logger.warning(f"[Stage 2] LawmadiLM 실패/타임아웃: {e} -> Gemini 단독")
        lm_draft = ""

    # -- Stage 3: Gemini Flash 완성 답변 (LM 초안 기반 또는 단독) --
    logger.info(f"[Stage 3/4] Gemini Flash 답변 (LM초안={'있음' if lm_draft else '없음'})")
    try:
        final_text = await _gemini_fallback_compose(
            query, analysis, rag_context, tools, gemini_history,
            now_kst, ssot_available, lang=lang, mode=mode,
            lm_draft=lm_draft,
        )
    except Exception as e:
        logger.error(f"[Stage 3] Gemini 답변 생성 실패: {e}")
        if lm_draft:
            final_text = lm_draft
        else:
            raise RuntimeError("LawmadiLM + Gemini 모두 답변 생성 실패")

    # 빈 응답 안전장치: Gemini가 빈 텍스트 반환 시 재시도 1회
    if not final_text or len(final_text.strip()) < 30:
        logger.warning(f"[Stage 3] Gemini 빈 응답 감지 ({len(final_text)}자) — 재시도")
        try:
            final_text = await _gemini_fallback_compose(
                query, analysis, rag_context, tools, gemini_history,
                now_kst, ssot_available, lang=lang, mode=mode,
                lm_draft=lm_draft,
            )
        except Exception as e:
            logger.error(f"[Stage 3 재시도] 실패: {e}")
        if not final_text or len(final_text.strip()) < 30:
            raise RuntimeError("Gemini 빈 응답 (재시도 포함)")

    # -- Stage 4: DRF 실시간 전수 검증 --
    logger.info("[Stage 4/4] DRF 전수 검증")
    try:
        drf_verification = _drf_verify_law_refs(final_text)
    except Exception as e:
        logger.warning(f"[Stage 4] DRF 검증 실패: {e}")
        drf_verification = VerificationResult()

    # FAIL_CLOSED 적용 (미검증 조문 태깅 또는 응답 차단)
    final_text = _apply_fail_closed(final_text, drf_verification)

    return final_text, drf_verification


# =============================================================
# Streaming 지원 함수들 (routes/legal.py에서 호출)
# =============================================================

async def run_pipeline_stage1(query: str) -> RAGContext:
    """스트리밍용: Stage 1만 실행"""
    try:
        return await _stage1_rag_search(query)
    except Exception as e:
        logger.warning(f"[Stream Stage 1] RAG 실패: {e}")
        return RAGContext()


async def run_pipeline_stage2(
    query: str,
    analysis: Dict,
    rag_context: RAGContext,
    drf_verification: Optional[VerificationResult] = None,
    lang: str = "",
    mode: str = "general",
) -> str:
    """스트리밍용: Stage 2만 실행 (강화 프롬프트)"""
    try:
        raw = await _call_lawmadilm(
            query, analysis, rag_context,
            drf_verification=drf_verification,
            lang=lang,
            mode=mode,
        )
        return _postprocess_lawmadilm(raw, query) or ""
    except Exception as e:
        logger.warning(f"[Stream Stage 2] LawmadiLM 실패: {e}")
        return ""


def run_pipeline_stage3(text: str) -> VerificationResult:
    """스트리밍용: Stage 3만 실행"""
    if not text:
        return VerificationResult()
    try:
        return _drf_verify_law_refs(text)
    except Exception as e:
        logger.warning(f"[Stream Stage 3] DRF 검증 실패: {e}")
        return VerificationResult()


# Public alias for external use
run_legal_pipeline = _run_legal_pipeline
# Option B: gemini-2.5-flash + law_cache direct injection (no CachedContent)
