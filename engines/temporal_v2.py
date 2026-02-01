import datetime
import re
from typing import Dict, Any, Optional, List


class TemporalEngine:
    """
    [Temporal] 타임라인 엔진 v2.0
    - 행위시법(ACT_TIME) / 재판시법(JUDGMENT_TIME) / 혼재(MIXED) 모드 지원
    - 날짜 내부 표준: YYYYMMDD (config.temporal_engine_settings.date_internal_standard)
    - 사용자 입력 날짜는 REJECT → 올바른 형식 요청 (FIX-1)
    - Sunset Clause 감지 및 경고 (LMD-CONST-004S)
    """
    def __init__(self, config: Dict[str, Any]):
        self.timezone: str = config.get("default_timezone", "Asia/Seoul")
        self.temporal_modes: Dict[str, str] = config.get("temporal_modes", {})
        self.sunset_detection: Dict[str, Any] = config.get("sunset_clause_detection", {})
        self.current_time = datetime.datetime.now()

        # 날짜 파싱: 내부 표준 YYYYMMDD만 수용
        self._date_pattern = re.compile(r"^(\d{4})(\d{2})(\d{2})$")

    # ── 날짜 검증 및 파싱 (사용자 입력용 — AUTO_PAD 금지) ──────────────
    def parse_user_date(self, raw_input: str) -> Optional[datetime.datetime]:
        """
        사용자 입력 날짜 검증
        YYYYMMDD 형식만 수용 — 그 외는 REJECT (FIX-1: 사용자 입력 AUTO_PAD 금지)
        """
        cleaned = str(raw_input).strip().replace("-", "").replace(".", "")

        if not self._date_pattern.match(cleaned):
            print(f"❌ [Temporal] 날짜 형식 오류: '{raw_input}'. "
                  f"'YYYYMMDD' 형식으로 입력해 주세요. (예: 20251115)")
            return None  # REJECT → LMD-CONST-006

        year = int(cleaned[0:4])
        month = int(cleaned[4:6])
        day = int(cleaned[6:8])

        try:
            return datetime.datetime(year, month, day)
        except ValueError:
            print(f"❌ [Temporal] 유효하지 않은 날짜: '{raw_input}' (LMD-CONST-006)")
            return None

    # ── 적용 모드 판별 ────────────────────────────────────────────────────
    def determine_temporal_mode(self, category: str) -> str:
        """
        사건 카테고리에 따라 적용 시점 모드를 결정
        SUBSTANTIVE_RIGHTS → ACT_TIME
        PROCEDURE_EXECUTION → JUDGMENT_TIME
        UNKNOWN → ASK_USER_CONFIRMATION
        """
        mode = self.temporal_modes.get(category)
        if mode is None:
            # 카테고리가 정의되지 않은 경우 → UNKNOWN
            mode = self.temporal_modes.get("UNKNOWN", "ASK_USER_CONFIRMATION")

        if mode == "ASK_USER_CONFIRMATION":
            print("\n❓ [Temporal] 사건 발생일(또는 계약일)과, "
                  "현재 진행 단계(소송/집행 등)를 알려주시면 "
                  "시점 기준(행위시/재판시)을 더 안전하게 확정할 수 있어요.")

        return mode

    # ── 적용 가능한 법령 버전 결정 ─────────────────────────────────────────
    def determine_applicable_law(
        self,
        target_date_str: str,
        law_versions: List[Dict[str, Any]],
        temporal_mode: str = "ACT_TIME",
        judgment_date_str: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        temporal_mode에 따라 적용 기준일을 결정한 후, 해당 시점의 법령 버전을 선정

        ACT_TIME: incident_date 기준
        JUDGMENT_TIME: judgment_date 기준 (재판/집행 시점)
        MIXED: 둘 다 반환하여 사용자 선택 유도
        """
        # 기준일 결정
        if temporal_mode == "ACT_TIME":
            reference_date = self.parse_user_date(target_date_str)
            if reference_date is None:
                return {"status": "FAIL", "event": "LMD-CONST-006",
                        "message": "행위시법 기준일 파싱 실패. YYYYMMDD 형식으로 입력해 주세요."}

        elif temporal_mode == "JUDGMENT_TIME":
            if not judgment_date_str:
                return {"status": "FAIL", "event": "LMD-CONST-004",
                        "message": "재판시법 모드에서는 '현재 진행 단계의 날짜'가 필요합니다."}
            reference_date = self.parse_user_date(judgment_date_str)
            if reference_date is None:
                return {"status": "FAIL", "event": "LMD-CONST-006",
                        "message": "재판시법 기준일 파싱 실패. YYYYMMDD 형식으로 입력해 주세요."}

        elif temporal_mode == "MIXED":
            # 두 기준일 모두 사용하여 각각의 적용 법령을 반환
            act_result = self.determine_applicable_law(target_date_str, law_versions, "ACT_TIME")
            judgment_result = self.determine_applicable_law(
                target_date_str, law_versions, "JUDGMENT_TIME", judgment_date_str
            )
            return {
                "status": "MIXED_MODE",
                "message": "행위시법과 재판시법이 혼재됩니다. 아래 두 결과를 비교하여 적용해 주세요.",
                "act_time_result": act_result,
                "judgment_time_result": judgment_result
            }

        else:
            return {"status": "FAIL", "event": "LMD-CONST-004",
                    "message": f"알 수 없는 temporal_mode: '{temporal_mode}'"}

        # 법령 버전 매칭
        applicable = self._find_applicable_version(reference_date, law_versions)

        # Sunset Clause 감지
        sunset_warning = self._check_sunset_clause(applicable)

        return {
            "status": "OK",
            "temporal_mode": temporal_mode,
            "reference_date": reference_date.strftime("%Y%m%d"),
            "is_historical": reference_date < self.current_time,
            "applied_version": applicable,
            "sunset_warning": sunset_warning
        }

    # ── 법령 버전 매칭 내부 로직 ──────────────────────────────────────────
    def _find_applicable_version(
        self,
        reference_date: datetime.datetime,
        law_versions: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """enforcement_date ≤ reference_date ≤ expiry_date인 버전 탐색"""
        for version in law_versions:
            start = self.parse_user_date(str(version.get("enforcement_date", "")))
            if start is None:
                continue

            expiry_raw = version.get("expiry_date")
            end = self.parse_user_date(str(expiry_raw)) if expiry_raw else datetime.datetime.max

            if end is None:
                end = datetime.datetime.max

            if start <= reference_date <= end:
                return version

        return None

    # ── Sunset Clause 감지 (LMD-CONST-004S) ──────────────────────────────
    def _check_sunset_clause(self, version: Optional[Dict[str, Any]]) -> Optional[str]:
        """
        DRF 메타데이터의 expiry_date 또는 valid_to가 존재하면 일몰 경고 발생
        config.temporal_engine_settings.sunset_clause_detection.sources 참조
        """
        if not version or not self.sunset_detection.get("enabled", False):
            return None

        detection_sources = self.sunset_detection.get("sources", [])
        expiry_fields = {
            "DRF_METADATA_EXPIRY_DATE": "expiry_date",
            "DRF_METADATA_VALID_TO": "valid_to"
        }

        for source in detection_sources:
            field = expiry_fields.get(source)
            if field and version.get(field):
                warning_msg = (
                    f"⚠️ [LMD-CONST-004S] 한시(일몰) 적용 가능성이 있어요. "
                    f"적용 종료일: {version[field]}. 유효기간을 다시 확인해 주세요."
                )
                print(warning_msg)
                return warning_msg

        return None

    # ── ASCII 타임라인 시각화 ─────────────────────────────────────────────
    def render_timeline(
        self,
        incident_date_str: str,
        enforcement_date_str: str,
        amendment_dates: Optional[List[str]] = None,
        expiry_date_str: Optional[str] = None
    ) -> str:
        """
        REFERENCE_SECTION용 ASCII 타임라인 렌더링
        config.TEMPORAL_ENGINE.timeline_visualizer 참조
        """
        today_str = self.current_time.strftime("%Y%m%d")
        parts = []

        parts.append(f"[사건] {incident_date_str}")
        parts.append("|----| ")
        parts.append(f"[시행] {enforcement_date_str}")

        if amendment_dates:
            for ad in amendment_dates:
                parts.append(f" |--| [개정] {ad}")

        if expiry_date_str:
            parts.append(f" |--| [일몰] {expiry_date_str}")

        parts.append(f" |----------| [오늘] {today_str}")

        return "".join(parts)
