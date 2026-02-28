"""
Law reference verification tool for Lawmadi ADK.

Ported from core/pipeline.py Stage 4 DRF verification logic.
Provides an ADK FunctionTool for verifying law references in generated responses.

Key functions:
- verify_law_references(response_text) -- extract & verify all law/precedent refs via DRF
- strip_unverified_sentences(response_text, unverified_refs) -- remove sentences with bad refs
"""

import asyncio
import concurrent.futures
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger("LawmadiADK.Verify")

# ---------------------------------------------------------------------------
# DRF API config
# ---------------------------------------------------------------------------
_DRF_BASE_URL = "https://www.law.go.kr/DRF/lawSearch.do"
_LAW_SERVICE_URL = "https://www.law.go.kr/DRF/lawService.do"
_DRF_TIMEOUT_SEC = int(os.getenv("DRF_TIMEOUT_SEC", "8"))


def _get_drf_key() -> str:
    """DRF API 키를 호출 시점에 로드 (Agent Engine env_vars 지연 주입 대응)."""
    return os.getenv("LAWGO_DRF_OC", "")

# ---------------------------------------------------------------------------
# Regex patterns for extracting law references
# ---------------------------------------------------------------------------
# CRITICAL: The original regex (?:[가-힣]+\s*)+ causes catastrophic backtracking.
# Using the FIXED pattern [가-힣]+(?:\s+[가-힣]+)* instead.
_LAW_REF_PATTERN = re.compile(
    r'([가-힣]+(?:\s+[가-힣]+)*\s*(?:등에\s+관한\s+)?'
    r'(?:법률|법|시행령|시행규칙|규정|조례))\s*'
    r'제(\d+)조(의\d+)?\s*(?:제(\d+)항)?'
)

_PREC_REF_PATTERN = re.compile(
    r'((?:대법원|대법|헌법재판소|헌재|서울고등법원|서울고법|서울중앙지방법원)\s*'
    r'(\d{4})\s*[.]\s*(\d{1,2})\s*[.]\s*\d{1,2}\s*[.]?\s*선고\s*'
    r'(\d{2,4}[가-힣]+\d+)\s*(?:판결|결정))'
)

_PREC_SIMPLE_PATTERN = re.compile(
    r'(\d{2,4}'
    r'(?:헌바|헌마|헌가|헌나|헌라|헌사|헌아|헌자|'
    r'다|나|가|마|카|타|파|라|바|사|아|자|차|하|'
    r'두|누|구|무|부|수|우|주|추|후|그|드|스|으)'
    r'(?:합)?\d{2,6})'
)


# ---------------------------------------------------------------------------
# DRF API helpers (standalone, no dependency on connectors/)
# ---------------------------------------------------------------------------

def _drf_law_search(law_name: str) -> Optional[Dict]:
    """Call DRF lawSearch.do to search for a law by name.

    Returns the raw JSON response or None on failure.
    """
    api_key = _get_drf_key()
    if not api_key:
        logger.warning("[Verify] LAWGO_DRF_OC not set -- cannot call DRF")
        return None

    params = {
        "OC": api_key,
        "target": "law",
        "type": "JSON",
        "query": law_name,
    }
    try:
        r = requests.get(
            _DRF_BASE_URL,
            params=params,
            timeout=_DRF_TIMEOUT_SEC,
        )
        if r.status_code != 200:
            logger.warning(f"[Verify] DRF lawSearch HTTP {r.status_code} for '{law_name}'")
            return None
        content_type = r.headers.get("Content-Type", "")
        if "json" not in content_type.lower():
            logger.warning(f"[Verify] DRF unexpected Content-Type: {content_type}")
            return None
        return r.json()
    except Exception as e:
        logger.warning(f"[Verify] DRF lawSearch error for '{law_name}': {e}")
        return None


