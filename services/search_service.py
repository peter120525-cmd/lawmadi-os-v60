import os
import logging
from typing import Any, Dict, Optional

from connectors.drf_client import DRFConnector

logger = logging.getLogger("LawmadiOS.SearchService")

class SearchService:
    """
    Minimal SearchService (debug-stable)
    - main.py가 ENABLE_SEARCH_SERVICE=true일 때 생성할 수 있도록
      __init__() 인자 없이 동작
    - 내부에서 DRFConnector를 직접 생성해 lawSearch/precSearch를 호출
    """

    def __init__(self):
        oc = os.getenv("LAWGO_DRF_OC", "choepeter").strip()
        timeout_ms = int(os.getenv("DRF_TIMEOUT_MS", "5000"))
        self.drf = DRFConnector(api_key=oc, timeout_ms=timeout_ms)
        logger.warning(f"✅ SearchService online (oc={oc}, timeout_ms={timeout_ms})")

    def search_law(self, query: str) -> Optional[Dict[str, Any]]:
        params = {"OC": self.drf.api_key, "target": "law", "type": "JSON", "query": query}
        return self.drf._request_json(self.drf.endpoints["lawSearch"], params)

    def search_precedents(self, query: str) -> Optional[Dict[str, Any]]:
        params = {"OC": self.drf.api_key, "target": "prec", "type": "JSON", "query": query}
        # precSearch는 현재 lawSearch.do로 매핑되어 있어야 정상
        return self.drf._request_json(self.drf.endpoints["precSearch"], params)
