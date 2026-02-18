from core.drf_integrity import validate_drf_xml
import os
import requests
import xml.etree.ElementTree as ET
import logging
import hashlib
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Import cache functions (lazy import to avoid circular dependency)
_cache_get = None
_cache_set = None

def _init_cache():
    global _cache_get, _cache_set
    if _cache_get is None:
        try:
            from connectors.db_client_v2 import cache_get, cache_set
            _cache_get = cache_get
            _cache_set = cache_set
            logger.info("✅ DRF 캐싱 활성화")
        except Exception as e:
            logger.warning(f"⚠️ DRF 캐싱 비활성화: {e}")
            _cache_get = lambda k: None
            _cache_set = lambda k, v, t: None

_DEFAULT_DRF_URL = "https://www.law.go.kr/DRF/lawSearch.do"
_LAW_SERVICE_URL = "http://www.law.go.kr/DRF/lawService.do"


class DRFConnector:

    def __init__(
        self,
        api_key: str = "",
        timeout_ms: int = 5000,
        config: Optional[Dict] = None,
    ) -> None:
        if config:
            # Legacy: config dict 방식 (SearchService 등에서 사용)
            dual = config.get("dual_ssot", {})
            self.drf_conf = dual.get("drf", {})
            self.data_conf = dual.get("data_go_kr", {})
            self.drf_key = os.getenv(self.drf_conf.get("api_key_env", "LAWGO_DRF_OC"), "")
            self.data_key = os.getenv(self.data_conf.get("api_key_env", "DATA_GO_KR_API_KEY"), "")
            self.drf_url = self.drf_conf.get("base_url", _DEFAULT_DRF_URL)
            self.data_url = self.data_conf.get("base_url", "")
        else:
            # Direct: keyword args 방식 (main.py에서 사용)
            self.drf_key = api_key or os.getenv("LAWGO_DRF_OC", "")
            self.data_key = os.getenv("DATA_GO_KR_API_KEY", "")
            self.drf_url = _DEFAULT_DRF_URL
            self.data_url = ""

        self.timeout_sec = max(1, timeout_ms // 1000)

    # -------------------------------------------------
    # DRF 호출
    # -------------------------------------------------
    def _call_drf(self, query, target="law", _retries=3):
        """
        DRF API 호출 (target 파라미터 지원, 지수 백오프 재시도)

        Args:
            query: 검색어
            target: DRF target (law, prec, admrul, expc, adrule, edulaw, etc.)
            _retries: 재시도 횟수 (기본 3)
        """
        if not self.drf_key or not self.drf_url:
            raise RuntimeError("DRF not available")

        params = {
            "OC": self.drf_key,
            "target": target,
            "type": "JSON",
            "query": query
        }

        last_err = None
        for attempt in range(_retries):
            try:
                r = requests.get(self.drf_url, params=params, timeout=self.timeout_sec)

                if r.status_code != 200:
                    raise RuntimeError(f"DRF HTTP {r.status_code}")

                content_type = r.headers.get("Content-Type", "")
                if "json" not in content_type.lower():
                    raise RuntimeError(f"DRF unexpected Content-Type: {content_type}")

                return r.json()
            except Exception as e:
                last_err = e
                if attempt < _retries - 1:
                    import time
                    wait = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s
                    logger.warning(f"⚠️ DRF 재시도 {attempt+1}/{_retries} ({target}): {e}, {wait}s 대기")
                    time.sleep(wait)

        raise RuntimeError(f"DRF {_retries}회 시도 실패: {last_err}")

    # -------------------------------------------------
    # data.go.kr 호출
    # -------------------------------------------------
    def _call_data_go(self, query):

        if not self.data_key or not self.data_url:
            raise RuntimeError("data.go.kr not available")

        params = {
            "serviceKey": self.data_key,
            "query": query,
            "type": "XML"
        }

        r = requests.get(self.data_url, params=params, timeout=self.timeout_sec)

        if r.status_code != 200:
            raise RuntimeError(f"data.go.kr HTTP {r.status_code}")

        content_type = r.headers.get("Content-Type", "")
        if "xml" not in content_type and "json" not in content_type:
            raise RuntimeError(f"data.go.kr unexpected Content-Type: {content_type}")

        validate_drf_xml(r.text)

        return ET.fromstring(r.text)

    # -------------------------------------------------
    # 🔥 교차 재시도 Dual SSOT (+ 캐싱) - Target별 독립 검색
    # -------------------------------------------------
    def search_by_target(self, query: str, target: str = "law") -> Optional[Any]:
        """
        특정 target으로 DRF 검색 (캐싱 포함)

        Args:
            query: 검색어
            target: DRF target 값

        Returns:
            JSON dict 또는 None
        """
        _init_cache()

        # Target별 독립 캐시 키
        cache_key = f"drf:v2:{target}:{hashlib.md5(query.encode('utf-8')).hexdigest()}"

        try:
            cached_data = _cache_get(cache_key)
            if cached_data and cached_data.get("data"):
                logger.info(f"🎯 [Cache HIT] target={target}, query={query[:30]}")
                return cached_data["data"]
        except Exception as e:
            logger.warning(f"⚠️ [Cache] 조회 실패: {e}")

        logger.info(f"🔍 [Cache MISS] target={target}, query={query[:30]}")

        # Dual SSOT 재시도 로직
        attempts = [
            ("DRF-1", lambda q: self._call_drf(q, target=target)),
            ("DATA-1", self._call_data_go),  # fallback (target 미지원일 수 있음)
            ("DRF-2", lambda q: self._call_drf(q, target=target)),
        ]

        for label, fn in attempts:
            try:
                result = fn(query)
                if result is not None:
                    logger.info(f"[DualSSOT] SUCCESS via {label} (target={target})")
                    try:
                        _cache_set(
                            cache_key,
                            {"data": result, "query": query[:200], "target": target},
                            ttl_seconds=3600
                        )
                        logger.info(f"💾 [Cache SET] {cache_key[:24]}... (TTL: 1h)")
                    except Exception as e:
                        logger.warning(f"⚠️ [Cache] 저장 실패: {e}")
                    return result
            except Exception as e:
                logger.warning(f"[DualSSOT] {label} failed: {str(e)}")

        logger.error(f"[DualSSOT] All attempts failed for target={target}")
        return None

    def law_search(self, query: str) -> Optional[Any]:
        """기존 메서드 유지 (target=law 기본값, 하위 호환성)"""
        return self.search_by_target(query, target="law")

    def search_precedents(self, query: str) -> Optional[Any]:
        """판례 검색 (target=prec)"""
        return self.search_by_target(query, target="prec")

    # -------------------------------------------------
    # lawService.do 호출 (법령용어, 조약 등)
    # -------------------------------------------------
    def _call_law_service(self, query, target):
        """
        lawService.do API 호출

        Args:
            query: 검색어
            target: lawService target (lstrm, trty, etc.)
        """
        if not self.drf_key:
            raise RuntimeError("DRF not available")

        params = {
            "OC": self.drf_key,
            "target": target,
            "type": "JSON",
            "query": query
        }

        r = requests.get(_LAW_SERVICE_URL, params=params, timeout=self.timeout_sec)

        if r.status_code != 200:
            raise RuntimeError(f"lawService HTTP {r.status_code}")

        content_type = r.headers.get("Content-Type", "")
        if "json" not in content_type.lower():
            raise RuntimeError(f"lawService unexpected Content-Type: {content_type}")

        # JSON 파싱
        try:
            return r.json()
        except Exception as e:
            raise RuntimeError(f"lawService JSON parse error: {e}")

    def _call_law_service_by_id(self, target: str, doc_id: str) -> Any:
        """
        lawService.do ID 기반 조회

        Args:
            target: lawService target (decc, trty, etc.)
            doc_id: 문서 ID

        Returns:
            JSON dict

        Raises:
            RuntimeError: API 호출 실패 시
        """
        if not self.drf_key:
            raise RuntimeError("DRF not available")

        params = {
            "OC": self.drf_key,
            "target": target,
            "type": "JSON",
            "ID": doc_id
        }

        r = requests.get(_LAW_SERVICE_URL, params=params, timeout=self.timeout_sec)

        if r.status_code != 200:
            raise RuntimeError(f"lawService HTTP {r.status_code}")

        content_type = r.headers.get("Content-Type", "")
        if "json" not in content_type.lower():
            raise RuntimeError(f"lawService unexpected Content-Type: {content_type}")

        # JSON 파싱
        try:
            return r.json()
        except Exception as e:
            raise RuntimeError(f"lawService JSON parse error: {e}")

    def search_legal_term(self, query: str) -> Optional[Any]:
        """
        법령용어 검색 (SSOT #10)

        Args:
            query: 검색어

        Returns:
            JSON dict 또는 None
        """
        _init_cache()

        # 법령용어 전용 캐시 키
        cache_key = f"drf:v2:lstrm:{hashlib.md5(query.encode('utf-8')).hexdigest()}"

        try:
            cached_data = _cache_get(cache_key)
            if cached_data and cached_data.get("data"):
                logger.info(f"🎯 [Cache HIT] target=lstrm, query={query[:30]}")
                return cached_data["data"]
        except Exception as e:
            logger.warning(f"⚠️ [Cache] 조회 실패: {e}")

        logger.info(f"🔍 [Cache MISS] target=lstrm, query={query[:30]}")

        # lawService.do 호출 (재시도 없음, 단일 엔드포인트)
        try:
            result = self._call_law_service(query, target="lstrm")
            if result is not None:
                logger.info(f"[lawService] SUCCESS (target=lstrm)")
                try:
                    _cache_set(
                        cache_key,
                        {"data": result, "query": query[:200], "target": "lstrm"},
                        ttl_seconds=3600
                    )
                    logger.info(f"💾 [Cache SET] {cache_key[:24]}... (TTL: 1h)")
                except Exception as e:
                    logger.warning(f"⚠️ [Cache] 저장 실패: {e}")
                return result
        except Exception as e:
            logger.warning(f"[lawService] lstrm failed: {str(e)}")

        logger.error(f"[lawService] Failed for target=lstrm")
        return None

    def search_admin_appeals(self, doc_id: str) -> Optional[Any]:
        """
        행정심판례 검색 (SSOT #8) - ID 기반 조회

        ⚠️ 주의: 키워드 검색 미지원, 정확한 심판례 ID 필요

        Args:
            doc_id: 행정심판례 ID (예: "223311", "223310")

        Returns:
            JSON dict 또는 None

        Example:
            >>> drf.search_admin_appeals("223311")
            {"PrecService": {"사건명": "...", ...}}
        """
        _init_cache()

        # ID 기반 캐시 키
        cache_key = f"drf:v2:decc:{hashlib.md5(doc_id.encode('utf-8')).hexdigest()}"

        try:
            cached_data = _cache_get(cache_key)
            if cached_data and cached_data.get("data"):
                logger.info(f"🎯 [Cache HIT] target=decc, ID={doc_id}")
                return cached_data["data"]
        except Exception as e:
            logger.warning(f"⚠️ [Cache] 조회 실패: {e}")

        logger.info(f"🔍 [Cache MISS] target=decc, ID={doc_id}")

        # lawService.do ID 기반 호출
        try:
            result = self._call_law_service_by_id(target="decc", doc_id=doc_id)
            if result is not None:
                logger.info(f"[lawService] SUCCESS (target=decc, ID={doc_id})")
                try:
                    _cache_set(
                        cache_key,
                        {"data": result, "doc_id": doc_id, "target": "decc"},
                        ttl_seconds=3600
                    )
                    logger.info(f"💾 [Cache SET] {cache_key[:24]}... (TTL: 1h)")
                except Exception as e:
                    logger.warning(f"⚠️ [Cache] 저장 실패: {e}")
                return result
        except Exception as e:
            logger.warning(f"[lawService] decc failed for ID={doc_id}: {str(e)}")

        logger.error(f"[lawService] Failed for target=decc, ID={doc_id}")
        return None

    def search_treaty(self, doc_id: str) -> Optional[Any]:
        """
        조약 검색 (SSOT #9) - ID 기반 조회

        ⚠️ 주의: 키워드 검색 미지원, 정확한 조약 ID 필요

        Args:
            doc_id: 조약 ID (예: "983", "2120", "1000")

        Returns:
            JSON dict 또는 None

        Example:
            >>> drf.search_treaty("983")
            {"BothTrtyService": {"조약한글명": "...", ...}}
        """
        _init_cache()

        # ID 기반 캐시 키
        cache_key = f"drf:v2:trty:{hashlib.md5(doc_id.encode('utf-8')).hexdigest()}"

        try:
            cached_data = _cache_get(cache_key)
            if cached_data and cached_data.get("data"):
                logger.info(f"🎯 [Cache HIT] target=trty, ID={doc_id}")
                return cached_data["data"]
        except Exception as e:
            logger.warning(f"⚠️ [Cache] 조회 실패: {e}")

        logger.info(f"🔍 [Cache MISS] target=trty, ID={doc_id}")

        # lawService.do ID 기반 호출
        try:
            result = self._call_law_service_by_id(target="trty", doc_id=doc_id)
            if result is not None:
                logger.info(f"[lawService] SUCCESS (target=trty, ID={doc_id})")
                try:
                    _cache_set(
                        cache_key,
                        {"data": result, "doc_id": doc_id, "target": "trty"},
                        ttl_seconds=3600
                    )
                    logger.info(f"💾 [Cache SET] {cache_key[:24]}... (TTL: 1h)")
                except Exception as e:
                    logger.warning(f"⚠️ [Cache] 저장 실패: {e}")
                return result
        except Exception as e:
            logger.warning(f"[lawService] trty failed for ID={doc_id}: {str(e)}")

        logger.error(f"[lawService] Failed for target=trty, ID={doc_id}")
        return None