def _drf_law_service(mst: str) -> Optional[Dict]:
    """Call DRF lawService.do to get article details by MST (법령일련번호).

    Returns the raw JSON response or None on failure.
    """
    api_key = _get_drf_key()
    if not api_key:
        return None

    params = {
        "OC": api_key,
        "target": "law",
        "MST": mst,
        "type": "JSON",
    }
    try:
        r = requests.get(
            _LAW_SERVICE_URL,
            params=params,
            timeout=max(_DRF_TIMEOUT_SEC, 10),
        )
        if r.status_code != 200:
            return None
        return r.json()
    except Exception as e:
        logger.warning(f"[Verify] lawService error for MST={mst}: {e}")
        return None


def _drf_prec_search(case_no: str) -> Optional[Dict]:
    """Call DRF precSearch.do (target=prec) to search for a precedent.

    Returns the raw JSON response or None on failure.
    """
    api_key = _get_drf_key()
    if not api_key:
        return None

    params = {
        "OC": api_key,
        "target": "prec",
        "type": "JSON",
        "query": case_no,
    }
    try:
        r = requests.get(
            _DRF_BASE_URL,
            params=params,
            timeout=_DRF_TIMEOUT_SEC,
        )
        if r.status_code != 200:
            return None
        content_type = r.headers.get("Content-Type", "")
        if "json" not in content_type.lower():
            return None
        return r.json()
    except Exception as e:
        logger.warning(f"[Verify] DRF precSearch error for '{case_no}': {e}")
        return None


# ---------------------------------------------------------------------------
# DRF response parsing helpers (ported from core/pipeline.py)
# ---------------------------------------------------------------------------

def _extract_mst_from_search(search_result: Dict, law_name: str) -> Optional[str]:
    """Extract 법령일련번호 (MST) from a lawSearch.do response.

    Priority: exact name match > startsWith match > contains match.
    """
    if not search_result:
        return None
    try:
        law_list = search_result.get("LawSearch", {}).get("law", [])
        if isinstance(law_list, dict):
            law_list = [law_list]
        if not isinstance(law_list, list):
            return None

        # Priority 1: exact match
        for law in law_list:
            name = law.get("법령명한글", "")
            if name == law_name:
                return law.get("법령일련번호")

        # Priority 2: starts with law_name and is a 법률
        for law in law_list:
            name = law.get("법령명한글", "")
            if name.startswith(law_name) and law.get("법령구분명") == "법률":
                return law.get("법령일련번호")

        # Priority 3: law_name contained in name
        for law in law_list:
            name = law.get("법령명한글", "")
            if law_name in name and law.get("법령구분명") == "법률":
                return law.get("법령일련번호")

    except Exception as e:
        logger.debug(f"[Verify] MST extraction failed for '{law_name}': {e}")

    return None


def _extract_articles_from_drf(raw_response: Any) -> List[Dict]:
    """Extract article list from a DRF lawService.do response.

    lawService.do structure: {"법령": {"조문": {"조문단위": [...]}}}
    Each 조문단위: {"조문번호": "3", "조문내용": "제3조(대항력) ...", ...}
    """
    if not raw_response:
        return []

    articles: List[Dict] = []
    try:
        if isinstance(raw_response, dict):
            # lawService.do response: {"법령": {"조문": {"조문단위": [...]}}}
            law_root = raw_response.get("법령", raw_response)
            if isinstance(law_root, dict):
                jo_section = law_root.get("조문", {})
                if isinstance(jo_section, dict):
                    jo_list = jo_section.get("조문단위", [])
                    if isinstance(jo_list, dict):
                        jo_list = [jo_list]
                    if isinstance(jo_list, list):
                        articles.extend(jo_list)

            # Fallback: LawSearch response structure
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

            # Direct list format
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
        logger.debug(f"[Verify] Article extraction failed: {e}")

    return articles


def _match_article_num(article_dict: Dict, target_num: int, suffix: str = "") -> bool:
    """Check if an article dict's 조문번호 matches target_num + suffix.

    suffix examples: "의2", "의3" (제839조의2 -> target_num=839, suffix="의2")
    DRF 조문번호 forms: "10", "10의4", "839의2", "제10조의4", etc.
    """
    try:
        raw = article_dict.get("조문번호", "")
        # Normalize: remove "제", "조"
        num_str = str(raw).strip().replace("제", "").replace("조", "").strip()
        target_str = f"{target_num}{suffix}" if suffix else str(target_num)

        if num_str == target_str:
            return True

        # Plain numeric comparison when no suffix
        if not suffix and num_str.isdigit():
            return int(num_str) == target_num

    except (ValueError, TypeError):
        pass
    return False


