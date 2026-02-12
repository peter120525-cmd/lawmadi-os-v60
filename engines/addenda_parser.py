import re
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

# [IT 기술: 커널 수준 로깅 및 시계열 트레이싱 설정]
logger = logging.getLogger("LawmadiOS.AddendaParser")

class AddendaParser:
    """
    [L1-TEMPORAL: 시계열 법리 분석 엔진]
    법령 개정 시 부칙(Addenda)에 명시된 시행 시점, 경과 조치, 소급 적용 여부를 
    결정론적 알고리즘으로 분석하여 현행법 유효성을 판정합니다.
    """
    def __init__(self):
        # [IT 기술: 하드닝된 법률 패턴 엔진]
        # 시행일 추출: '이 법은 ... 부터 시행한다' 패턴 정밀 매칭
        self.enforcement_pattern = re.compile(r"이\s?법은\s?(.*?)\s?부터\s?시행한다")
        # 경과 조치 및 적용례 감지 (LMD-CONST 준수 여부 판단 근거)
        self.interim_measure_pattern = re.compile(r"경과\s?조치|종전의\s?규정|적용\s?례|특례")
        # 날짜 표준화 패턴 (YYYY년 MM월 DD일)
        self.effective_date_pattern = re.compile(r"(\d{4})년\s?(\d{1,2})월\s?(\d{1,2})일")
        
        # IT 표준: 내부 데이터 표준 포맷 (ISO 8601 준용)
        self.DATE_STANDARD = "%Y%m%d"

    def parse_addenda(self, addenda_content: str) -> Dict[str, Any]:
        """
        [IT 기술: Structural Transition Analysis]
        비정형 부칙 데이터를 분석하여 시행일 및 계층적 경과 규정 리스트를 반환합니다.
        """
        if not addenda_content or not addenda_content.strip():
            logger.warning("⚠️ [L1-Temporal] 부칙 데이터 부재 - 분석 스킵")
            return self._generate_empty_result()

        analysis_result: Dict[str, Any] = {
            "enforcement_date": self._extract_effective_date(addenda_content),
            "has_interim_measures": False,
            "specific_clauses": [],
            "integrity_status": "VERIFIED",
            "analysis_version": "v50.2.4-HARDENED"
        }

        # 조 단위 분리 (IT 기술: 계층적 파싱)
        clauses = re.split(r"제\d+조", addenda_content)
        for idx, clause in enumerate(clauses):
            if not clause.strip(): continue
            
            if self.interim_measure_pattern.search(clause):
                analysis_result["has_interim_measures"] = True
                analysis_result["specific_clauses"].append({
                    "id": idx,
                    "summary": self._summarize_clause(clause),
                    "type": "INTERIM_MEASURE"
                })

        logger.info(f"✅ [L1-Temporal] 부칙 분석 완료 (시행일: {analysis_result['enforcement_date']})")
        return analysis_result

    def _extract_effective_date(self, text: str) -> Optional[str]:
        """
        [IT 기술: Date Normalization Pipeline]
        자연어 날짜를 YYYYMMDD 내부 표준 규격으로 정규화합니다.
        """
        match = self.enforcement_pattern.search(text)
        if match:
            date_match = self.effective_date_pattern.search(match.group(1))
            if date_match:
                try:
                    year = date_match.group(1)
                    month = date_match.group(2).zfill(2)
                    day = date_match.group(3).zfill(2)
                    candidate = f"{year}{month}{day}"
                    # 날짜 유효성 최종 검증 (IT 기술: Semantic Validation)
                    datetime.strptime(candidate, self.DATE_STANDARD)
                    return candidate
                except ValueError:
                    logger.error(f"🚨 [L1-Temporal] 잘못된 날짜 형식 감지: {date_match.groups()}")
        return None

    def _summarize_clause(self, clause_text: str) -> str:
        """[IT 기술: Text Minimization] 경과 조치의 핵심 법리 문장 추출"""
        clean_text = clause_text.strip().replace("\n", " ")
        # 첫 번째 마침표까지만 추출하여 데이터 노이즈 제거
        summary = clean_text.split(".")[0]
        return summary[:200] # 데이터 오버플로우 방지 (Truncation)

    def evaluate_retroactive_applicability(self, incident_date: str, addenda_info: Dict[str, Any]) -> str:
        """
        [IT 기술: Temporal Logic Comparator]
        사건 발생 시점과 법령 시행 시점을 비교하여 소급 적용 프로토콜을 결정합니다.
        """
        enforcement = addenda_info.get("enforcement_date")
        
        # [Fail-Closed] 시행일을 확정할 수 없는 경우 안전하게 이전 법령 적용 원칙 고수
        if not enforcement:
            return "UNKNOWN_ENFORCEMENT_FALLBACK_TO_OLD"

        # 입력 데이터 규격 검증 (IT 보안: Input Validation)
        if not incident_date or len(incident_date) != 8 or not incident_date.isdigit():
            logger.error(f"🚨 [L1-Temporal] 유효하지 않은 사건일 포맷: {incident_date}")
            return "INVALID_INCIDENT_DATE"

        # 시간순 비교 (문자열 비교는 YYYYMMDD 규격에서 산술 비교와 동일한 성능 확보)
        if incident_date < enforcement:
            if addenda_info.get("has_interim_measures", False):
                logger.info("🚦 [Temporal] 구법 적용 (경과 조치 존재 확인)")
                return "APPLY_OLD_LAW_WITH_INTERIM_MEASURES"
            return "APPLY_OLD_LAW_PRINCIPLE"

        logger.info("🚦 [Temporal] 신법 적용 (시행일 이후 사건)")
        return "APPLY_NEW_LAW"

    def _generate_empty_result(self) -> Dict[str, Any]:
        """[IT 기술: Zero-Fill Policy] 빈 데이터 수신 시 표준 객체 반환"""
        return {
            "enforcement_date": None,
            "has_interim_measures": False,
            "specific_clauses": [],
            "integrity_status": "EMPTY_INPUT"
        }