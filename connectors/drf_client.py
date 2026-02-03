import requests
import time
import re
from typing import Dict, Any, Optional, List
from connectors.validator import LawmadiValidator
from connectors import db_client


class DRFConnector:
    """
    DRF 법령 검색 + 검증
    + Query Rewrite
    + Domain Signal 추출
    """

    QUERY_REWRITE_RULES = {
        "전세": ["주택임대차보호법", "민법 임대차"],
        "전세사기": ["주택임대차보호법", "민법 임대차", "사기"],
        "보증금": ["주택임대차보호법", "민법"],
        "임대차": ["주택임대차보호법", "민법 임대차"],
        "깡통전세": ["주택임대차보호법"],
        "임대인": ["주택임대차보호법", "민법"],
        "임차인": ["주택임대차보호법", "민법"],

        "계약": ["민법"],
        "손해배상": ["민법 손해배상"],
        "채무": ["민법 채권"],
        "해제": ["민법 계약해제"],
        "취소": ["민법 취소"],
        "부당이득": ["민법 부당이득"],

        "사기": ["형법 사기"],
        "횡령": ["형법 횡령"],
        "배임": ["형법 배임"],
        "고소": ["형법", "형사소송법"],
        "처벌": ["형법"],
        "형사": ["형법"],

        "대출": ["금융소비자보호법"],
        "보이스피싱": ["전기통신금융사기 피해방지법"],
        "카드": ["여신전문금융업법"],
        "금융사기": ["금융소비자보호법"]
    }

    LAW_DOMAIN_MAP = {
        "주택임대차보호법": "REAL_ESTATE",
        "민법": "CIVIL",
        "형법": "CRIMINAL",
        "형사소송법": "CRIMINAL",
        "금융소비자보호법": "FINANCE",
        "여신전문금융업법": "FINANCE",
        "전기통신금융사기 피해방지법": "FINANCE"
    }

    def __init__(self, api_key, timeout_ms, endpoints, cb, api_failure_policy):
        self.api_key = api_key
        self.timeout_sec = timeout_ms / 1000.0
        self.endpoints = endpoints
        self.cb = cb
        self.policy = api_failure_policy
        self.rpm_limit = 120
        self.validator = LawmadiValidator()

    def fetch_verified_law(self, query: str) -> Dict[str, Any]:
        cache_key = f"law:{query.strip()}"

        # 🔒 DB Cache 비활성화 (ADC 없을 때 Fail-soft)
        cached = None

        # 🔒 DB 기반 rate limit 비활성화 (로컬/개발 모드)
        pass

        query_candidates = self._rewrite_query_candidates(query)
        law_domains = self._extract_law_domains(query_candidates)

        for q in query_candidates:
            raw = self._execute_request(
                self.endpoints["lawSearch"],
                {"OC": self.api_key, "target": "law", "type": "json", "query": q}
            )
            if not raw:
                continue

            structured = self._wrap_law_response(raw)
            if structured["content"] and self.validator.validate_all(structured):
                db_client.cache_set(cache_key, structured["content"])
                structured["law_domains"] = law_domains
                structured["query_used"] = q
                return structured

        return self._fail_closed("LMD-CONST-005")

    def _rewrite_query_candidates(self, query: str) -> List[str]:
        candidates = [query]
        for k, laws in self.QUERY_REWRITE_RULES.items():
            if k in query:
                for law in laws:
                    candidates.append(f"{law} {query}")
        return list(dict.fromkeys(candidates))[:5]

    def _extract_law_domains(self, candidates: List[str]) -> List[str]:
        domains = set()
        for q in candidates:
            for law, domain in self.LAW_DOMAIN_MAP.items():
                if law in q:
                    domains.add(domain)
        return list(domains)

    def _execute_request(self, url: str, params: Dict[str, str]) -> Optional[Dict]:
        try:
            r = requests.get(url, params=params, timeout=self.timeout_sec)
            r.raise_for_status()
            return r.json()
        except Exception:
            self.cb.record_failure()
            return None

    def _wrap_law_response(self, raw: Dict) -> Dict[str, Any]:
        laws = raw.get("LawSearch", {}).get("Law", [])
        return {
            "status": "Verified" if laws else "Empty",
            "content": laws
        }

    def _fail_closed(self, event: str):
        return {
            "status": "FAIL_CLOSED",
            "event": event,
            "message": "법령 검증 실패"
        }


def fetch_verified_law_full(query: str):
    # 1단계: 법령 검색
    search = fetch_verified_law(query)
    laws = search.get("laws", []) if isinstance(search, dict) else []
    if not laws:
        return {"status": "FAIL_CLOSED"}

    # 2단계: 첫 번째 법령 조문 조회
    law = laws[0]
    law_id = law.get("법령ID") or law.get("lawId")
    if not law_id:
        return {"status": "FAIL_CLOSED"}

    detail = law_service(law_id)
    return {
        "status": "OK",
        "law": law.get("법령명"),
        "articles": detail
    }

# 🔧 Runtime Monkey Patch: DRF 2단 호출을 Connector 메서드로 연결
def _bind_full_fetch():
    def fetch_verified_law_full(self, query: str):
        search = self.fetch_verified_law(query)
        laws = search.get("laws", []) if isinstance(search, dict) else []
        if not laws:
            return {"status": "FAIL_CLOSED"}

        law = laws[0]
        law_id = law.get("법령ID") or law.get("lawId")
        if not law_id:
            return {"status": "FAIL_CLOSED"}

        detail = self.law_service(law_id)
        return {
            "status": "OK",
            "law": law.get("법령명"),
            "articles": detail
        }

    DRFConnector.fetch_verified_law_full = fetch_verified_law_full

_bind_full_fetch()

from core.drf_integrity import hash_article
