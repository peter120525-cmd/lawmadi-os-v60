"""
DRF tools for Lawmadi ADK -- Korean legal database search (law.go.kr DRF API).

Ported from connectors/drf_client.py as standalone sync functions
suitable for ADK FunctionTool registration.

All functions are synchronous and return dict for ADK consumption.
"""

import logging
import os
import time
from typing import Dict, List, Optional

import requests

from tools.circuit_breaker import drf_circuit_breaker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DRF_SEARCH_URL = "https://www.law.go.kr/DRF/lawSearch.do"
_LAW_SERVICE_URL = "https://www.law.go.kr/DRF/lawService.do"
_TIMEOUT_SEC = 5
_MAX_RETRIES = 3


def _get_api_key() -> str:
    """Read DRF API key from environment."""
    return os.getenv("LAWGO_DRF_OC", "")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _request_with_retry(
    url: str,
    params: dict,
    *,
    retries: int = _MAX_RETRIES,
    timeout: int = _TIMEOUT_SEC,
) -> Optional[dict]:
    """
    HTTP GET with exponential backoff retry + circuit breaker.

    Returns parsed JSON dict on success, raises RuntimeError on exhausted retries.
    Backoff schedule: 0.5s, 1.0s, 2.0s
    """
    if not drf_circuit_breaker.allow_request():
        raise RuntimeError("DRF circuit breaker OPEN — requests blocked")

    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            content_type = r.headers.get("Content-Type", "")
            if "json" not in content_type.lower():
                raise RuntimeError(f"Unexpected Content-Type: {content_type}")
            drf_circuit_breaker.record_success()
            return r.json()
        except Exception as e:
            last_err = e
            drf_circuit_breaker.record_failure()
            if attempt < retries - 1:
                wait = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s
                logger.warning(
                    f"DRF retry {attempt + 1}/{retries}: {e}, waiting {wait}s"
                )
                time.sleep(wait)
    raise RuntimeError(f"All {retries} attempts failed: {last_err}")


def _drf_search(query: str, target: str) -> dict:
    """
    Generic DRF lawSearch.do call.

    Args:
        query: Search keyword.
        target: DRF target value (law, prec, admrul, expc, decc, ordin, etc.).

    Returns:
        Raw JSON dict from DRF API.

    Raises:
        RuntimeError: On API failure after retries.
    """
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("LAWGO_DRF_OC environment variable not set")

    params = {
        "OC": api_key,
        "target": target,
        "type": "JSON",
        "query": query,
    }
    return _request_with_retry(_DRF_SEARCH_URL, params)


def _law_service_query(query: str, target: str) -> dict:
    """
    Generic lawService.do call with query parameter.

    Args:
        query: Search keyword.
        target: lawService target (lstrm, etc.).

    Returns:
        Raw JSON dict from lawService API.
    """
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("LAWGO_DRF_OC environment variable not set")

    params = {
        "OC": api_key,
        "target": target,
        "type": "JSON",
        "query": query,
    }
    return _request_with_retry(_LAW_SERVICE_URL, params)


def _law_service_by_id(target: str, doc_id: str) -> dict:
    """
    lawService.do call with ID parameter (for treaties, constitutional decisions, etc.).

    Args:
        target: lawService target (trty, decc, etc.).
        doc_id: Document ID.

    Returns:
        Raw JSON dict from lawService API.
    """
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("LAWGO_DRF_OC environment variable not set")

    params = {
        "OC": api_key,
        "target": target,
        "type": "JSON",
        "ID": doc_id,
    }
    return _request_with_retry(_LAW_SERVICE_URL, params)


def _safe_list(data) -> list:
    """Ensure data is a list (DRF sometimes returns a single dict instead of a list)."""
    if data is None:
        return []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return []


def _error_result(message: str) -> dict:
    """Build a standardized error response dict."""
    return {"status": "error", "error_message": message}


