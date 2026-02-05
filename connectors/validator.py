import hashlib
import re
import json
import logging
from typing import Dict, List, Any, Optional

# [IT 기술: 시스템 표준 로깅 계층 설정]
logger = logging.getLogger("LawmadiOS.Validator")

class LawmadiValidator:
    """
    [L5: DATA_INTEGRITY_ENGINE]
    Lawmadi OS의 데이터 무결성 및 보안 검증을 수행하는 하드닝 엔진입니다.
    - LMD-CONST-005: 캐시 무결성 서명 검증
    - LMD-CONST-007: 구조적 패킷 검증
    - LMD-CONST-009: 식별자 규격 검증
    """
    def __init__(self):
        # 사건번호: 4자리 연도 + 법원 구분자 + 번호 (공백 허용 유연성 확보)
        self.case_format = re.compile(r"^\d{4}\s*[가-힣]{1,2}\s*\d+$")
        # 법령 식별자: 숫자형 문자열 규격 강제
        self.law_id_format = re.compile(r"^\d+$")

    # ── [L5] 통합 검증 파이프라인 ──────────────────────────────────────────
    def validate_all(self, structured_data: Dict[str, Any]) -> bool:
        """
        [IT 기술: Multi-Stage Validation]
        구조 검사 -> 콘텐츠 유효성 -> 식별자 무결성을 단계별로 검증합니다.
        하나라도 실패 시 'Fail-Closed' 원칙에 따라 즉시 차단합니다.
        """
        # 1. 구조적 무결성 검사 (Required Fields)
        if not self._check_structure(structured_data):
            logger.error("❌ [LMD-CONST-007] 구조 검증 실패: 필수 메타데이터 누락")
            return False

        # 2. 페이로드 존재 확인
        content = structured_data.get("content")
        if not content:
            logger.warning("⚠️ [LMD-CONST-007] 유효 페이로드 부재: 빈 데이터 수신")
            return False

        # 3. 데이터 식별자 전수 검증 (Sampling 아님)
        if not self._verify_all_identifiers(content):
            return False

        return True

    # ── [L5] 구조적 무결성 검사 ───────────────────────────────────────────
    def _check_structure(self, data: Dict) -> bool:
        """내부 통신 규격(Packet Standard) 준수 여부 확인"""
        required_fields = ["status", "content", "source"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            logger.error(f"❌ 필수 필드 누락: {missing}")
            return False
        return True

    # ── [L5] 식별자 무결성 전수 검증 ────────────────────────────────────────
    def _verify_all_identifiers(self, content: Any) -> bool:
        """
        수신된 모든 항목의 ID 규격을 검증하여 데이터 오염을 방지합니다.
        (LMD-CONST-009 식별자 보안 정책 준수)
        """
        items = content if isinstance(content, list) else [content]
        
        # IT 기술: DRF API의 다양한 키 명칭을 수용하도록 매핑 테이블 구성
        id_keys = ["법령일련번호", "법령ID", "ID", "id"]
        
        failed_indices = []

        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                failed_indices.append(idx)
                continue

            # 유효한 키를 찾아서 검증
            found_id = None
            for key in id_keys:
                if key in item:
                    found_id = str(item[key]).strip()
                    break
            
            if not found_id or not self.law_id_format.match(found_id):
                failed_indices.append(idx)

        if failed_indices:
            logger.error(f"❌ [LMD-CONST-009] 식별자 무결성 위반 발견 (Index: {failed_indices})")
            return False

        return True

    # ── [L5] 판례 사건번호 형식 검증 ────────────────────────────────────────
    def validate_case_number(self, case_number: str) -> bool:
        """사건번호가 국가 표준 사법 형식인지 검증합니다."""
        if not case_number: return False
        
        cleaned = case_number.strip()
        if not self.case_format.match(cleaned):
            logger.error(f"❌ [L5] 사건번호 규격 오류: '{cleaned}' (정상 예: 2023다123456)")
            return False
        return True

    # ── [LMD-CONST-005] SHA-256 무결성 서명 엔진 ───────────────────────────
    def generate_signature(self, data: Any) -> str:
        """
        [IT 기술: Cryptographic Integrity]
        데이터 패킷의 고유 지문을 생성하여 캐시 변조를 원천 차단합니다.
        """
        try:
            # IT 기술: 키 순서 고정 및 유니코드 안전 직렬화 적용
            data_string = json.dumps(data, sort_keys=True, ensure_ascii=False)
            return hashlib.sha256(data_string.encode('utf-8')).hexdigest()
        except Exception as e:
            logger.error(f"🚨 서명 생성 실패 (Serialization Error): {e}")
            return "SIGNATURE_ERROR"

    def verify_signature(self, data: Any, expected_signature: str) -> bool:
        """
        [LMD-CONST-005] 저장된 서명과 현재 데이터의 지문을 대조합니다.
        불일치 시 외부 침입 또는 데이터 오염으로 간주하고 처리를 거부합니다.
        """
        computed = self.generate_signature(data)
        if computed != expected_signature:
            logger.critical("🚨 [LMD-CONST-005] CACHE_INTEGRITY_VIOLATION: 데이터 무결성 파괴 감지")
            return False
        return True