from core.drf_integrity import validate_drf_xml
import os
import time as _time
import random as _random
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import xml.etree.ElementTree as ET
import logging
import hashlib
from typing import Optional, Dict, Any

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

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
_LAW_SERVICE_URL = "https://www.law.go.kr/DRF/lawService.do"

# Target별 캐시 TTL (초) — 법률 데이터는 자주 변경되지 않으므로 긴 TTL 적용
_CACHE_TTL = {
    "law": 21600,    # 6시간
    "prec": 14400,   # 4시간
    "lstrm": 7200,   # 2시간
    "decc": 7200,    # 2시간
    "trty": 21600,   # 6시간
    "default": 3600, # 1시간
}


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

        # --- 커넥션 풀: requests.Session ---
        self._session = requests.Session()
        self._session.headers.update({
            "Connection": "keep-alive",
            "User-Agent": "Lawmadi-OS/v60 (DRF Client)",
        })
        _adapter = HTTPAdapter(
            pool_connections=5,
            pool_maxsize=10,
            max_retries=Retry(total=0),   # 재시도는 앱 레벨에서 관리
        )
        self._session.mount("https://", _adapter)
        self._session.mount("http://", _adapter)

        # --- 커넥션 풀: httpx.AsyncClient ---
        self._async_client: Optional[httpx.AsyncClient] = None

        logger.info("✅ DRF 커넥션 풀 초기화 (pool_connections=5, pool_maxsize=10)")

    # -------------------------------------------------
    # 세션 / Async 클라이언트 관리
    # -------------------------------------------------
    async def _get_async_client(self) -> "httpx.AsyncClient":
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(
                timeout=float(self.timeout_sec),
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                ),
                headers={
                    "Connection": "keep-alive",
                    "User-Agent": "Lawmadi-OS/v60 (DRF AsyncClient)",
                },
            )
        return self._async_client

    async def close_async(self):
        if self._async_client and not self._async_client.is_closed:
            await self._async_client.aclose()
            self._async_client = None

    def close(self):
        self._session.close()
        logger.info("✅ DRF 세션 종료")

    # -------------------------------------------------
    # DRF 호출
    # -------------------------------------------------
    def _call_drf(self, query, target="law", _retries=2):
        """
        DRF API 호출 (target 파라미터 지원, 지수 백오프 재시도)

        Args:
            query: 검색어
            target: DRF target (law, prec, admrul, expc, adrule, edulaw, etc.)
            _retries: 재시도 횟수 (기본 2)
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
                r = self._session.get(self.drf_url, params=params, timeout=self.timeout_sec)

                if r.status_code != 200:
                    raise RuntimeError(f"DRF HTTP {r.status_code}")

                content_type = r.headers.get("Content-Type", "")
                if "json" not in content_type.lower():
                    raise RuntimeError(f"DRF unexpected Content-Type: {content_type}")

                return r.json()
            except Exception as e:
                last_err = e
                if attempt < _retries - 1:
                    wait = (2 ** attempt) * 0.5 + _random.uniform(0, 0.3)
                    logger.warning(f"⚠️ DRF 재시도 {attempt+1}/{_retries} ({target}): {e}, {wait:.1f}s 대기")
                    _time.sleep(wait)

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

        r = self._session.get(self.data_url, params=params, timeout=self.timeout_sec)

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
                    ttl = _CACHE_TTL.get(target, _CACHE_TTL["default"])
                    try:
                        _cache_set(
                            cache_key,
                            {"data": result, "query": query[:200], "target": target},
                            ttl_seconds=ttl
                        )
                        logger.info(f"💾 [Cache SET] {cache_key[:24]}... (TTL: {ttl//3600}h)")
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

        r = self._session.get(_LAW_SERVICE_URL, params=params, timeout=self.timeout_sec)

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

        r = self._session.get(_LAW_SERVICE_URL, params=params, timeout=self.timeout_sec)

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

    def get_law_articles(self, law_name: str) -> Optional[Any]:
        """
        법령명으로 lawSearch → MST 추출 → lawService로 조문 상세 조회

        Returns:
            lawService.do JSON 응답 (조문단위 포함) 또는 None
        """
        _init_cache()

        cache_key = f"drf:v2:lawsvc:{hashlib.md5(law_name.encode('utf-8')).hexdigest()}"
        try:
            cached = _cache_get(cache_key)
            if cached and cached.get("data"):
                # 시간 기반 만료: _cached_at 타임스탬프 확인 (6시간 TTL)
                cached_at = cached.get("_cached_at", 0)
                if cached_at and (_time.time() - cached_at) > 21600:  # 6h
                    logger.warning(f"⚠️ [Cache EXPIRED] lawService {law_name}: 캐시 6시간 초과 → 재조회")
                else:
                    # 캐시 검증: 조문 수가 극히 적으면 잘린 데이터일 수 있음 → 재조회
                    cached_data = cached["data"]
                    arts = cached_data.get("법령", {}).get("조문", {}).get("조문단위", [])
                    if isinstance(arts, list) and len(arts) < 3:
                        logger.warning(f"⚠️ [Cache STALE] lawService {law_name}: 조문 {len(arts)}건 → 재조회")
                    else:
                        logger.info(f"🎯 [Cache HIT] lawService, query={law_name[:30]} ({len(arts) if isinstance(arts, list) else '?'}건)")
                        return cached_data
        except Exception:
            pass

        # Step 1: lawSearch.do로 법령일련번호(MST) 조회
        search_result = self.law_search(law_name)
        if not search_result:
            return None

        mst = None
        try:
            law_list = search_result.get("LawSearch", {}).get("law", [])
            if isinstance(law_list, dict):
                law_list = [law_list]
            # 1순위: 법령명 정확 일치
            for law in law_list:
                name = law.get("법령명한글", "")
                if name == law_name:
                    mst = law.get("법령일련번호")
                    break
            # 2순위: 법령명이 검색어로 시작 (예: "주택임대차보호법 시행령" 방지)
            if not mst:
                for law in law_list:
                    name = law.get("법령명한글", "")
                    if name.startswith(law_name) and law.get("법령구분명") == "법률":
                        mst = law.get("법령일련번호")
                        break
            # 3순위: 법률 구분 중 가장 유사한 것
            if not mst:
                for law in law_list:
                    name = law.get("법령명한글", "")
                    if law_name in name and law.get("법령구분명") == "법률":
                        mst = law.get("법령일련번호")
                        break
        except Exception as e:
            logger.warning(f"⚠️ MST 추출 실패: {e}")
            return None

        if not mst:
            logger.warning(f"⚠️ [lawService] MST 미발견: {law_name}")
            return None

        logger.info(f"🔍 [lawService] {law_name} → MST={mst}")
        # Step 2: lawService.do로 조문 상세 조회 (3회 재시도 + 지수 백오프)
        last_err = None
        for attempt in range(3):
            try:
                params = {
                    "OC": self.drf_key,
                    "target": "law",
                    "MST": mst,
                    "type": "JSON",
                }
                r = self._session.get(_LAW_SERVICE_URL, params=params, timeout=max(self.timeout_sec, 15))
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}")
                data = r.json()
                try:
                    _cache_set(cache_key, {"data": data, "law_name": law_name, "mst": mst, "_cached_at": _time.time()}, ttl_seconds=21600)
                except Exception:
                    pass
                return data
            except Exception as e:
                last_err = e
                if attempt < 2:
                    wait = (2 ** attempt) * 0.5 + _random.uniform(0, 0.3)
                    logger.warning(f"⚠️ lawService 재시도 {attempt+1}/3: {law_name} MST={mst}: {e}")
                    _time.sleep(wait)
        logger.warning(f"⚠️ lawService 3회 실패: {law_name}: {last_err}")
        return None

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
                ttl = _CACHE_TTL.get("lstrm", _CACHE_TTL["default"])
                try:
                    _cache_set(
                        cache_key,
                        {"data": result, "query": query[:200], "target": "lstrm"},
                        ttl_seconds=ttl
                    )
                    logger.info(f"💾 [Cache SET] {cache_key[:24]}... (TTL: {ttl//3600}h)")
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
                ttl = _CACHE_TTL.get("decc", _CACHE_TTL["default"])
                try:
                    _cache_set(
                        cache_key,
                        {"data": result, "doc_id": doc_id, "target": "decc"},
                        ttl_seconds=ttl
                    )
                    logger.info(f"💾 [Cache SET] {cache_key[:24]}... (TTL: {ttl//3600}h)")
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
                ttl = _CACHE_TTL.get("trty", _CACHE_TTL["default"])
                try:
                    _cache_set(
                        cache_key,
                        {"data": result, "doc_id": doc_id, "target": "trty"},
                        ttl_seconds=ttl
                    )
                    logger.info(f"💾 [Cache SET] {cache_key[:24]}... (TTL: {ttl//3600}h)")
                except Exception as e:
                    logger.warning(f"⚠️ [Cache] 저장 실패: {e}")
                return result
        except Exception as e:
            logger.warning(f"[lawService] trty failed for ID={doc_id}: {str(e)}")

        logger.error(f"[lawService] Failed for target=trty, ID={doc_id}")
        return None

    # -------------------------------------------------
    # Async variants (httpx.AsyncClient)
    # 기존 동기 메서드 유지 + _async 비동기 메서드 병행
    # -------------------------------------------------

    async def _call_drf_async(self, query, target="law", _retries=2):
        """DRF API 비동기 호출 (httpx.AsyncClient, 지수 백오프 재시도)"""
        if not _HTTPX_AVAILABLE:
            raise RuntimeError("httpx not available for async DRF call")
        if not self.drf_key or not self.drf_url:
            raise RuntimeError("DRF not available")

        params = {
            "OC": self.drf_key,
            "target": target,
            "type": "JSON",
            "query": query,
        }

        last_err = None
        client = await self._get_async_client()
        for attempt in range(_retries):
            try:
                r = await client.get(self.drf_url, params=params)

                if r.status_code != 200:
                    raise RuntimeError(f"DRF HTTP {r.status_code}")

                content_type = r.headers.get("Content-Type", "")
                if "json" not in content_type.lower():
                    raise RuntimeError(f"DRF unexpected Content-Type: {content_type}")

                return r.json()
            except Exception as e:
                last_err = e
                if attempt < _retries - 1:
                    import asyncio
                    wait = (2 ** attempt) * 0.5 + _random.uniform(0, 0.3)
                    logger.warning(f"⚠️ DRF async 재시도 {attempt+1}/{_retries} ({target}): {e}, {wait:.1f}s 대기")
                    await asyncio.sleep(wait)

        raise RuntimeError(f"DRF async {_retries}회 시도 실패: {last_err}")

    async def search_by_target_async(self, query: str, target: str = "law") -> Optional[Any]:
        """비동기 target 검색 (캐싱 포함)"""
        import asyncio as _aio
        await _aio.to_thread(_init_cache)

        cache_key = f"drf:v2:{target}:{hashlib.md5(query.encode('utf-8')).hexdigest()}"
        try:
            cached_data = await _aio.to_thread(_cache_get, cache_key)
            if cached_data and cached_data.get("data"):
                logger.info(f"🎯 [Cache HIT async] target={target}, query={query[:30]}")
                return cached_data["data"]
        except Exception:
            pass

        logger.info(f"🔍 [Cache MISS async] target={target}, query={query[:30]}")
        try:
            result = await self._call_drf_async(query, target=target)
            if result is not None:
                logger.info(f"[DualSSOT async] SUCCESS (target={target})")
                ttl = _CACHE_TTL.get(target, _CACHE_TTL["default"])
                try:
                    await _aio.to_thread(_cache_set, cache_key, {"data": result, "query": query[:200], "target": target}, ttl)
                except Exception:
                    pass
                return result
        except Exception as e:
            logger.warning(f"[DualSSOT async] failed: {e}")

        # Fallback: sync 호출을 thread에서 실행 (이벤트 루프 블로킹 방지)
        return await _aio.to_thread(self.search_by_target, query, target)

    async def law_search_async(self, query: str) -> Optional[Any]:
        """비동기 법률 검색"""
        return await self.search_by_target_async(query, target="law")

    async def search_precedents_async(self, query: str) -> Optional[Any]:
        """비동기 판례 검색"""
        return await self.search_by_target_async(query, target="prec")

    async def get_law_articles_async(self, law_name: str) -> Optional[Any]:
        """비동기 법령 조문 상세 조회 (lawSearch → MST → lawService)"""
        import asyncio as _aio
        if not _HTTPX_AVAILABLE:
            return await _aio.to_thread(self.get_law_articles, law_name)

        await _aio.to_thread(_init_cache)

        cache_key = f"drf:v2:lawsvc:{hashlib.md5(law_name.encode('utf-8')).hexdigest()}"
        try:
            cached = await _aio.to_thread(_cache_get, cache_key)
            if cached and cached.get("data"):
                cached_at = cached.get("_cached_at", 0)
                if cached_at and (_time.time() - cached_at) > 21600:
                    logger.warning(f"⚠️ [Cache EXPIRED async] lawService {law_name}: 캐시 6시간 초과 → 재조회")
                else:
                    cached_data = cached["data"]
                    arts = cached_data.get("법령", {}).get("조문", {}).get("조문단위", [])
                    if isinstance(arts, list) and len(arts) < 3:
                        logger.warning(f"⚠️ [Cache STALE async] lawService {law_name}: 조문 {len(arts)}건 → 재조회")
                    else:
                        return cached_data
        except Exception:
            pass

        # Step 1: lawSearch.do로 MST 조회 (async)
        search_result = await self.law_search_async(law_name)
        if not search_result:
            return None

        mst = None
        try:
            law_list = search_result.get("LawSearch", {}).get("law", [])
            if isinstance(law_list, dict):
                law_list = [law_list]
            for law in law_list:
                name = law.get("법령명한글", "")
                if name == law_name:
                    mst = law.get("법령일련번호")
                    break
            if not mst:
                for law in law_list:
                    name = law.get("법령명한글", "")
                    if name.startswith(law_name) and law.get("법령구분명") == "법률":
                        mst = law.get("법령일련번호")
                        break
            if not mst:
                for law in law_list:
                    name = law.get("법령명한글", "")
                    if law_name in name and law.get("법령구분명") == "법률":
                        mst = law.get("법령일련번호")
                        break
        except Exception as e:
            logger.warning(f"⚠️ MST 추출 실패 (async): {e}")
            return None

        if not mst:
            return None

        # Step 2: lawService.do 비동기 호출 (3회 재시도 + 지수 백오프)
        last_err = None
        client = await self._get_async_client()
        for attempt in range(3):
            try:
                params = {
                    "OC": self.drf_key,
                    "target": "law",
                    "MST": mst,
                    "type": "JSON",
                }
                r = await client.get(_LAW_SERVICE_URL, params=params, timeout=max(float(self.timeout_sec), 15.0))
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}")
                data = r.json()
                try:
                    await _aio.to_thread(_cache_set, cache_key, {"data": data, "law_name": law_name, "mst": mst, "_cached_at": _time.time()}, 21600)
                except Exception:
                    pass
                return data
            except Exception as e:
                last_err = e
                if attempt < 2:
                    wait = (2 ** attempt) * 0.5 + _random.uniform(0, 0.3)
                    logger.warning(f"⚠️ lawService async 재시도 {attempt+1}/3: {law_name} MST={mst}: {e}")
                    await _aio.sleep(wait)
        logger.warning(f"⚠️ lawService async 3회 실패: {law_name}: {last_err}")
        return None

    # -------------------------------------------------
    # elaw (영문 법령) 조문 조회
    # -------------------------------------------------
    def get_elaw_articles(self, law_name_en: str) -> Optional[Any]:
        """
        영문 법령명으로 elaw 검색 → MST 추출 → lawService로 조문 상세 조회

        Args:
            law_name_en: 영문 법령명 (예: "CIVIL ACT", "CRIMINAL ACT")

        Returns:
            lawService.do elaw JSON 응답 (Jo 배열 포함) 또는 None
        """
        _init_cache()

        cache_key = f"drf:v2:elawsvc:{hashlib.md5(law_name_en.upper().encode('utf-8')).hexdigest()}"
        try:
            cached = _cache_get(cache_key)
            if cached and cached.get("data"):
                cached_at = cached.get("_cached_at", 0)
                if not cached_at or (_time.time() - cached_at) <= 21600:
                    logger.info(f"🎯 [Cache HIT] elawService, query={law_name_en[:30]}")
                    return cached["data"]
        except Exception:
            pass

        # Step 1: lawSearch.do?target=elaw 로 영문 법령 검색 → MST 추출
        search_result = self.search_by_target(law_name_en, target="elaw")
        if not search_result:
            return None

        mst = None
        try:
            law_list = search_result.get("LawSearch", {}).get("law", [])
            if isinstance(law_list, dict):
                law_list = [law_list]
            name_upper = law_name_en.upper()
            # 1순위: 법령명영문 정확 일치 (대소문자 무시)
            for law in law_list:
                en_name = (law.get("법령명영문") or "").upper()
                if en_name == name_upper:
                    mst = law.get("법령일련번호") or law.get("MST")
                    break
            # 2순위: 부분 포함
            if not mst:
                for law in law_list:
                    en_name = (law.get("법령명영문") or "").upper()
                    if name_upper in en_name or en_name in name_upper:
                        mst = law.get("법령일련번호") or law.get("MST")
                        break
        except Exception as e:
            logger.warning(f"⚠️ elaw MST 추출 실패: {e}")
            return None

        if not mst:
            logger.warning(f"⚠️ [elawService] MST 미발견: {law_name_en}")
            return None

        logger.info(f"🔍 [elawService] {law_name_en} → MST={mst}")

        # Step 2: lawService.do?target=elaw&MST={mst} 조문 조회 (2회 재시도)
        last_err = None
        for attempt in range(2):
            try:
                params = {
                    "OC": self.drf_key,
                    "target": "elaw",
                    "MST": mst,
                    "type": "JSON",
                }
                r = self._session.get(_LAW_SERVICE_URL, params=params, timeout=max(self.timeout_sec, 15))
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}")
                data = r.json()
                try:
                    _cache_set(cache_key, {"data": data, "law_name_en": law_name_en, "mst": mst, "_cached_at": _time.time()}, ttl_seconds=21600)
                except Exception:
                    pass
                return data
            except Exception as e:
                last_err = e
                if attempt < 1:
                    wait = 0.5 + _random.uniform(0, 0.3)
                    logger.warning(f"⚠️ elawService 재시도 {attempt+1}/2: {law_name_en} MST={mst}: {e}")
                    _time.sleep(wait)
        logger.warning(f"⚠️ elawService 2회 실패: {law_name_en}: {last_err}")
        return None

    async def get_elaw_articles_async(self, law_name_en: str) -> Optional[Any]:
        """비동기 영문 법령 조문 상세 조회 (elaw target)"""
        import asyncio as _aio
        if not _HTTPX_AVAILABLE:
            return await _aio.to_thread(self.get_elaw_articles, law_name_en)

        await _aio.to_thread(_init_cache)

        cache_key = f"drf:v2:elawsvc:{hashlib.md5(law_name_en.upper().encode('utf-8')).hexdigest()}"
        try:
            cached = await _aio.to_thread(_cache_get, cache_key)
            if cached and cached.get("data"):
                cached_at = cached.get("_cached_at", 0)
                if not cached_at or (_time.time() - cached_at) <= 21600:
                    return cached["data"]
        except Exception:
            pass

        # Step 1: elaw 검색으로 MST 조회 (async)
        search_result = await self.search_by_target_async(law_name_en, target="elaw")
        if not search_result:
            return None

        mst = None
        try:
            law_list = search_result.get("LawSearch", {}).get("law", [])
            if isinstance(law_list, dict):
                law_list = [law_list]
            name_upper = law_name_en.upper()
            for law in law_list:
                en_name = (law.get("법령명영문") or "").upper()
                if en_name == name_upper:
                    mst = law.get("법령일련번호") or law.get("MST")
                    break
            if not mst:
                for law in law_list:
                    en_name = (law.get("법령명영문") or "").upper()
                    if name_upper in en_name or en_name in name_upper:
                        mst = law.get("법령일련번호") or law.get("MST")
                        break
        except Exception as e:
            logger.warning(f"⚠️ elaw MST 추출 실패 (async): {e}")
            return None

        if not mst:
            return None

        # Step 2: lawService.do elaw 비동기 조회 (2회 재시도)
        last_err = None
        client = await self._get_async_client()
        for attempt in range(2):
            try:
                params = {
                    "OC": self.drf_key,
                    "target": "elaw",
                    "MST": mst,
                    "type": "JSON",
                }
                r = await client.get(_LAW_SERVICE_URL, params=params, timeout=max(float(self.timeout_sec), 15.0))
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}")
                data = r.json()
                try:
                    await _aio.to_thread(_cache_set, cache_key, {"data": data, "law_name_en": law_name_en, "mst": mst, "_cached_at": _time.time()}, 21600)
                except Exception:
                    pass
                return data
            except Exception as e:
                last_err = e
                if attempt < 1:
                    wait = 0.5 + _random.uniform(0, 0.3)
                    logger.warning(f"⚠️ elawService async 재시도 {attempt+1}/2: {law_name_en} MST={mst}: {e}")
                    await _aio.sleep(wait)
        logger.warning(f"⚠️ elawService async 2회 실패: {law_name_en}: {last_err}")
        return None
