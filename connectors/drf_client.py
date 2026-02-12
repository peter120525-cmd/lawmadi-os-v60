from core.drf_integrity import validate_drf_xml
import os
import requests
import xml.etree.ElementTree as ET
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

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
    # 🔥 교차 재시도 Dual SSOT
    # -------------------------------------------------
    def law_search(self, query):

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
                    return result

            except Exception as e:
                logger.warning(f"[DualSSOT] {label} failed: {str(e)}")

        logger.error("[DualSSOT] All attempts failed. Returning None.")
        return None
