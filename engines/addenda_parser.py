import re
from typing import Dict, List, Optional

class AddendaParser:
    """
    [L1-Temporal] 부칙 파서: 법 개정 시 경과 규정 및 시행 시점 정밀 분석
    """
    def __init__(self):
        # 부칙 내 핵심 조항 감지를 위한 정규표현식
        self.enforcement_pattern = re.compile(r"이 법은 (.*?)부터 시행한다")
        self.interim_measure_pattern = re.compile(r"경과조치|종전의 규정|적용례")
        self.effective_date_pattern = re.compile(r"(\d{4})년 (\d{1,2})월 (\d{1,2})일")

    def parse_addenda(self, addenda_content: str) -> Dict[str, Any]:
        """
        부칙 전문을 분석하여 시행일 및 경과 규정 리스트를 반환합니다.
        """
        analysis_result = {
            "enforcement_date": self._extract_effective_date(addenda_content),
            "has_interim_measures": False,
            "specific_clauses": []
        }

        # 조 단위로 분리하여 분석
        clauses = addenda_content.split("제")
        for clause in clauses:
            if self.interim_measure_pattern.search(clause):
                analysis_result["has_interim_measures"] = True
                analysis_result["specific_clauses"].append(self._summarize_clause(clause))

        return analysis_result

    def _extract_effective_date(self, text: str) -> Optional[str]:
        """
        '이 법은 ~부터 시행한다' 문구에서 날짜 데이터 추출
        """
        match = self.enforcement_pattern.search(text)
        if match:
            date_match = self.effective_date_pattern.search(match.group(1))
            if date_match:
                return f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
        return None

    def _summarize_clause(self, clause_text: str) -> str:
        """
        IT 가공을 통한 핵심 경과 조치 요약
        """
        # 불필요한 공백 제거 및 첫 문장 추출
        clean_text = clause_text.strip().replace("\n", " ")
        summary = clean_text.split(".")[0]
        return f"제{summary}"

    def evaluate_retroactive_applicability(self, incident_date: str, addenda_info: Dict) -> str:
        """
        사건일과 부칙 정보를 비교하여 소급 적용 여부를 기술적으로 판정
        """
        if not addenda_info["enforcement_date"]:
            return "UNKNOWN_ENFORCEMENT_DATE"

        if incident_date < addenda_info["enforcement_date"]:
            if addenda_info["has_interim_measures"]:
                return "APPLY_OLD_LAW_WITH_INTERIM_MEASURES" # 경과조치에 따른 구법 적용
            return "APPLY_OLD_LAW_PRINCIPLE" # 일반적인 구법 적용
            
        return "APPLY_NEW_LAW" # 신법 적용