def _get_article_text(articles: List[Dict], article_num: int, suffix: str = "") -> Optional[str]:
    """Return the text of a specific article from the article list."""
    art_label = f"제{article_num}조{suffix}"
    for art in articles:
        try:
            if _match_article_num(art, article_num, suffix):
                content = (
                    art.get("조문내용", "")
                    or art.get("조문", "")
                    or art.get("content", "")
                )
                title = art.get("조문제목", "") or art.get("제목", "")
                if content:
                    return f"{art_label}({title}) {content}" if title else f"{art_label} {content}"
        except (ValueError, TypeError):
            continue
    return None


# ---------------------------------------------------------------------------
# Full law article retrieval: lawSearch -> MST -> lawService
# ---------------------------------------------------------------------------

def _get_law_articles(law_name: str) -> Optional[Any]:
    """Retrieve law articles for a given law name via DRF API.

    Two-step process:
    1. lawSearch.do to find MST (법령일련번호)
    2. lawService.do to get article details
    """
    # Step 1: lawSearch.do to get MST
    search_result = _drf_law_search(law_name)
    if not search_result:
        return None

    mst = _extract_mst_from_search(search_result, law_name)
    if not mst:
        logger.warning(f"[Verify] MST not found for '{law_name}'")
        return None

    logger.info(f"[Verify] {law_name} -> MST={mst}")

    # Step 2: lawService.do to get articles
    return _drf_law_service(mst)


# ---------------------------------------------------------------------------
# Precedent verification helpers
# ---------------------------------------------------------------------------

def _extract_precedent_summary(raw_prec: Any) -> str:
    """Extract 판시사항/판결요지/결정요지 from DRF precedent response."""
    summary_parts: List[str] = []
    try:
        items: List[Dict] = []
        if isinstance(raw_prec, dict):
            prec_root = raw_prec.get("PrecSearch", raw_prec)
            if isinstance(prec_root, dict):
                prec_list = prec_root.get("prec", [])
                if isinstance(prec_list, dict):
                    prec_list = [prec_list]
                items = prec_list if isinstance(prec_list, list) else []
            for key in ["판시사항", "판결요지", "결정요지", "이유"]:
                val = raw_prec.get(key, "")
                if val and isinstance(val, str):
                    summary_parts.append(val[:500])
        elif isinstance(raw_prec, list):
            items = raw_prec

        for item in items[:1]:
            if isinstance(item, dict):
                for key in ["판시사항", "판결요지", "결정요지", "이유"]:
                    val = item.get(key, "")
                    if val and isinstance(val, str):
                        summary_parts.append(val[:500])
    except Exception as e:
        logger.debug(f"[Verify] Precedent summary extraction failed: {e}")

    return " ".join(summary_parts)[:1500]


def _extract_cited_context(text: str, case_no: str, window: int = 3) -> str:
    """Extract context around a case number citation in the response text."""
    lines = text.split("\n")
    context_lines: List[str] = []
    for i, line in enumerate(lines):
        if case_no in line:
            start = max(0, i - window)
            end = min(len(lines), i + window + 1)
            context_lines.extend(lines[start:end])
    return " ".join(context_lines)[:2000]


