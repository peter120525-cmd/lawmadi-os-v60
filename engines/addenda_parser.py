import re
from typing import Dict, List, Optional, Any


class AddendaParser:
    """
    [L1-Temporal] 부칙 파서: 법 개정 시 경과 규정 및 시행 시점 정밀 분석
    날짜 출력 형식: YYYYMMDD (config.temporal_engine_settings.date_internal_standard)
    """
    def __init__(self):
        self.enforcement_pattern = re.compile(r"이 법은 (.*?)부터 시행한다")
        self.interim_measure_pattern = re.compile(r"경과조치|종전의 규정|적용례")
        self.effective_date_pattern = re.compile(r"(\d{4})년 (\d{1,2})월 (\d{1,2})일")

    def parse_addenda(self, addenda_content: str) -> Dict[str, Any]:
        """
        부칙 전문을 분석하여 시행일 및 경과 규정 리스트를 반환합니다.
        """
        analysis_result: Dict[str, Any] = {
            "enforcement_date": self._extract_effective_date(addenda_content),
            "has_interim_measures": False,
            "specific_clauses": []
        }

        clauses = addenda_content.split("제")
        for clause in clauses:
            if self.interim_measure_pattern.search(clause):
                analysis_result["has_interim_measures"] = True
                analysis_result["specific_clauses"].append(self._summarize_clause(clause))

        return analysis_result

    def _extract_effective_date(self, text: str) -> Optional[str]:
        """
        '이 법은 ~부터 시행한다' 문구에서 날짜 추출
        출력 형식: YYYYMMDD (내부 표준)
        """
        match = self.enforcement_pattern.search(text)
        if match:
            date_match = self.effective_date_pattern.search(match.group(1))
            if date_match:
                year = date_match.group(1)
                month = date_match.group(2).zfill(2)
                day = date_match.group(3).zfill(2)
                return f"{year}{month}{day}"  # YYYYMMDD
        return None

    def _summarize_clause(self, clause_text: str) -> str:
        """경과 조치 핵심 요약 (첫 문장 추출)"""
        clean_text = clause_text.strip().replace("\n", " ")
        summary = clean_text.split(".")[0]
        return f"제{summary}"

    def evaluate_retroactive_applicability(self, incident_date: str, addenda_info: Dict[str, Any]) -> str:
        """
        사건일과 부칙 시행일을 비교하여 소급 적용 여부 판정
        날짜 비교: YYYYMMDD 문자열 비교 (사전순 == 시간순)
        """
        enforcement = addenda_info.get("enforcement_date")
        if not enforcement:
            return "UNKNOWN_ENFORCEMENT_DATE"

        # 사건일도 YYYYMMDD 형식이어야 비교 가능
        if len(incident_date) != 8 or not incident_date.isdigit():
            return "INVALID_INCIDENT_DATE_FORMAT"

        if incident_date < enforcement:
            if addenda_info.get("has_interim_measures", False):
                return "APPLY_OLD_LAW_WITH_INTERIM_MEASURES"
            return "APPLY_OLD_LAW_PRINCIPLE"

        return "APPLY_NEW_LAW"
