import logging
from typing import Optional, Any, Dict

from connectors.drf_client import DRFConnector

logger = logging.getLogger(__name__)


class SearchService:
    """
    SearchService (Facade)
    - 외부 인터페이스 유지
    - 실제 SSOT 검색은 DRFConnector에 위임
    """

    def __init__(self, config: Optional[Dict] = None) -> None:
        try:
            if config:
                self.drf = DRFConnector(config=config)
            else:
                self.drf = DRFConnector()
            self.ready = True
            logger.info("✅ SearchService bound to DRFConnector (Dual SSOT)")
        except Exception as e:
            self.drf = None
            self.ready = False
            logger.warning(f"🟡 SearchService init degraded: {e}")

    def search_law(self, query: str) -> Optional[Any]:
        if not self.ready or not self.drf:
            logger.warning("⚠️ SearchService not ready (law)")
            return None
        try:
            return self.drf.law_search(query)
        except Exception as e:
            logger.warning(f"⚠️ search_law failed: {e}")
            return None

    def search_precedent(self, query: str) -> Optional[Any]:
        if not self.ready or not self.drf:
            logger.warning("⚠️ SearchService not ready (precedent)")
            return None
        try:
            return self.drf.law_search(query)
        except Exception as e:
            logger.warning(f"⚠️ search_precedent failed: {e}")
            return None

    def search_precedents(self, limit: int = 10) -> Optional[Any]:
        """판례 목록 조회 (DRF law_search 위임)"""
        if not self.ready or not self.drf:
            logger.warning("⚠️ SearchService not ready (precedents)")
            return None
        try:
            return self.drf.law_search("판례")
        except Exception as e:
            logger.warning(f"⚠️ search_precedents failed: {e}")
            return None