def _check_precedent_content_match(drf_summary: str, cited_context: str) -> bool:
    """Check if DRF precedent summary matches the cited context in the response.

    Passes if 3+ legal keywords match or 20%+ keyword overlap.
    """
    if not drf_summary or not cited_context:
        return False

    # Extract key legal terms (2-6 char Korean nouns)
    drf_keywords = set(re.findall(r'[가-힣]{2,6}', drf_summary))

    # Remove overly common stopwords
    stopwords = {
        "하였다", "있다", "없다", "한다", "이다", "경우", "것으로", "대하여",
        "아니라", "하여", "않는", "되는", "위한", "따라", "대한", "관한",
        "같은", "있는", "없는", "하는", "된다", "이에", "그리고",
    }
    drf_keywords -= stopwords

    if len(drf_keywords) < 3:
        # Too few keywords -- pass based on existence alone
        return True

    match_count = sum(1 for kw in drf_keywords if kw in cited_context)
    match_ratio = match_count / len(drf_keywords) if drf_keywords else 0

    return match_count >= 3 or match_ratio >= 0.2


# ---------------------------------------------------------------------------
# Reference extraction from response text
# ---------------------------------------------------------------------------

def _extract_law_refs(text: str) -> List[Tuple[str, int, str, str]]:
    """Extract law article references from text.

    Returns list of (law_name, article_num, suffix, display_key) tuples.
    Deduplicates by display_key.
    """
    refs = _LAW_REF_PATTERN.findall(text)
    seen: set = set()
    items: List[Tuple[str, int, str, str]] = []
    for law_name, article_num_str, suffix_str, paragraph_str in refs:
        law_name = law_name.strip()
        article_num = int(article_num_str)
        suffix = suffix_str.strip() if suffix_str else ""
        key = f"{law_name} 제{article_num}조{suffix}"
        if key in seen:
            continue
        seen.add(key)
        items.append((law_name, article_num, suffix, key))
    return items


def _extract_prec_refs(text: str) -> List[str]:
    """Extract unique precedent case numbers from text.

    Returns deduplicated list of case number strings.
    """
    prec_refs = _PREC_REF_PATTERN.findall(text)
    if prec_refs:
        case_numbers = [p[3] for p in prec_refs]
    else:
        case_numbers = _PREC_SIMPLE_PATTERN.findall(text)

    seen: set = set()
    unique: List[str] = []
    for cn in case_numbers:
        cn = cn.strip()
        if cn in seen or len(cn) < 5:
            continue
        seen.add(cn)
        unique.append(cn)
    return unique


# ---------------------------------------------------------------------------
# Core verification function (sync -- runs DRF calls in threads)
# ---------------------------------------------------------------------------

async def _verify_single_law(law_name: str) -> Tuple[str, Optional[Any]]:
    """Fetch law articles for a single law name in a thread."""
    try:
        raw = await asyncio.to_thread(_get_law_articles, law_name)
        return law_name, raw
    except Exception as e:
        logger.warning(f"[Verify] Failed to fetch '{law_name}': {e}")
        return law_name, None


async def _verify_single_prec(case_no: str) -> Tuple[str, Optional[Dict], Optional[Exception]]:
    """Fetch precedent data for a single case number in a thread."""
    try:
        raw = await asyncio.to_thread(_drf_prec_search, case_no)
        return case_no, raw, None
    except Exception as e:
        return case_no, None, e


