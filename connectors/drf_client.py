from core.drf_integrity import validate_drf_xml
import os
import requests
import xml.etree.ElementTree as ET
import logging
import hashlib
from typing import Optional, Dict

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
    def _call_drf(self, query):

        if not self.drf_key or not self.drf_url:
            raise RuntimeError("DRF not available")

        params = {
            "OC": self.drf_key,
            "target": "law",
            "type": "XML",
            "query": query
        }

        r = requests.get(self.drf_url, params=params, timeout=self.timeout_sec)

        if r.status_code != 200:
            raise RuntimeError(f"DRF HTTP {r.status_code}")

        content_type = r.headers.get("Content-Type", "")
        if "xml" not in content_type and "json" not in content_type:
            raise RuntimeError(f"DRF unexpected Content-Type: {content_type}")

        validate_drf_xml(r.text)

        return ET.fromstring(r.text)

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
    # 🔥 교차 재시도 Dual SSOT (+ 캐싱)
    # -------------------------------------------------
    def law_search(self, query):
        # 캐싱 초기화 (최초 1회)
        _init_cache()

        # 1) 캐시 조회 (query 기반 MD5 해시)
        cache_key = f"drf:v2:{hashlib.md5(query.encode('utf-8')).hexdigest()}"

        try:
            cached_data = _cache_get(cache_key)
            if cached_data and cached_data.get("xml_text"):
                logger.info(f"🎯 [Cache HIT] {query[:50]}...")
                # 캐시된 XML 텍스트를 ElementTree로 파싱
                return ET.fromstring(cached_data["xml_text"])
        except Exception as e:
            logger.warning(f"⚠️ [Cache] 조회 실패: {e}")

        # 2) 캐시 미스 - API 호출 (기존 Dual SSOT 로직)
        logger.info(f"🔍 [Cache MISS] {query[:50]}... (API 호출)")

        attempts = [
            ("DRF-1", self._call_drf),
            ("DATA-1", self._call_data_go),
            ("DRF-2", self._call_drf),
            ("DATA-2", self._call_data_go),
        ]

        for label, fn in attempts:
            try:
                logger.info(f"[DualSSOT] Attempt {label}")
                result = fn(query)

                if result is not None:
                    logger.info(f"[DualSSOT] SUCCESS via {label}")

                    # 3) 캐시 저장 (XML 텍스트로 변환하여 저장)
                    try:
                        xml_text = ET.tostring(result, encoding='unicode')
                        _cache_set(
                            cache_key,
                            {
                                "xml_text": xml_text,
                                "query": query[:200],  # 디버깅용
                                "source": label
                            },
                            ttl_seconds=3600  # 1시간 캐시
                        )
                        logger.info(f"💾 [Cache SET] {cache_key[:16]}... (TTL: 1h)")
                    except Exception as e:
                        logger.warning(f"⚠️ [Cache] 저장 실패: {e}")

                    return result

            except Exception as e:
                logger.warning(f"[DualSSOT] {label} failed: {str(e)}")

        logger.error("[DualSSOT] All attempts failed. Returning None.")
        return None