# ---------------------------------------------------------------------------
# 1. search_law_drf — Search Korean laws by keyword
# ---------------------------------------------------------------------------

def search_law_drf(query: str) -> dict:
    """
    Search Korean laws by keyword using law.go.kr DRF API.

    Args:
        query: Korean law search keyword (e.g. "근로기준법", "임대차").

    Returns:
        dict with keys:
            - status: "success" or "error"
            - results: list of law entries (법령명한글, 법령일련번호, 시행일자, 법령구분명)
            - total_count: number of results
            - error_message: (only on error)
    """
    try:
        raw = _drf_search(query, target="law")

        law_list = _safe_list(
            raw.get("LawSearch", {}).get("law")
        )

        results = []
        for law in law_list:
            results.append({
                "법령명한글": law.get("법령명한글", ""),
                "법령일련번호": law.get("법령일련번호", ""),
                "시행일자": law.get("시행일자", ""),
                "법령구분명": law.get("법령구분명", ""),
            })

        total = int(raw.get("LawSearch", {}).get("totalCnt", len(results)))

        return {
            "status": "success",
            "results": results,
            "total_count": total,
        }
    except Exception as e:
        logger.error(f"search_law_drf failed: {e}")
        return _error_result(str(e))


# ---------------------------------------------------------------------------
# 2. search_precedents_drf — Search Korean court precedents
# ---------------------------------------------------------------------------

def search_precedents_drf(query: str) -> dict:
    """
    Search Korean court precedents (판례) by keyword.

    Args:
        query: Precedent search keyword (e.g. "부당해고", "손해배상").

    Returns:
        dict with keys:
            - status: "success" or "error"
            - results: list of precedent entries (사건번호, 사건명, 선고일자, 법원명, 판결유형)
            - total_count: number of results
            - error_message: (only on error)
    """
    try:
        raw = _drf_search(query, target="prec")

        prec_list = _safe_list(
            raw.get("PrecSearch", {}).get("prec")
        )

        results = []
        for prec in prec_list:
            results.append({
                "사건번호": prec.get("사건번호", ""),
                "사건명": prec.get("사건명", ""),
                "선고일자": prec.get("선고일자", ""),
                "법원명": prec.get("법원명", ""),
                "판결유형": prec.get("판결유형", ""),
            })

        total = int(raw.get("PrecSearch", {}).get("totalCnt", len(results)))

        return {
            "status": "success",
            "results": results,
            "total_count": total,
        }
    except Exception as e:
        logger.error(f"search_precedents_drf failed: {e}")
        return _error_result(str(e))


# ---------------------------------------------------------------------------
# 3. get_law_articles — Get specific law articles by law name
# ---------------------------------------------------------------------------