def verify_law_references(response_text: str) -> dict:
    """Verify all law and precedent references in a response text via DRF API.

    This is the main ADK FunctionTool function. It:
    1. Extracts law article references (e.g. "주택임대차보호법 제3조") using regex
    2. Extracts precedent references (e.g. "대법원 2020. 7. 9. 선고 2018다12345 판결")
    3. Verifies each reference against the DRF (법제처) API
    4. Returns verification results with pass/fail status

    Args:
        response_text: The generated legal response text to verify.

    Returns:
        dict with keys:
            - status: "success" | "error" | "no_refs"
            - total_refs: int -- total number of unique references found
            - verified_refs: list[dict] -- references that passed verification
            - unverified_refs: list[dict] -- references that failed verification
            - verification_ratio: float -- verified / total (0.0-1.0)
            - all_passed: bool -- True if every reference verified
            - fail_closed: bool -- True if any law ref is unverified (ratio < 1.0)
            - summary: str -- human-readable summary of verification results
    """
    if not response_text or not response_text.strip():
        return {
            "status": "no_refs",
            "total_refs": 0,
            "verified_refs": [],
            "unverified_refs": [],
            "verification_ratio": 1.0,
            "all_passed": True,
            "fail_closed": False,
            "summary": "응답 텍스트가 비어 있습니다.",
        }

    # ── 1) Extract references ──
    law_items = _extract_law_refs(response_text)
    prec_items = _extract_prec_refs(response_text)

    if not law_items and not prec_items:
        return {
            "status": "no_refs",
            "total_refs": 0,
            "verified_refs": [],
            "unverified_refs": [],
            "verification_ratio": 1.0,
            "all_passed": True,
            "fail_closed": False,
            "summary": "법률/판례 참조가 발견되지 않았습니다.",
        }

    # Check DRF API key (호출 시점 로드)
    if not _get_drf_key():
        return {
            "status": "error",
            "total_refs": len(law_items) + len(prec_items),
            "verified_refs": [],
            "unverified_refs": [],
            "verification_ratio": 0.0,
            "all_passed": False,
            "fail_closed": False,
            "summary": "DRF API 키(LAWGO_DRF_OC)가 설정되지 않아 검증을 수행할 수 없습니다.",
        }

    # ── 2) Run async verification ──
    # Agent Engine은 async 환경 — 별도 스레드에서 새 이벤트 루프 실행
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                asyncio.run,
                _async_verify_all(response_text, law_items, prec_items),
            )
            return future.result(timeout=30.0)
    except Exception as e:
        logger.error(f"[Verify] Async verification failed: {e}")
        return {
            "status": "error",
            "total_refs": len(law_items) + len(prec_items),
            "verified_refs": [],
            "unverified_refs": [],
            "verification_ratio": 0.0,
            "all_passed": False,
            "fail_closed": False,
            "summary": f"검증 중 오류 발생: {e}",
        }


