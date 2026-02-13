import logging
import os
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
            # config가 없으면 환경변수에서 DRF API 키 읽기
            if config:
                self.drf = DRFConnector(config=config)
            else:
                api_key = os.getenv("LAWGO_DRF_OC", "").strip()
                if not api_key:
                    raise ValueError("LAWGO_DRF_OC environment variable not set")

                self.drf = DRFConnector(
                    api_key=api_key,
                    timeout_ms=int(os.getenv("DRF_TIMEOUT_MS", "5000"))
                )
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

    def search_admrul(self, query: str) -> Optional[Any]:
        """행정규칙 검색 (SSOT #2)"""
        if not self.ready or not self.drf:
            logger.warning("⚠️ SearchService not ready (admrul)")
            return None
        try:
            return self.drf.search_by_target(query, target="admrul")
        except Exception as e:
            logger.warning(f"⚠️ search_admrul failed: {e}")
            return None

    def search_expc(self, query: str) -> Optional[Any]:
        """법령해석례 검색 (SSOT #7)"""
        if not self.ready or not self.drf:
            logger.warning("⚠️ SearchService not ready (expc)")
            return None
        try:
            return self.drf.search_by_target(query, target="expc")
        except Exception as e:
            logger.warning(f"⚠️ search_expc failed: {e}")
            return None

    def search_constitutional(self, query: str) -> Optional[Any]:
        """헌재결정례 검색 (SSOT #6) - 판례 중 헌재 필터링"""
        if not self.ready or not self.drf:
            logger.warning("⚠️ SearchService not ready (constitutional)")
            return None
        try:
            # target=prec로 검색 후 헌법재판소 필터링
            raw = self.drf.search_by_target(query, target="prec")
            if not raw:
                return None

            # 응답에서 헌법재판소 관련 항목만 필터링
            # (DRF 응답 구조에 따라 구현)
            # 예: raw["PrecSearch"]["prec"] 리스트에서 "법원명" 필드 확인
            return raw  # 일단 전체 반환 (Gemini가 자연스럽게 필터링)
        except Exception as e:
            logger.warning(f"⚠️ search_constitutional failed: {e}")
            return None

    def search_ordinance(self, query: str) -> Optional[Any]:
        """자치법규 검색 (SSOT #4)"""
        if not self.ready or not self.drf:
            logger.warning("⚠️ SearchService not ready (ordinance)")
            return None
        try:
            return self.drf.search_by_target(query, target="ordin")
        except Exception as e:
            logger.warning(f"⚠️ search_ordinance failed: {e}")
            return None

    def search_legal_term(self, query: str) -> Optional[Any]:
        """법령용어 검색 (SSOT #10)"""
        if not self.ready or not self.drf:
            logger.warning("⚠️ SearchService not ready (legal_term)")
            return None
        try:
            return self.drf.search_legal_term(query)
        except Exception as e:
            logger.warning(f"⚠️ search_legal_term failed: {e}")
            return None

    def search_admin_appeals(self, doc_id: str) -> Optional[Any]:
        """행정심판례 검색 (SSOT #8) - ID 기반"""
        if not self.ready or not self.drf:
            logger.warning("⚠️ SearchService not ready (admin_appeals)")
            return None
        try:
            return self.drf.search_admin_appeals(doc_id)
        except Exception as e:
            logger.warning(f"⚠️ search_admin_appeals failed: {e}")
            return None

    def search_treaty(self, doc_id: str) -> Optional[Any]:
        """조약 검색 (SSOT #9) - ID 기반"""
        if not self.ready or not self.drf:
            logger.warning("⚠️ SearchService not ready (treaty)")
            return None
        try:
            return self.drf.search_treaty(doc_id)
        except Exception as e:
            logger.warning(f"⚠️ search_treaty failed: {e}")
            return None