def get_law_articles(law_name: str) -> dict:
    """
    Get specific law articles (조문) by law name.

    Two-step process:
        Step 1: lawSearch.do to find MST (법령일련번호) by matching law name
        Step 2: lawService.do with MST to fetch article details (조문단위)

    MST matching priority:
        1. Exact match on 법령명한글
        2. Prefix match (법령명한글 starts with law_name) among 법률 type
        3. Contains match (law_name in 법령명한글) among 법률 type

    Args:
        law_name: Korean law name (e.g. "근로기준법", "민법").

    Returns:
        dict with keys:
            - status: "success" or "error"
            - law_name: the queried law name
            - articles: list of article dicts (조문번호, 조문내용, 조문제목)
            - error_message: (only on error)
    """
    try:
        # Step 1: lawSearch.do -> find MST
        raw_search = _drf_search(law_name, target="law")

        law_list = _safe_list(
            raw_search.get("LawSearch", {}).get("law")
        )

        if not law_list:
            return _error_result(f"No laws found for: {law_name}")

        mst: Optional[str] = None

        # Priority 1: exact match
        for law in law_list:
            name = law.get("법령명한글", "")
            if name == law_name:
                mst = law.get("법령일련번호")
                break

        # Priority 2: prefix match among 법률 type
        if not mst:
            for law in law_list:
                name = law.get("법령명한글", "")
                if name.startswith(law_name) and law.get("법령구분명") == "법률":
                    mst = law.get("법령일련번호")
                    break

        # Priority 3: contains match among 법률 type
        if not mst:
            for law in law_list:
                name = law.get("법령명한글", "")
                if law_name in name and law.get("법령구분명") == "법률":
                    mst = law.get("법령일련번호")
                    break

        if not mst:
            return _error_result(f"MST not found for: {law_name}")

        logger.info(f"get_law_articles: {law_name} -> MST={mst}")

        # Step 2: lawService.do with MST to get articles
        api_key = _get_api_key()
        if not api_key:
            return _error_result("LAWGO_DRF_OC environment variable not set")

        params = {
            "OC": api_key,
            "target": "law",
            "MST": mst,
            "type": "JSON",
        }

        # Use longer timeout for large laws (e.g. 민법)
        raw_service = _request_with_retry(
            _LAW_SERVICE_URL,
            params,
            timeout=max(_TIMEOUT_SEC, 10),
        )

        if not raw_service:
            return _error_result(f"lawService returned empty for MST={mst}")

        # Extract articles (조문단위)
        article_units = _safe_list(
            raw_service.get("법령", {}).get("조문", {}).get("조문단위")
        )

        articles: List[dict] = []
        for art in article_units:
            articles.append({
                "조문번호": art.get("조문번호", ""),
                "조문내용": art.get("조문내용", ""),
                "조문제목": art.get("조문제목", ""),
            })

        return {
            "status": "success",
            "law_name": law_name,
            "articles": articles,
        }
    except Exception as e:
        logger.error(f"get_law_articles failed: {e}")
        return _error_result(str(e))


# ---------------------------------------------------------------------------
# 4. search_legal_term_drf — Search legal terminology
# ---------------------------------------------------------------------------

def search_legal_term_drf(query: str) -> dict:
    """
    Search Korean legal terminology (법령용어) via lawService.do.

    Args:
        query: Legal term to search (e.g. "선의취득", "채무불이행").

    Returns:
        dict with keys:
            - status: "success" or "error"
            - results: list of term entries from DRF
            - error_message: (only on error)
    """
    try:
        raw = _law_service_query(query, target="lstrm")

        # The response structure varies; extract the term list
        term_list = _safe_list(
            raw.get("LsTermService", {}).get("lstrm")
            if raw.get("LsTermService")
            else raw.get("lstrm")
        )

        return {
            "status": "success",
            "results": term_list,
        }
    except Exception as e:
        logger.error(f"search_legal_term_drf failed: {e}")
        return _error_result(str(e))


# ---------------------------------------------------------------------------
# 5. search_admin_rules_drf — Search administrative rules (행정규칙)
# ---------------------------------------------------------------------------

def search_admin_rules_drf(query: str) -> dict:
    """
    Search Korean administrative rules (행정규칙) by keyword.

    Args:
        query: Administrative rule search keyword (e.g. "훈령", "예규").

    Returns:
        dict with keys:
            - status: "success" or "error"
            - results: list of administrative rule entries
            - total_count: number of results
            - error_message: (only on error)
    """
    try:
        raw = _drf_search(query, target="admrul")

        rule_list = _safe_list(
            raw.get("AdmRulSearch", {}).get("admrul")
            if raw.get("AdmRulSearch")
            else raw.get("admrul")
        )

        total = int(
            raw.get("AdmRulSearch", {}).get("totalCnt", len(rule_list))
        )

        return {
            "status": "success",
            "results": rule_list,
            "total_count": total,
        }
    except Exception as e:
        logger.error(f"search_admin_rules_drf failed: {e}")
        return _error_result(str(e))


# ---------------------------------------------------------------------------
# 6. search_constitutional_drf — Search constitutional court decisions
# ---------------------------------------------------------------------------