async def _async_verify_all(
    response_text: str,
    law_items: List[Tuple[str, int, str, str]],
    prec_items: List[str],
) -> dict:
    """Async core: verify all law + precedent references concurrently.

    Groups law references by law_name and verifies once per law.
    Total timeout: 25 seconds for all DRF calls.
    """
    verified_refs: List[Dict] = []
    unverified_refs: List[Dict] = []

    # Group law items by law_name for efficient batching
    unique_laws: set = set()
    for law_name, _, _, _ in law_items:
        unique_laws.add(law_name)

    # ── Fetch all law data + precedent data concurrently ──
    law_tasks = [_verify_single_law(ln) for ln in unique_laws]
    prec_tasks = [_verify_single_prec(cn) for cn in prec_items]

    drf_failed = False
    all_fetch_results: List[Any] = []

    if law_tasks or prec_tasks:
        try:
            all_fetch_results = await asyncio.wait_for(
                asyncio.gather(*law_tasks, *prec_tasks, return_exceptions=True),
                timeout=25.0,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"[Verify] DRF fetch timeout (25s) -- "
                f"laws: {len(law_tasks)}, precs: {len(prec_tasks)}"
            )
            drf_failed = True

    if drf_failed:
        total = len(law_items) + len(prec_items)
        return {
            "status": "error",
            "total_refs": total,
            "verified_refs": [],
            "unverified_refs": [],
            "verification_ratio": 0.0,
            "all_passed": False,
            "fail_closed": True,
            "summary": f"DRF API 타임아웃 (25초). 법률 {len(law_tasks)}건, 판례 {len(prec_tasks)}건 검증 실패.",
        }

    # ── Parse fetch results ──
    law_articles_cache: Dict[str, Any] = {}
    law_result_count = len(law_tasks)

    for i, res in enumerate(all_fetch_results[:law_result_count]):
        if isinstance(res, BaseException):
            logger.warning(f"[Verify] Law fetch exception: {res}")
            continue
        try:
            ln, raw = res
            law_articles_cache[ln] = raw
        except (ValueError, TypeError) as e:
            logger.warning(f"[Verify] Law result parse error: {e}")

    prec_results_raw: List[Tuple[str, Optional[Dict], Optional[Exception]]] = []
    for res in all_fetch_results[law_result_count:]:
        if isinstance(res, BaseException):
            logger.warning(f"[Verify] Precedent fetch exception: {res}")
            continue
        prec_results_raw.append(res)

    # ── Verify each law article reference ──
    for law_name, article_num, suffix, key in law_items:
        try:
            raw = law_articles_cache.get(law_name)
            law_exists = bool(raw)
            article_exists = False
            article_text = None
            articles: List[Dict] = []

            if raw:
                articles = _extract_articles_from_drf(raw)
                if articles:
                    article_exists = any(
                        _match_article_num(a, article_num, suffix) for a in articles
                    )
                    article_text = _get_article_text(articles, article_num, suffix)

            ref_entry: Dict[str, Any] = {
                "ref": key,
                "type": "law",
                "law_name": law_name,
                "article_num": article_num,
                "law_exists": law_exists,
                "article_exists": article_exists,
                "article_text": article_text[:300] if article_text else None,
                "verified": law_exists and article_exists,
            }

            if ref_entry["verified"]:
                verified_refs.append(ref_entry)
                logger.info(f"[Verify] PASS: {key}")
            else:
                reason = (
                    "법령 미존재" if not law_exists
                    else f"제{article_num}조{suffix} 미존재 (총 {len(articles)}개 조문 중)"
                )
                ref_entry["reason"] = reason
                unverified_refs.append(ref_entry)
                logger.warning(f"[Verify] FAIL: {key} -- {reason}")

        except Exception as e:
            logger.warning(f"[Verify] {key} verification error: {e}")
            unverified_refs.append({
                "ref": key,
                "type": "law",
                "law_name": law_name,
                "article_num": article_num,
                "law_exists": False,
                "article_exists": False,
                "article_text": None,
                "verified": False,
                "reason": f"검증 오류: {type(e).__name__}: {e}",
            })

    # ── Verify each precedent reference ──
    for case_no, raw_prec, fetch_err in prec_results_raw:
        try:
            if fetch_err:
                raise fetch_err

            prec_exists = bool(raw_prec)
            content_match = False
            drf_summary = ""

            if prec_exists and raw_prec:
                drf_summary = _extract_precedent_summary(raw_prec)
                if drf_summary:
                    cited_context = _extract_cited_context(response_text, case_no)
                    content_match = _check_precedent_content_match(drf_summary, cited_context)

            verified = prec_exists and (content_match or not drf_summary)

            ref_entry = {
                "ref": f"판례 {case_no}",
                "type": "precedent",
                "case_no": case_no,
                "verified": verified,
                "prec_exists": prec_exists,
                "content_match": content_match,
            }

            if verified:
                verified_refs.append(ref_entry)
                logger.info(
                    f"[Verify] PASS: 판례 {case_no} "
                    f"(exists={prec_exists}, content_match={content_match})"
                )
            else:
                reason = "판례 미존재" if not prec_exists else "판시사항 내용 불일치"
                ref_entry["reason"] = reason
                unverified_refs.append(ref_entry)
                logger.warning(f"[Verify] FAIL: 판례 {case_no} -- {reason}")

        except Exception as e:
            logger.warning(f"[Verify] 판례 {case_no} verification error: {e}")
            unverified_refs.append({
                "ref": f"판례 {case_no}",
                "type": "precedent",
                "case_no": case_no,
                "verified": False,
                "reason": f"검증 오류: {type(e).__name__}: {e}",
            })

    # ── Compute final results ──
    total_refs = len(verified_refs) + len(unverified_refs)
    verification_ratio = len(verified_refs) / max(total_refs, 1)
    all_passed = len(unverified_refs) == 0

    # FAIL_CLOSED: any unverified law reference triggers caution
    law_unverified = [r for r in unverified_refs if r.get("type") != "precedent"]
    law_total = (
        sum(1 for r in verified_refs if r.get("type") != "precedent")
        + len(law_unverified)
    )
    law_ratio = len(law_unverified) / max(law_total, 1) if law_total > 0 else 0
    fail_closed = law_ratio > 0.001  # Any unverified law ref -> fail_closed

    # Build human-readable summary
    law_pass = sum(1 for r in verified_refs if r.get("type") != "precedent")
    law_fail = len(law_unverified)
    prec_pass = sum(1 for r in verified_refs if r.get("type") == "precedent")
    prec_fail = sum(1 for r in unverified_refs if r.get("type") == "precedent")

    summary_parts = [
        f"총 {total_refs}건 검증 완료.",
        f"법률: {law_pass}/{law_pass + law_fail}건 통과.",
        f"판례: {prec_pass}/{prec_pass + prec_fail}건 통과.",
    ]
    if fail_closed:
        summary_parts.append(
            f"주의: 미검증 법조문 {law_fail}건 발견. "
            "해당 조문이 포함된 문장의 정확성을 확인해 주세요."
        )
    if unverified_refs:
        bad_refs_str = ", ".join(r.get("ref", "?") for r in unverified_refs[:5])
        if len(unverified_refs) > 5:
            bad_refs_str += f" 외 {len(unverified_refs) - 5}건"
        summary_parts.append(f"미검증 참조: {bad_refs_str}")

    logger.info(
        f"[Verify] Complete: {total_refs} refs "
        f"(law {law_pass+law_fail}, prec {prec_pass+prec_fail}) | "
        f"pass {len(verified_refs)}, fail {len(unverified_refs)}"
    )

    return {
        "status": "success",
        "total_refs": total_refs,
        "verified_refs": verified_refs,
        "unverified_refs": unverified_refs,
        "verification_ratio": round(verification_ratio, 4),
        "all_passed": all_passed,
        "fail_closed": fail_closed,
        "summary": " ".join(summary_parts),
    }


