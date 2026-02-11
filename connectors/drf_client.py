# connectors/drf_client.py
import requests
import logging
import json
import hashlib
from typing import Any, Dict, Optional, List
from datetime import datetime, timezone

# 지능형 모듈 (있으면 사용, 없으면 폴백)
try:
    from connectors.validator import LawmadiValidator  # optional
    from core.law_selector import LawSelector          # optional
except Exception:
    LawmadiValidator = None
    LawSelector = None

# DB 인터페이스는 v2로 고정 (Fail-soft)
try:
    import connectors.db_client as db
except Exception:
    db = None

logger = logging.getLogger("LawmadiOS.DRFConnector")


class DRFConnector:
    """
    Lawmadi OS DRF Connector (Hardened)
    - Recon(검색어 확장) -> Selection(최적 법령 선택) -> Strike(본문 조회)
    - Cloud SQL(Postgres) 기반 On-Demand Cache + Rate Limit
    """

    DEFAULT_ENDPOINTS = {
        "lawSearch": "http://www.law.go.kr/DRF/lawSearch.do",
        "lawService": "http://www.law.go.kr/DRF/lawService.do",
        "precSearch": "http://www.law.go.kr/DRF/lawSearch.do",
        "precService": "http://www.law.go.kr/DRF/lawService.do",
        # 필요 시 확장:
        # "admrulSearch": "http://www.law.go.kr/DRF/admrulSearch.do",
        # "admrulService": "http://www.law.go.kr/DRF/admrulService.do",
    }

    QUERY_REWRITE_RULES = {
        "전세": ["주택임대차보호법", "민법"],
        "보증금": ["주택임대차보호법", "민법"],
        "임대차": ["주택임대차보호법", "민법"],
        "상가": ["상가건물 임대차보호법"],
        "소음": ["공동주택관리법", "소음·진동관리법"],
        "해고": ["근로기준법"],
        "임금": ["근로기준법", "최저임금법"],
        "사기": ["형법", "특정경제범죄 가중처벌 등에 관한 법률"],
        "이혼": ["민법", "가사소송법"],
        "양육비": ["가사소송법", "양육비 이행확보 및 지원에 관한 법률"],
    }

    def __init__(
        self,
        api_key: str,
        timeout_ms: int = 5000,
        endpoints: Optional[Dict[str, str]] = None,
        cb: Any = None,
        api_failure_policy: str = "FAIL_CLOSED",
        env_version: str = "v50.2.3-HARDENED",
        rate_limit_rpm: int = 120,
        rate_limit_window_seconds: int = 60,
        cache_ttl_seconds: int = 3600,
    ):
        self.api_key = (api_key or "").strip()
        self.timeout_sec = max(0.5, timeout_ms / 1000.0)
        self.endpoints = {**self.DEFAULT_ENDPOINTS, **(endpoints or {})}
        self.cb = cb
        self.policy = api_failure_policy
        self.env_version = env_version

        self.rate_limit_rpm = int(rate_limit_rpm)
        self.rate_limit_window_seconds = int(rate_limit_window_seconds)
        self.cache_ttl_seconds = int(cache_ttl_seconds)

        self.validator = LawmadiValidator() if LawmadiValidator else None
        self.selector = LawSelector() if LawSelector else None

    # -----------------------------
    # Internal helpers
    # -----------------------------
    def _fail_closed(self, event: str) -> Dict[str, Any]:
        logger.warning(f"🚨 Fail-Closed: {event}")
        return {"status": "FAIL_CLOSED", "event": event, "message": "법령 근거를 확정할 수 없습니다."}

    def _rewrite_query_candidates(self, query: str) -> List[str]:
        q = (query or "").strip()
        if not q:
            return []
        candidates = [q]
        for k, laws in self.QUERY_REWRITE_RULES.items():
            if k in q:
                candidates.extend(laws)
        # 중복 제거 + 최대 5개
        return list(dict.fromkeys(candidates))[:5]

    def _request_json(self, url: str, params: Dict[str, str]) -> Optional[Dict[str, Any]]:
        try:
            r = requests.get(url, params=params, timeout=self.timeout_sec)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"📡 API 통신 오류: {url} | {e}")
            if self.cb:
                try:
                    self.cb.record_failure()
                except Exception:
                    pass
            return None

    def _cache_get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        if not db:
            return None
        try:
            return db.cache_get(cache_key)
        except Exception:
            return None

    def _cache_set(self, cache_key: str, content: Dict[str, Any], ttl_seconds: Optional[int] = None) -> None:
        if not db:
            return
        try:
            db.cache_set(cache_key, content, ttl_seconds=ttl_seconds or self.cache_ttl_seconds)
        except Exception:
            pass

    def _rate_limit_ok(self, provider: str = "LAW_GO_KR_DRF") -> bool:
        """
        - 먼저 check(허용 여부) -> 허용이면 hit(카운트 증가)
        - DB가 꺼져있거나 오류면 Fail-soft(허용)
        """
        if not db:
            return True
        try:
            ok = db.rate_limit_check(provider, limit=self.rate_limit_rpm)
            if ok:
                db.rate_limit_hit(provider, window_seconds=self.rate_limit_window_seconds)
            return ok
        except Exception:
            return True

    def _wrap_law_service(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        laws = raw.get("LawService") or raw.get("Law") or {}
        return {
            "status": "VERIFIED" if laws else "EMPTY",
            "content": laws,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # -----------------------------
    # Public APIs
    # -----------------------------
    def search_laws(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        lawSearch.do로 목록 조회 (경량)
        - On-Demand 캐시/분석의 입력으로 사용하기 좋음
        """
        q = (query or "").strip()
        if not q:
            return []

        if not self._rate_limit_ok():
            return []

        raw = self._request_json(
            self.endpoints["lawSearch"],
            {"OC": self.api_key, "target": "law", "type": "json", "query": q},
        )
        if not raw:
            return []

        items = raw.get("LawSearch", {}).get("Law", [])
        if isinstance(items, dict):
            items = [items]

        out: List[Dict[str, Any]] = []
        for it in items[: max(1, int(limit))]:
            law_id = it.get("법령ID") or it.get("lawId") or ""
            title = it.get("법령명한글") or it.get("법령명") or it.get("title") or "제목 없음"
            deep_link = it.get("법령상세링크") or it.get("link") or ""
            if not deep_link and title:
                deep_link = f"https://www.law.go.kr/법령/{title}"

            out.append(
                {
                    "law_id": str(law_id),
                    "title": str(title),
                    "deep_link": str(deep_link),
                }
            )
        return out

    def get_law_detail(self, law_id: str) -> Dict[str, Any]:
        """
        lawService.do로 본문/구조 조회
        """
        lid = (law_id or "").strip()
        if not lid:
            return {"status": "ERROR", "message": "empty law_id"}

        cache_key = f"law_detail_{hashlib.md5(lid.encode()).hexdigest()}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        if not self._rate_limit_ok():
            return self._fail_closed("LMD-CONST-009_RATE_LIMIT")

        raw = self._request_json(
            self.endpoints["lawService"],
            {"OC": self.api_key, "target": "law", "type": "json", "ID": lid},
        )
        if not raw:
            return self._fail_closed("LMD-CONST-007_FETCH_FAIL")

        structured = {"status": "VERIFIED", "law_id": lid, "raw": raw}
        self._cache_set(cache_key, structured)
        return structured

    def fetch_verified_law(self, query: str) -> Dict[str, Any]:
        """
        Recon -> Selection -> Strike
        """
        q = (query or "").strip()
        if not q:
            return self._fail_closed("EMPTY_QUERY")

        cache_key = f"law_smart_{hashlib.md5(q.encode()).hexdigest()}"
        cached = self._cache_get(cache_key)
        if cached:
            logger.info(f"💾 cache hit: {q[:12]}...")
            return cached

        if not self._rate_limit_ok():
            return self._fail_closed("LMD-CONST-009_RATE_LIMIT")

        # Recon
        search_queries = self._rewrite_query_candidates(q)
        candidates: List[Dict[str, str]] = []
        seen = set()

        for sq in search_queries:
            raw = self._request_json(
                self.endpoints["lawSearch"],
                {"OC": self.api_key, "target": "law", "type": "json", "query": sq},
            )
            if not raw:
                continue

            items = raw.get("LawSearch", {}).get("Law", [])
            if isinstance(items, dict):
                items = [items]

            for item in items:
                lid = item.get("법령ID")
                lname = item.get("법령명한글") or item.get("법령명") or ""
                if lid and lid not in seen:
                    candidates.append({"id": str(lid), "name": str(lname)})
                    seen.add(lid)

        if not candidates:
            return self._fail_closed("LMD-CONST-005_NO_CANDIDATE")

        # Selection
        best = None
        if self.selector:
            try:
                best = self.selector.select_best_law(q, candidates)
            except Exception:
                best = None
        if not best:
            best = candidates[0]

        # Strike
        raw_detail = self._request_json(
            self.endpoints["lawService"],
            {"OC": self.api_key, "target": "law", "type": "json", "ID": best["id"]},
        )
        if not raw_detail:
            return self._fail_closed("LMD-CONST-007_FETCH_FAIL")

        structured = self._wrap_law_service(raw_detail)
        structured.update(
            {
                "query_used": q,
                "selected_law": best,
                "source": "API_STRIKE",
            }
        )

        self._cache_set(cache_key, structured)
        return structured

    def fetch_precedents(self, query: str) -> Dict[str, Any]:
        """
        lawSearch.do 판례 목록 검색 (필요 시 precService 확장)
        """
        q = (query or "").strip()
        if not q:
            return {"status": "ERROR", "message": "empty query"}

        cache_key = f"prec_{hashlib.md5(q.encode()).hexdigest()}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        if not self._rate_limit_ok():
            return self._fail_closed("LMD-CONST-009_RATE_LIMIT")

        raw = self._request_json(
            self.endpoints["precSearch"],
            {"OC": self.api_key, "target": "prec", "type": "json", "query": q},
        )
        if not raw:
            return {"status": "ERROR", "message": "판례 데이터 수신 실패"}

        structured = {"status": "VERIFIED", "raw_data": raw, "source": "API"}
        self._cache_set(cache_key, structured)
        return structured
