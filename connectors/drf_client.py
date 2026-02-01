import requests
import time
import re
from typing import Dict, Any, Optional
from connectors.validator import LawmadiValidator
from connectors import db_client


class DRFConnector:
    """
    [L3-L5] 국가법령정보센터(DRF) API 통신 및 7단계 검증
    캐시: Cloud SQL (db_client.cache_get / cache_set)
    Rate Limit: Cloud SQL (db_client.rate_limit_check)
    config.data_sync_connectors 참조
    """
    def __init__(
        self,
        api_key: str,
        timeout_ms: int,
        endpoints: Dict[str, str],
        cb,  # CircuitBreaker instance
        api_failure_policy: Dict[str, Any]
    ):
        self.api_key = api_key
        self.timeout_sec = timeout_ms / 1000.0
        self.endpoints = endpoints
        self.cb = cb
        self.policy = api_failure_policy

        self.max_retries: int = self.policy.get("max_retries", 5)
        self.retry_interval_sec: int = self.policy.get("retry_interval_sec", 60)
        self.max_consecutive_failures: int = self.policy.get("max_consecutive_failures", 5)
        self.rpm_limit: int = 120  # config.data_sync_connectors.rate_limits.LAW_GO_KR_DRF

        self.consecutive_failures = 0
        self.validator = LawmadiValidator()
        self._date_normalize_pattern = re.compile(r"^(\d{4})[.\-]?(\d{1,2})[.\-]?(\d{1,2})$")

    # ────────────────────────────────────────────────────────────────────────
    # PUBLIC: 법령 검색
    # ────────────────────────────────────────────────────────────────────────
    def fetch_verified_law(self, query: str) -> Dict[str, Any]:
        """
        캐시 조회 → 히트면 무결성 검증 후 반환
        미스면 API 호출 → 검증 → 캐시 저장
        """
        cache_key = f"law:{query.strip()}"

        # [캐시 조회]
        cached = db_client.cache_get(cache_key)
        if cached is not None:
            # 무결성 검증 (LMD-CONST-005)
            if db_client.cache_verify_signature(cache_key):
                print(f"📦 [Cache HIT] {cache_key}")
                cached["status"] = "Verified (Cache)"
                cached["source"] = "National Law Information Center (DRF) — Cached"
                return cached
            else:
                # 서명 불일치 → 캐시 삭제됨, API로 새로 가져옴
                print(f"🔄 [Cache MISS] 서명 불일치 → API 재조회")

        # [Rate Limit 체크]
        if not db_client.rate_limit_check("LAW_GO_KR_DRF", self.rpm_limit):
            print("⚠️ [Rate Limit] DRF 호출 횟수 초과. 잠시 후 다시 시도해 주세요.")
            # Rate Limit 초과 시 캐시가 있으면 그것을 반환 (007A)
            return self._handle_api_failure()

        # [API 호출]
        raw = self._execute_request(
            url=self.endpoints["law_search"],
            params={"OC": self.api_key, "target": "law", "type": "json", "query": query}
        )
        if raw is None:
            return self._handle_api_failure()

        # [구조화 및 검증]
        structured = self._wrap_law_response(raw)
        if not self.validator.validate_all(structured):
            return {"status": "FAIL_CLOSED", "message": "법령 데이터 무결성 검증 실패 (LMD-CONST-005)"}

        # [캐시 저장]
        signature = self.validator.generate_signature(structured["content"])
        structured["signature"] = signature
        db_client.cache_set(cache_key, structured["content"], signature, ttl_days=30)

        self.consecutive_failures = 0
        self.cb.record_success()
        return structured

    # ────────────────────────────────────────────────────────────────────────
    # PUBLIC: 판례 검증 (7단계)
    # ────────────────────────────────────────────────────────────────────────
    def fetch_verified_precedent(self, case_number: str, keywords: str = "") -> Dict[str, Any]:
        """
        7단계 PRECEDENT_VERIFICATION_PROTOCOL
        캐시 키: prec:{case_number}
        """
        cache_key = f"prec:{case_number.strip()}"

        # [캐시 조회]
        cached = db_client.cache_get(cache_key)
        if cached is not None and db_client.cache_verify_signature(cache_key):
            print(f"📦 [Cache HIT] {cache_key}")
            cached["status"] = "Verified (Cache)"
            cached["source"] = "National Law Information Center (DRF) — Cached"
            return cached

        # [Rate Limit]
        if not db_client.rate_limit_check("LAW_GO_KR_DRF", self.rpm_limit):
            return self._handle_api_failure()

        # [1단계] 사건번호 검색
        list_response = self._execute_request(
            url=self.endpoints["law_search"],
            params={"OC": self.api_key, "target": "prec", "type": "json", "nb": case_number}
        )
        if list_response is None:
            return self._handle_api_failure()

        # [2단계] 판례일련번호 추출
        prec_list = list_response.get("PrecSearch", {}).get("Prec", [])
        if not prec_list:
            return {"status": "FAIL_CLOSED", "event": "LMD-CONST-006",
                    "message": "입력하신 사건번호로 판례를 찾을 수 없습니다."}

        prec_id = None
        for item in prec_list:
            if str(item.get("사건번호", "")).strip() == case_number.strip():
                prec_id = item.get("판례일련번호")
                break

        if prec_id is None:
            return {"status": "FAIL_CLOSED", "event": "LMD-CONST-006",
                    "message": "사건번호가 정확히 일치하는 판례가 없습니다."}

        # [3단계] 본문 조회
        body_response = self._execute_request(
            url=self.endpoints["law_service"],
            params={"OC": self.api_key, "target": "prec", "type": "json", "ID": str(prec_id)}
        )
        if body_response is None:
            return self._handle_api_failure()

        prec_info = body_response.get("PrecInfo", {})

        # [4단계] 날짜 정규화
        raw_date = str(prec_info.get("선고일자", ""))
        normalized_date = self._normalize_date_from_drf(raw_date)
        if normalized_date is None:
            return {"status": "FAIL_CLOSED", "event": "LMD-CONST-006",
                    "message": f"선고일자 정규화 실패: '{raw_date}'"}

        # [5단계] 사건번호 EXACT MATCH
        body_case_number = str(prec_info.get("사건번호", "")).strip()
        if body_case_number != case_number.strip():
            return {"status": "FAIL_CLOSED", "event": "LMD-CONST-006",
                    "message": f"사건번호 불일치: 검색='{case_number}', 본문='{body_case_number}'"}

        # [6단계] 키워드 교차검증
        if keywords:
            summary = str(prec_info.get("판결요지", ""))
            if not self._cross_check_keywords(keywords, summary):
                return {"status": "FAIL_CLOSED", "event": "LMD-CONST-006",
                        "message": "키워드와 판결요지가 일치하지 않습니다."}

        # [7단계] 검증 완료 → 캐시 저장
        result_content = {
            "case_number": body_case_number,
            "decision_date": normalized_date,
            "summary": prec_info.get("판결요지", ""),
            "full_text": prec_info.get("판례내용", ""),
            "prec_id": str(prec_id)
        }
        signature = self.validator.generate_signature(result_content)
        db_client.cache_set(cache_key, result_content, signature, ttl_days=30)

        self.consecutive_failures = 0
        self.cb.record_success()

        return {
            "status": "Verified",
            "source": "National Law Information Center (DRF)",
            "event": None,
            "content": result_content,
            "signature": signature
        }

    # ────────────────────────────────────────────────────────────────────────
    # PRIVATE: HTTP 실행 + Retry + CB
    # ────────────────────────────────────────────────────────────────────────
    def _execute_request(self, url: str, params: Dict[str, str]) -> Optional[Dict]:
        for attempt in range(1, self.max_retries + 1):
            if not self.cb.is_allowed():
                print(f"🔴 [CB] {self.cb.provider_name} 차단 중.")
                self.consecutive_failures += 1
                return None

            try:
                response = requests.get(url, params=params, timeout=self.timeout_sec)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                self.cb.record_failure()
                wait = self.retry_interval_sec * (2 ** (attempt - 1))
                print(f"🌐 [DRF] 연결 실패 (attempt {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    print(f"   → {wait}s 후 재시도...")
                    time.sleep(wait)

        self.consecutive_failures += 1
        return None

    # ────────────────────────────────────────────────────────────────────────
    # PRIVATE: API 실패 시 캐시 Fallback (007A / 007B 분기)
    # ────────────────────────────────────────────────────────────────────────
    def _handle_api_failure(self) -> Dict[str, Any]:
        """
        캐시가 있고 무결성 통과 → 007A (사용자 동의 후 캐시 반환 가능)
        캐시 없음 → 007B (답변 불가)
        """
        if self.consecutive_failures >= self.max_consecutive_failures:
            event = "LMD-CONST-007B"
            print(f"🚨 [Constitution] {event}: DRF 연속 실패 "
                  f"{self.consecutive_failures}회")
            return {
                "status": "FAIL_CLOSED",
                "event": event,
                "message": "현재 DRF 연결이 불가하고 검증된 캐시도 없습니다. "
                           "답변을 생성할 수 없습니다."
            }

        return {
            "status": "FAIL_CLOSED",
            "event": None,
            "message": "DRF API 응답 실패. 잠시 후 다시 시도해 주세요."
        }

    # ────────────────────────────────────────────────────────────────────────
    # PRIVATE: 날짜 정규화 (DRF 응답용만 AUTO_PAD 허용)
    # ────────────────────────────────────────────────────────────────────────
    def _normalize_date_from_drf(self, raw_date: str) -> Optional[str]:
        if not raw_date:
            return None
        raw_date = str(raw_date).strip()
        match = self._date_normalize_pattern.match(raw_date)
        if not match:
            return None
        year, month, day = match.group(1), match.group(2), match.group(3)
        padded = f"{year}{month.zfill(2)}{day.zfill(2)}"
        if len(padded) == 8 and padded.isdigit():
            return padded
        return None

    # ────────────────────────────────────────────────────────────────────────
    # PRIVATE: 키워드 교차검증
    # ────────────────────────────────────────────────────────────────────────
    def _cross_check_keywords(self, keywords: str, summary: str) -> bool:
        keyword_list = [kw.strip() for kw in keywords.split() if len(kw.strip()) >= 2]
        if not keyword_list:
            return True
        return any(kw in summary for kw in keyword_list)

    # ────────────────────────────────────────────────────────────────────────
    # PRIVATE: 법령 응답 구조화
    # ────────────────────────────────────────────────────────────────────────
    def _wrap_law_response(self, raw: Dict) -> Dict[str, Any]:
        law_list = raw.get("LawSearch", {}).get("Law", [])
        return {
            "status": "Verified" if law_list else "Empty",
            "source": "National Law Information Center (DRF)",
            "content": law_list
        }