# ---------------------------------------------------------------------------
# Helper: strip sentences containing unverified references
# ---------------------------------------------------------------------------

def strip_unverified_sentences(response_text: str, unverified_refs: list) -> dict:
    """Remove sentences containing unverified law references from the response text.

    This is used when FAIL_CLOSED is triggered but the response can be partially
    salvaged by removing only the problematic sentences.

    Args:
        response_text: The original response text.
        unverified_refs: List of dicts from verify_law_references()["unverified_refs"].
            Each dict should have a "ref" key (e.g. "주택임대차보호법 제3조").

    Returns:
        dict with keys:
            - stripped_text: str -- the cleaned text with offending sentences removed
            - removed_count: int -- number of lines/sentences removed
            - remaining_length: int -- character length of stripped_text
            - removed_refs: list[str] -- the ref strings that were found and removed
    """
    if not response_text:
        return {
            "stripped_text": "",
            "removed_count": 0,
            "remaining_length": 0,
            "removed_refs": [],
        }

    if not unverified_refs:
        return {
            "stripped_text": response_text,
            "removed_count": 0,
            "remaining_length": len(response_text),
            "removed_refs": [],
        }

    # Collect bad reference strings
    bad_refs: List[str] = []
    for ref_info in unverified_refs:
        ref_str = ""
        if isinstance(ref_info, dict):
            ref_str = ref_info.get("ref", "")
        elif isinstance(ref_info, str):
            ref_str = ref_info
        if ref_str:
            bad_refs.append(ref_str)

    if not bad_refs:
        return {
            "stripped_text": response_text,
            "removed_count": 0,
            "remaining_length": len(response_text),
            "removed_refs": [],
        }

    lines = response_text.split("\n")
    cleaned: List[str] = []
    removed_count = 0
    removed_refs_found: List[str] = []

    for line in lines:
        matching_refs = [ref for ref in bad_refs if ref in line]
        if matching_refs:
            removed_count += 1
            for ref in matching_refs:
                if ref not in removed_refs_found:
                    removed_refs_found.append(ref)
            logger.debug(f"[Strip] Removed line containing unverified ref: {line[:80]}...")
        else:
            cleaned.append(line)

    stripped_text = "\n".join(cleaned)

    return {
        "stripped_text": stripped_text,
        "removed_count": removed_count,
        "remaining_length": len(stripped_text),
        "removed_refs": removed_refs_found,
    }