def search_constitutional_drf(query: str) -> dict:
    """
    Search Korean constitutional court decisions (헌법재판소 결정례) by keyword.

    Args:
        query: Constitutional decision search keyword (e.g. "위헌", "헌법소원").

    Returns:
        dict with keys:
            - status: "success" or "error"
            - results: list of constitutional decision entries
            - total_count: number of results
            - error_message: (only on error)
    """
    try:
        raw = _drf_search(query, target="decc")

        decc_list = _safe_list(
            raw.get("DeccSearch", {}).get("decc")
            if raw.get("DeccSearch")
            else raw.get("decc")
        )

        total = int(
            raw.get("DeccSearch", {}).get("totalCnt", len(decc_list))
        )

        return {
            "status": "success",
            "results": decc_list,
            "total_count": total,
        }
    except Exception as e:
        logger.error(f"search_constitutional_drf failed: {e}")
        return _error_result(str(e))


# ---------------------------------------------------------------------------
# 7. search_ordinance_drf — Search local ordinances (자치법규)
# ---------------------------------------------------------------------------

def search_ordinance_drf(query: str) -> dict:
    """
    Search Korean local ordinances (자치법규) by keyword.

    Args:
        query: Ordinance search keyword (e.g. "서울특별시 조례", "건축").

    Returns:
        dict with keys:
            - status: "success" or "error"
            - results: list of ordinance entries
            - total_count: number of results
            - error_message: (only on error)
    """
    try:
        raw = _drf_search(query, target="ordin")

        ordin_list = _safe_list(
            raw.get("OrdinSearch", {}).get("ordin")
            if raw.get("OrdinSearch")
            else raw.get("ordin")
        )

        total = int(
            raw.get("OrdinSearch", {}).get("totalCnt", len(ordin_list))
        )

        return {
            "status": "success",
            "results": ordin_list,
            "total_count": total,
        }
    except Exception as e:
        logger.error(f"search_ordinance_drf failed: {e}")
        return _error_result(str(e))


# ---------------------------------------------------------------------------
# 8. search_expc_drf — Search legal interpretations (법령해석례)
# ---------------------------------------------------------------------------

def search_expc_drf(query: str) -> dict:
    """
    Search Korean legal interpretations (법령해석례) by keyword.

    Args:
        query: Legal interpretation search keyword (e.g. "유권해석", "질의회신").

    Returns:
        dict with keys:
            - status: "success" or "error"
            - results: list of legal interpretation entries
            - total_count: number of results
            - error_message: (only on error)
    """
    try:
        raw = _drf_search(query, target="expc")

        expc_list = _safe_list(
            raw.get("ExpcSearch", {}).get("expc")
            if raw.get("ExpcSearch")
            else raw.get("expc")
        )

        total = int(
            raw.get("ExpcSearch", {}).get("totalCnt", len(expc_list))
        )

        return {
            "status": "success",
            "results": expc_list,
            "total_count": total,
        }
    except Exception as e:
        logger.error(f"search_expc_drf failed: {e}")
        return _error_result(str(e))


# ---------------------------------------------------------------------------
# 9. search_treaty_drf — Search treaties by ID
# ---------------------------------------------------------------------------

def search_treaty_drf(doc_id: str) -> dict:
    """
    Retrieve a Korean treaty (조약) by its document ID via lawService.do.

    Note: This is an ID-based lookup, not a keyword search.

    Args:
        doc_id: Treaty document ID (e.g. "983", "2120", "1000").

    Returns:
        dict with keys:
            - status: "success" or "error"
            - result: treaty detail dict from DRF
            - error_message: (only on error)
    """
    try:
        raw = _law_service_by_id(target="trty", doc_id=doc_id)

        # Extract the treaty data from the response wrapper
        result = raw.get("BothTrtyService", raw)

        return {
            "status": "success",
            "result": result,
        }
    except Exception as e:
        logger.error(f"search_treaty_drf failed: {e}")
        return _error_result(str(e))
