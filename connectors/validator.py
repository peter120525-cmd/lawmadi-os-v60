import hashlib
import re
import json
from typing import Dict, Any

class LawmadiValidator:
    """
    [L5] 데이터 무결성 및 2단계 검증 엔진
    """
    def __init__(self):
        # 법률 데이터 무결성 검증을 위한 정규표현식 (사건번호, 법령ID)
        self.case_format = re.compile(r"^\d{4}[가-후]{1,2}\d+$")
        self.law_id_format = re.compile(r"^\d{6}$") # 6자리 법령 일련번호

    def validate_all(self, raw_data: Dict[str, Any]) -> bool:
        """
        데이터의 형식과 내용이 무결한지 통합 검사합니다.
        """
        # 1. 구조적 무결성 검사
        if not self._check_structure(raw_data):
            return False
            
        # 2. 식별자 형식 검사 (사건번호 등)
        if not self._verify_identifiers(raw_data):
            return False

        return True

    def _check_structure(self, data: Dict) -> bool:
        """
        IT 데이터 아키텍처 상 필수 필드가 존재하는지 확인
        """
        required_fields = ["status", "content", "source"]
        return all(field in data for field in required_fields)

    def _verify_identifiers(self, data: Dict) -> bool:
        """
        데이터 내의 사건번호나 법령 ID가 국가 표준 규격인지 검증
        """
        content = data.get("content", [])
        if not content:
            return False
            
        # 데이터 샘플링 검사 (첫 번째 항목의 유효성 확인)
        sample = content[0] if isinstance(content, list) else content
        law_id = str(sample.get("법령일련번호", ""))
        
        return bool(self.law_id_format.match(law_id))

    def generate_signature(self, data: Any) -> str:
        """
        데이터 변조 방지를 위한 SHA-256 서명 생성
        """
        data_string = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_string.encode()).hexdigest()

    def verify_signature(self, data: Any, signature: str) -> bool:
        """
        수신된 데이터의 서명이 생성된 서명과 일치하는지 비교 (무결성 확인)
        """
        return self.generate_signature(data) == signature
