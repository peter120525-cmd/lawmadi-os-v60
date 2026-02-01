import requests
import time
import re
from typing import Dict, Any, Optional
from connectors.validator import LawmadiValidator


class DRFConnector:
    """
    [L3-L5] 국가법령정보센터(DRF) API 통신 및 7단계 검증
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
        self.endpoints = endpoints          # {"law_search": "...", "law_service": "..."}
        self.cb = cb                        # Per-provider CircuitBreaker
        self.policy = api_failure_policy

        self.max_retries: int = self.policy.get("max_retries", 5)
        self.retry_interval_sec: int = self.policy.get("retry_interval_sec", 60)
        self.max_consecutive_failures: int = self.policy.get("max_consecutive_failures", 5)

        self.consecutive_failures = 0
        self.validator = LawmadiValidator()

        # 날짜 정규화: DRF 응답용만 AUTO_PAD 허용
        self._date_normalize_pattern = re.compile(r"^(\d{4})[.\-]?(\d{1,2})[.\-]?(\d{1,2})$")

    # ────────────────────────────────────────────────────────────────────────
    # PUBLIC: 법령 검색 (target=law)
    # ────────────────────────────────────────────────────────────────────────
    def fetch_verified_law(self, query: str) -> Dict[str, Any]:
        """법령 검색 후 구조적 검증까지 수행"""
        raw = self._execute_request(
            url=self.endpoints["law_search"],
            params={"OC": self.api_key, "target": "law", "type": "json", "query": query}
        )
        if raw is None:
            return self._handle_api_failure()

        # 구조적 검증
        structured = self._wrap_law_response(raw)
        if not self.validator.validate_all(structured):
            return {"status": "FAIL_CLOSED", "message": "법령 데이터 무결성 검증 실패 (LMD-CONST-005)"}

        # 서명 생성 및 캐시에 저장 가능한 형태로 반환
        structured["signature"] = self.validator.generate_signature(structured["content"])
        self.consecutive_failures = 0
        self.cb.record_success()
        return structured

    # ────────────────────────────────────────────────────────────────────────
    # PUBLIC: 판례 검증 (7단계 PRECEDENT_VERIFICATION_PROTOCOL)
    # ────────────────────────────────────────────────────────────────────────
    def fetch_verified_precedent(self, case_number: str, keywords: str = "") -> Dict[str, Any]:
        """
        7단계 검증 플로:
        1. SEARCH_PRECEDENT_LIST_BY_CASE_NUMBER
        2. EXTRACT_DRF_PREC_ID_FROM_LIST
        3. FETCH_PRECEDENT_BODY_BY_DRF_PREC_ID
        4. NORMALIZE_DECISION_DATE
        5. VALIDATE_CASE_NUMBER_EXACT_MATCH
        6. CROSS_CHECK_KEYWORDS_WITH_SUMMARY
        7. ON_MISMATCH → FAIL_CLOSED
        """
        # [1단계] 사건번호로 판례 목록 검색
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
                    "message": "사건번호가 정확히 일치하는 판례가 없습니다. "
                               "예: '2016다234043 유치권방해금지' 형식으로 입력해 주세요."}

        # [3단계] 판례 본문 조회
        body_response = self._execute_request(
            url=self.endpoints["law_service"],
            params={"OC": self.api_key, "target": "prec", "type": "json", "ID": str(prec_id)}
        )
        if body_response is None:
            return self._handle_api_failure()

        prec_info = body_response.get("PrecInfo", {})

        # [4단계] 선고일자 정규화 (DRF 응답이므로 AUTO_PAD 허용)
        raw_date = str(prec_info.get("선고일자", ""))
        normalized_date = self._normalize_date_from_drf(raw_date)
        if normalized_date is None:
            return {"status": "FAIL_CLOSED", "event": "LMD-CONST-006",
                    "message": f"선고일자 정규화 실패: '{raw_date}' (LMD-CONST-006)"}

        # [5단계] 사건번호 EXACT MATCH 검증
        body_case_number = str(prec_info.get("사건번호", "")).strip()
        if body_case_number != case_number.strip():
            return {"status": "FAIL_CLOSED", "event": "LMD-CONST-006",
                    "message": f"사건번호 불일치: 검색='{case_number}', 본문='{body_case_number}'"}

        # [6단계] 키워드와 판결요지 교차검증
        if keywords:
            summary = str(prec_info.get("판결요지", ""))
            if not self._cross_check_keywords(keywords, summary):
                return {"status": "FAIL_CLOSED", "event": "LMD-CONST-006",
                        "message": "키워드와 판결요지가 일치하지 않습니다. 사건번호를 다시 확인해 주세요."}

        # [7단계] 검증 완료 — 구조화된 응답 반환
        self.consecutive_failures = 0
        self.cb.record_success()

        return {
            "status": "Verified",
            "source": "National Law Information Center (DRF)",
            "event": None,
            "content": {
                "case_number": body_case_number,
                "decision_date": normalized_date,
                "summary": prec_info.get("판결요지", ""),
                "full_text": prec_info.get("판례내용", ""),
                "prec_id": str(prec_id)
            },
            "signature": self.validator.generate_signature(prec_info)
        }

    # ────────────────────────────────────────────────────────────────────────
    # PRIVATE: HTTP 실행 + Retry + CB 통합
    # ────────────────────────────────────────────────────────────────────────
    def _execute_request(self, url: str, params: Dict[str, str]) -> Optional[Dict]:
        """
        Retry 루프 + Exponential Backoff + Circuit Breaker 연동
        """
        for attempt in range(1, self.max_retries + 1):
            # CB가 차단 중이면 호출 불가
            if not self.cb.is_allowed():
                print(f"🔴 [CB] {self.cb.provider_name} 차단 중. 호출 불가.")
                self.consecutive_failures += 1
                return None

            try:
                response = requests.get(url, params=params, timeout=self.timeout_sec)
                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                self.cb.record_failure()
                wait = self.retry_interval_sec * (2 ** (attempt - 1))  # Exponential backoff
                print(f"🌐 [DRF] 연결 실패 (attempt {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    print(f"   → {wait}s 후 재시도...")
                    time.sleep(wait)

        # 모든 재시도 소진
        self.consecutive_failures += 1
        return None

    # ────────────────────────────────────────────────────────────────────────
    # PRIVATE: API 실패 시 Constitution Event 발행
    # ────────────────────────────────────────────────────────────────────────
    def _handle_api_failure(self) -> Dict[str, Any]:
        """
        연속 실패 횟수가 임계값을 넘으면 Constitution Event 발행
        007A (검증된 캐시 있음) vs 007B (캐시 없음) 분기
        """
        if self.consecutive_failures >= self.max_consecutive_failures:
            # TODO: 캐시 존재 여부를 실제로 확인하여 007A/007B 분기
            # 현재는 캐시 미구현이므로 007B로 기본
            event = "LMD-CONST-007B"
            print(f"🚨 [Constitution] {event} 발행: DRF 연속 실패 "
                  f"{self.consecutive_failures}회 (임계값: {self.max_consecutive_failures})")
            return {
                "status": "FAIL_CLOSED",
                "event": event,
                "message": "현재 DRF 연결/검증이 불가하고 검증된 캐시도 없어 법률 근거 섹션을 제공할 수 없습니다. "
                           "참고 정보(REFERENCE)만 제공 가능합니다."
            }

        return {
            "status": "FAIL_CLOSED",
            "event": None,
            "message": "DRF API 응답 실패. 잠시 후 다시 시도해 주세요."
        }

    # ────────────────────────────────────────────────────────────────────────
    # PRIVATE: 날짜 정규화 (DRF 응답용만)
    # ────────────────────────────────────────────────────────────────────────
    def _normalize_date_from_drf(self, raw_date: str) -> Optional[str]:
        """
        DRF 응답에서 오는 날짜만 AUTO_PAD 허용 (FIX-1)
        출력 형식: YYYYMMDD (config.temporal_engine_settings.date_internal_standard)
        """
        if not raw_date:
            return None

        # int로 온 경우 문자열로 변환
        raw_date = str(raw_date).strip()

        match = self._date_normalize_pattern.match(raw_date)
        if not match:
            return None

        year, month, day = match.group(1), match.group(2), match.group(3)

        # AUTO_PAD: 월/일이 1자리면 0으로 패딩 (DRF 응답용만 허용)
        padded = f"{year}{month.zfill(2)}{day.zfill(2)}"

        # 최종 검증: 8자리 숫자
        if len(padded) == 8 and padded.isdigit():
            return padded

        return None  # FAIL_CLOSED (LMD-CONST-006)

    # ────────────────────────────────────────────────────────────────────────
    # PRIVATE: 키워드 교차검증
    # ────────────────────────────────────────────────────────────────────────
    def _cross_check_keywords(self, keywords: str, summary: str) -> bool:
        """사용자 키워드가 판결요지에 포함되는지 확인"""
        keyword_list = [kw.strip() for kw in keywords.split() if len(kw.strip()) >= 2]
        if not keyword_list:
            return True  # 키워드가 없으면 검증 통과
        return any(kw in summary for kw in keyword_list)

    # ────────────────────────────────────────────────────────────────────────
    # PRIVATE: 법령 응답 구조화
    # ────────────────────────────────────────────────────────────────────────
    def _wrap_law_response(self, raw: Dict) -> Dict[str, Any]:
        """DRF 법령 응답을 내부 표준 구조로 변환"""
        law_list = raw.get("LawSearch", {}).get("Law", [])
        return {
            "status": "Verified" if law_list else "Empty",
            "source": "National Law Information Center (DRF)",
            "content": law_list
        }
