import requests
import logging
import json
import hashlib
import datetime
import time
from typing import Any, Dict, Optional, List

# 사용자 프로젝트 모듈 임포트
try:
    from connectors.validator import LawmadiValidator
    from core.law_selector import LawSelector
except ImportError:
    # 모듈 부재 시 폴백 로직
    LawmadiValidator = None
    LawSelector = None

# [IT 기술: 커넥터 계층 고가용성 로깅 설정]
logger = logging.getLogger("LawmadiOS.DRFConnector")

class DRFConnector:
    """
    [L3/L5 하이브리드: Hardened 지능형 커넥터]
    지능형 쿼리 재작성(Recon), 정밀 타격(Strike), 그리고 Cloud SQL 기반 
    무결성 캐싱이 통합된 Lawmadi OS의 핵심 데이터 수집 레이어입니다.
    """

    # IT 기술: 시맨틱 검색 보정을 위한 쿼리 재작성 규칙
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
        "양육비": ["가사소송법", "양육비 이행확보 및 지원에 관한 법률"]
    }

    def __init__(self, api_key: str, db: Any = None, timeout_ms: int = 5000, endpoints: Dict[str, str] = None, cb: Any = None, api_failure_policy: str = "FAIL_CLOSED"):
        self.api_key = api_key
        self.db = db  # Cloud SQL 연결 (PostgreSQL)
        self.timeout_sec = timeout_ms / 1000.0
        self.endpoints = endpoints
        self.cb = cb
        self.policy = api_failure_policy
        self.env_version = '50.1.3-GA-HARDENED'
        
        # 지능형 모듈 초기화
        self.validator = LawmadiValidator() if LawmadiValidator else None
        self.selector = LawSelector() if LawSelector else None

    # =========================================================
    # 🛡️ [INFRA HARDENING] 캐시 및 무결성 엔진
    # =========================================================

    def _generate_signature(self, content: str) -> str:
        """[LMD-CONST-005] SHA-256 기반 데이터 무결성 서명 생성"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _check_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Cloud SQL 'drf_cache'에서 유효한 서명 데이터 조회"""
        if not self.db: return None
        try:
            # IT 기술: 만료되지 않은 데이터만 조회
            query = "SELECT content, signature FROM drf_cache WHERE cache_key = %s AND expires_at > NOW()"
            result = self.db.execute(query, (cache_key,)).fetchone()
            if result:
                content_json, signature = result
                # 데이터 무결성 검증: 저장 시점의 서명과 현재 내용 대조
                if self._generate_signature(json.dumps(content_json)) == signature:
                    return content_json
                else:
                    logger.error(f"🚨 [INTEGRITY_VIOLATION] 캐시 오염 감지: {cache_key}")
            return None
        except Exception as e:
            logger.error(f"⚠️ 캐시 엔진 장애: {e}")
            return None

    def _set_cache(self, cache_key: str, content_dict: Dict[str, Any], ttl_days: int = 30):
        """무결성 서명을 포함하여 Cloud SQL에 캐시 저장 (UPSERT)"""
        if not self.db: return
        try:
            content_str = json.dumps(content_dict)
            signature = self._generate_signature(content_str)
            expires_at = datetime.datetime.now() + datetime.timedelta(days=ttl_days)
            
            query = """
                INSERT INTO drf_cache (cache_key, content, signature, expires_at, env_version)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (cache_key) DO UPDATE SET 
                content = EXCLUDED.content, signature = EXCLUDED.signature, 
                expires_at = EXCLUDED.expires_at, created_at = NOW();
            """
            self.db.execute(query, (cache_key, content_str, signature, expires_at, self.env_version))
            self.db.commit()
        except Exception as e:
            logger.error(f"⚠️ 캐시 쓰기 오류: {e}")

    # =========================================================
    # 🚦 [RATE LIMITER] 지능형 트래픽 제어
    # =========================================================

    def _is_rate_limited(self, provider: str = "LAW_GO_KR_DRF") -> bool:
        """Cloud SQL 기반 윈도우별 API 호출 횟수 체크 및 카운트 증가"""
        if not self.db: return False
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            # 1분 단위 윈도우 설정
            window_start = now.replace(second=0, microsecond=0)
            window_end = window_start + datetime.timedelta(minutes=1)

            # IT 기술: Atomic Upsert를 통한 호출 카운트 증가
            query = """
                INSERT INTO rate_limit_tracker (provider, call_count, window_start, window_end, env_version)
                VALUES (%s, 1, %s, %s, %s)
                ON CONFLICT (provider) DO UPDATE SET
                call_count = CASE 
                    WHEN rate_limit_tracker.window_end < NOW() THEN 1 
                    ELSE rate_limit_tracker.call_count + 1 
                END,
                window_start = CASE WHEN rate_limit_tracker.window_end < NOW() THEN %s ELSE rate_limit_tracker.window_start END,
                window_end = CASE WHEN rate_limit_tracker.window_end < NOW() THEN %s ELSE rate_limit_tracker.window_end END
                RETURNING call_count;
            """
            result = self.db.execute(query, (provider, window_start, window_end, self.env_version, window_start, window_end)).fetchone()
            self.db.commit()

            # DRF 정책: 120 rpm 준수
            if result and result[0] > 120:
                logger.warning(f"🚫 [RATE_LIMIT] 공급자 제한 도달: {provider} ({result[0]} calls)")
                return True
            return False
        except Exception as e:
            logger.error(f"⚠️ Rate Limit 트래킹 오류: {e}")
            return False

    # =========================================================
    # 📡 [CORE PIPELINE] Recon & Strike 지능형 로직
    # =========================================================

    def fetch_verified_law(self, query: str) -> Dict[str, Any]:
        """[L3/L5] 정찰(Recon) -> 선택(Selection) -> 타격(Strike) 통합 파이프라인"""
        cache_key = f"law_smart_{hashlib.md5(query.encode()).hexdigest()}"
        
        # 1. 인프라 캐시 확인
        cached = self._check_cache(cache_key)
        if cached: 
            logger.info(f"💾 캐시 히트: {query[:10]}...")
            return cached

        # 2. Rate Limit 확인
        if self._is_rate_limited():
            return self._fail_closed("LMD-CONST-009_RATE_LIMIT")

        # 3. 정찰 (Recon): 질문 기반 연관 법령군 탐색
        search_queries = self._rewrite_query_candidates(query)
        candidates = []
        seen_ids = set()

        for q in search_queries:
            raw = self._execute_request(
                self.endpoints.get("lawSearch", "https://www.law.go.kr/DRF/lawSearch.do"),
                {"OC": self.api_key, "target": "law", "type": "json", "query": q}
            )
            if not raw: continue
            
            items = raw.get("LawSearch", {}).get("Law", [])
            if isinstance(items, dict): items = [items]

            for item in items:
                lid = item.get("법령ID")
                lname = item.get("법령명한글", item.get("법령명"))
                if lid and lid not in seen_ids:
                    candidates.append({"id": lid, "name": lname})
                    seen_ids.add(lid)
        
        if not candidates:
            return self._fail_closed("LMD-CONST-005_NO_CANDIDATE")

        # 4. 선택 (Selection): L5 지능형 에이전트의 최적 법령 판단
        best_law = None
        if self.selector:
            best_law = self.selector.select_best_law(query, candidates)
        
        if not best_law:
            best_law = candidates[0]

        # 5. 타격 (Strike): 선택된 법령의 상세 데이터 정밀 획득
        detail_raw = self._execute_request(
            self.endpoints.get("lawService", "https://www.law.go.kr/DRF/lawService.do"),
            {"OC": self.api_key, "target": "law", "type": "json", "ID": best_law['id']}
        )
        
        if not detail_raw:
            return self._fail_closed("LMD-CONST-007_FETCH_FAIL")

        # 6. 응답 구조화 및 캐시 저장
        structured = self._wrap_law_response(detail_raw)
        structured["query_used"] = query
        structured["selected_law_name"] = best_law['name']
        structured["source"] = "API_STRIKE"
        
        self._set_cache(cache_key, structured)
        return structured

    def _rewrite_query_candidates(self, query: str) -> List[str]:
        """키워드 매핑을 통한 검색어 확장 (Recon)"""
        candidates = [query]
        for k, laws in self.QUERY_REWRITE_RULES.items():
            if k in query: candidates.extend(laws)
        return list(dict.fromkeys(candidates))[:5]

    def _execute_request(self, url: str, params: Dict[str, str]) -> Optional[Dict]:
        """IT 기술: 하드웨어 타임아웃 및 예외 처리가 통합된 실행 레이어"""
        try:
            r = requests.get(url, params=params, timeout=self.timeout_sec)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"📡 API 통신 장애: {url} | {e}")
            if self.cb: self.cb.record_failure()
            return None

    def _wrap_law_response(self, raw: Dict) -> Dict[str, Any]:
        """최종 응답 패키징"""
        laws = raw.get("LawService", {}) or raw.get("Law", {})
        return {
            "status": "VERIFIED" if laws else "EMPTY", 
            "content": laws,
            "timestamp": datetime.datetime.now().isoformat()
        }

    def _fail_closed(self, event: str):
        """[IT 보안] 장애 시 안전 차단 정책(Fail-Closed)"""
        logger.warning(f"🚨 Fail-Closed 트리거: {event}")
        return {"status": "FAIL_CLOSED", "event": event, "message": "법령 근거를 확정할 수 없습니다."}

    def fetch_precedents(self, query: str) -> Dict[str, Any]:
        """판례 검색 (캐시 엔진 통합)"""
        cache_key = f"prec_{hashlib.md5(query.encode()).hexdigest()}"
        cached = self._check_cache(cache_key)
        if cached: return cached

        if self._is_rate_limited():
            return self._fail_closed("LMD-CONST-009_RATE_LIMIT")

        try:
            params = {"OC": self.api_key, "target": "prec", "type": "json", "query": query}
            r = requests.get(self.endpoints.get("precSearch", "https://www.law.go.kr/DRF/precSearch.do"), params=params, timeout=self.timeout_sec)
            if r.status_code == 200:
                res = r.json()
                self._set_cache(cache_key, res)
                return {"status": "VERIFIED", "raw_data": res, "source": "API"}
            return {"status": "ERROR", "message": "판례 데이터 수신 실패"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}