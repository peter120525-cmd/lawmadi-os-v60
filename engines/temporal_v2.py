import datetime
from typing import Dict, Any, Optional

class TemporalEngine:
    """
    [Temporal] 타임라인 엔진 v2.0: 행위시 vs 재판시 법령 판정 및 부칙 분석
    """
    def __init__(self, timezone: str = "Asia/Seoul"):
        self.timezone = timezone
        self.current_time = datetime.datetime.now()

    def determine_applicable_law(self, incident_date: str, law_versions: list) -> Dict[str, Any]:
        """
        사건 발생일(incident_date)을 기준으로 적용 가능한 법령 버전을 선정합니다.
        format: YYYY-MM-DD
        """
        target_date = datetime.datetime.strptime(incident_date, "%Y-%m-%d")
        
        applicable_version = None
        for version in law_versions:
            start_date = datetime.datetime.strptime(version['enforcement_date'], "%Y-%m-%d")
            end_date = version.get('expiry_date')
            
            # 종료일이 없는 경우(현재 시행 중) 처리
            end_date_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.datetime.max
            
            if start_date <= target_date <= end_date_dt:
                applicable_version = version
                break
        
        return {
            "is_historical": target_date < self.current_time,
            "incident_date": incident_date,
            "applied_version_id": applicable_version['id'] if applicable_version else "Not Found",
            "law_content": applicable_version
        }

    def analyze_addenda(self, addenda_text: str, query_context: str) -> str:
        """
        부칙(Addenda) 내의 '경과조치' 조항을 정밀 분석합니다.
        """
        # IT 기술적 키워드 추출 (경과조치, 시행일, 유효기간 등)
        keywords = ["경과조치", "종전의 규정", "적용례", "유효기간"]
        found_rules = [line for line in addenda_text.split('\n') if any(k in line for k in keywords)]
        
        if not found_rules:
            return "특별한 경과조치가 발견되지 않아 일반 원칙에 따라 행위시법을 적용합니다."
            
        return " | ".join(found_rules)

    def check_retroactivity(self, old_law: float, new_law: float) -> str:
        """
        [L5] 소급적용 여부 판정 (형벌의 경중 비교 등)
        """
        if new_law > old_law:
            return "신법의 형량이 더 무거우므로 '소급금지의 원칙'에 따라 구법 적용 권장."
        return "신법이 유리하게 개정되었으므로 '신법 우선의 원칙' 검토 필요."
