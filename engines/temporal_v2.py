import re
import logging
import datetime
import enum
from typing import Dict, List, Optional, Any

# [IT 기술: 커널 수준 로깅 및 시계열 트레이싱 설정]
logger = logging.getLogger("LawmadiOS.TemporalEngine")

class TemporalMode(enum.Enum):
    """[IT 기술: 시계열 분석 모드 정의]"""
    ACT_TIME = "ACT_TIME"               # 행위시법 (Substantive)
    JUDGMENT_TIME = "JUDGMENT_TIME"     # 재판시법 (Procedural)
    MIXED = "MIXED"                     # 혼재 모드 (Case-specific)
    UNKNOWN = "ASK_USER_CONFIRMATION"   # 사용자 확인 필요

class AddendaParser:
    """
    [L1-TEMPORAL: 통합 시계열 및 부칙 분석 엔진]
    법령의 부칙(Addenda) 분석과 시계열 적용법(Applicable Law) 결정을 통합 수행합니다.
    - LMD-CONST-004: 시계열 논리 위반 방지
    - LMD-CONST-004S: 일몰 조항(Sunset Clause) 감지
    - LMD-CONST-006: 날짜 규격 무결성 강제
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        # [IT 기술: 하드닝된 법률 패턴 엔진]
        self.enforcement_pattern = re.compile(r"이\s?법은\s?(.*?)\s?부터\s?시행한다")
        self.interim_measure_pattern = re.compile(r"경과\s?조치|종전의\s?규정|적용\s?례|특례")
        self.effective_date_pattern = re.compile(r"(\d{4})년\s?(\d{1,2})월\s?(\d{1,2})일")
        self._date_strict_pattern = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
        
        # IT 표준 설정
        self.DATE_STANDARD = "%Y%m%d"
        self.current_time = datetime.datetime.now()
        
        # Sunset Clause 설정 (LMD-CONST-004S)
        self.sunset_detection = self.config.get("sunset_clause_detection", {"enabled": True, "sources": ["expiry_date", "valid_to"]})

    # =========================================================
    # 🛡️ [IT 기술: LMD-CONST-006] 날짜 무결성 검증 (Strict Validation)
    # =========================================================
    def parse_user_date(self, raw_input: str) -> Optional[datetime.datetime]:
        """
        사용자 입력 날짜를 검증합니다. (FIX-1: AUTO_PAD 금지 정책)
        YYYYMMDD 형식만 수용하며, 그 외 형식은 시스템 보호를 위해 REJECT합니다.
        """
        cleaned = str(raw_input).strip().replace("-", "").replace(".", "")

        if not self._date_strict_pattern.match(cleaned):
            logger.error(f"❌ [LMD-CONST-006] 날짜 규격 위반: '{raw_input}' (YYYYMMDD 필수)")
            return None

        try:
            return datetime.datetime.strptime(cleaned, self.DATE_STANDARD)
        except ValueError:
            logger.error(f"❌ [LMD-CONST-006] 논리적 날짜 오류: '{raw_input}'")
            return None

    # =========================================================
    # 📡 [IT 기술: L1-Temporal] 부칙(Addenda) 분석 레이어
    # =========================================================
    def parse_addenda(self, addenda_content: str) -> Dict[str, Any]:
        """비정형 부칙 데이터를 분석하여 시행일 및 경과 규정을 추출합니다."""
        if not addenda_content or not addenda_content.strip():
            return {"enforcement_date": None, "has_interim_measures": False, "specific_clauses": []}

        analysis_result = {
            "enforcement_date": self._extract_effective_date_raw(addenda_content),
            "has_interim_measures": False,
            "specific_clauses": []
        }

        clauses = re.split(r"제\d+조", addenda_content)
        for idx, clause in enumerate(clauses):
            if self.interim_measure_pattern.search(clause):
                analysis_result["has_interim_measures"] = True
                analysis_result["specific_clauses"].append(clause.strip().split(".")[0])

        return analysis_result

    def _extract_effective_date_raw(self, text: str) -> Optional[str]:
        match = self.enforcement_pattern.search(text)
        if match:
            date_match = self.effective_date_pattern.search(match.group(1))
            if date_match:
                return f"{date_match.group(1)}{date_match.group(2).zfill(2)}{date_match.group(3).zfill(2)}"
        return None

    # =========================================================
    # 🚦 [IT 기술: L5] 적용 시점 판정 및 법령 매칭 (Logic Layer)
    # =========================================================
    def determine_applicable_law(
        self,
        incident_date_str: str,
        law_versions: List[Dict[str, Any]],
        mode: str = "ACT_TIME",
        judgment_date_str: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        [IT 기술: Temporal Logic Comparator]
        설정된 모드에 따라 기준일을 결정하고 최적의 법령 버전을 선정합니다.
        """
        # 1. 기준 시점(Reference Date) 확정
        if mode == "ACT_TIME":
            ref_date = self.parse_user_date(incident_date_str)
        elif mode == "JUDGMENT_TIME":
            if not judgment_date_str:
                return {"status": "FAIL", "event": "LMD-CONST-004", "message": "재판시 기준일 누락"}
            ref_date = self.parse_user_date(judgment_date_str)
        elif mode == "MIXED":
            # 재귀 호출을 통한 다중 결과 취합
            return {
                "status": "MIXED_MODE",
                "act_time_result": self.determine_applicable_law(incident_date_str, law_versions, "ACT_TIME"),
                "judgment_time_result": self.determine_applicable_law(incident_date_str, law_versions, "JUDGMENT_TIME", judgment_date_str)
            }
        else:
            return {"status": "FAIL", "message": "UNKNOWN_MODE"}

        if not ref_date:
            return {"status": "FAIL", "event": "LMD-CONST-006", "message": "날짜 파싱 실패"}

        # 2. 법령 버전 매칭 (Start <= Ref <= End)
        applicable_version = self._find_version(ref_date, law_versions)
        
        # 3. [LMD-CONST-004S] 일몰 조항 감지
        sunset_warning = self._check_sunset_clause(applicable_version)

        return {
            "status": "OK",
            "applied_version": applicable_version,
            "reference_date": ref_date.strftime(self.DATE_STANDARD),
            "sunset_warning": sunset_warning
        }

    def _find_version(self, ref_date: datetime.datetime, versions: List[Dict]) -> Optional[Dict]:
        """[IT 기술: Binary Match] 유효 기간 내의 법령 버전을 탐색합니다."""
        for v in versions:
            start = self.parse_user_date(str(v.get("enforcement_date", "")))
            if not start: continue
            
            expiry_raw = v.get("expiry_date") or v.get("valid_to")
            end = self.parse_user_date(str(expiry_raw)) if expiry_raw else datetime.datetime.max
            
            if start <= ref_date <= end:
                return v
        return None

    # =========================================================
    # 🚨 [IT 기술: LMD-CONST-004S] 일몰 조항 감지 (Sunset Alert)
    # =========================================================
    def _check_sunset_clause(self, version: Optional[Dict[str, Any]]) -> Optional[str]:
        """한시법 또는 일몰 조항이 포함된 데이터 패킷을 감지하여 경고를 생성합니다."""
        if not version or not self.sunset_detection.get("enabled"):
            return None

        for field in self.sunset_detection.get("sources", []):
            if version.get(field):
                msg = f"⚠️ [LMD-CONST-004S] 일몰(한시) 적용 감지. 적용 종료일: {version[field]}"
                logger.warning(msg)
                return msg
        return None

    # =========================================================
    # 📊 [IT 기술: 시각화] ASCII 타임라인 렌더링 (UI/UX)
    # =========================================================
    def render_timeline(self, incident: str, enforcement: str, amendment_dates: Optional[List[str]] = None) -> str:
        """REFERENCE_SECTION 출력을 위한 시계열 ASCII 타임라인을 생성합니다."""
        today = self.current_time.strftime(self.DATE_STANDARD)
        tl = [
            f"📅 [사건] {incident}",
            f"   |────▶ [시행] {enforcement}"
        ]
        if amendment_dates:
            for d in amendment_dates:
                tl.append(f"   |── [개정] {d}")
        tl.append(f"   └────────────▶ [오늘] {today} (v50.2.4)")
        return "\n".join(tl)