import hashlib
import re
import json
from typing import Dict, List, Any


class LawmadiValidator:
    """
    [L5] 데이터 무결성 및 검증 엔진
    - 구조적 필드 검사
    - 전체 항목의 식별자 검증 (샘플링 아님)
    - SHA-256 서명 생성/검증 (캐시 무결성에 연결)
    """
    def __init__(self):
        # 사건번호: 4자리 연도 + 법원 구분자(1-2글자) + 번호
        # 실제 법원 구분자: 가, 나, 다, 라, 마, 바, 사, 아, 자, 차, 카, 타, 파, 하 등
        self.case_format = re.compile(r"^\d{4}[가-힣]{1,2}\d+$")
        # 법령 일련번호: 숫자열 (길이 제한 없음, DRF 기준)
        self.law_id_format = re.compile(r"^\d+$")

    # ── 통합 검증 엔트리포인트 ───────────────────────────────────────────
    def validate_all(self, structured_data: Dict[str, Any]) -> bool:
        """
        구조적 무결성 → 식별자 검증 (전체 항목) → 통과/실패 반환
        """
        # 1. 필수 필드 구조 검사
        if not self._check_structure(structured_data):
            print("❌ [Validator] 구조 검증 실패: 필수 필드 누락")
            return False

        # 2. 콘텐츠가 비어있으면 실패
        content = structured_data.get("content", [])
        if not content:
            print("❌ [Validator] 콘텐츠가 비어있습니다.")
            return False

        # 3. 전체 항목의 식별자 검증
        if not self._verify_all_identifiers(content):
            return False

        return True

    # ── 구조 검사 ─────────────────────────────────────────────────────────
    def _check_structure(self, data: Dict) -> bool:
        """내부 표준 구조의 필수 필드가 존재하는지 확인"""
        required_fields = ["status", "content", "source"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            print(f"❌ [Validator] 누락된 필드: {missing}")
            return False
        return True

    # ── 식별자 검증 (전체 항목) ────────────────────────────────────────────
    def _verify_all_identifiers(self, content: List[Any]) -> bool:
        """
        리스트의 모든 항목을 순회하며 법령ID 형식을 검증
        하나라도 실패하면 전체 실패 (FAIL_CLOSED)
        """
        items = content if isinstance(content, list) else [content]
        failed_indices = []

        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                failed_indices.append(idx)
                continue

            law_id = str(item.get("법령일련번호", "")).strip()
            if not law_id or not self.law_id_format.match(law_id):
                failed_indices.append(idx)

        if failed_indices:
            print(f"❌ [Validator] 식별자 검증 실패 항목 인덱스: {failed_indices}")
            return False

        return True

    # ── 사건번호 형식 검증 ─────────────────────────────────────────────────
    def validate_case_number(self, case_number: str) -> bool:
        """사건번호가 국가 표준 형식인지 검증"""
        cleaned = case_number.strip()
        if not self.case_format.match(cleaned):
            print(f"❌ [Validator] 사건번호 형식 오류: '{cleaned}' "
                  f"(예: 2016다234043)")
            return False
        return True

    # ── SHA-256 서명 생성 ──────────────────────────────────────────────────
    def generate_signature(self, data: Any) -> str:
        """
        데이터의 SHA-256 서명을 생성
        캐시 저장 시 함께 저장되어, 후속 무결성 검증에 사용됨
        (LMD-CONST-005 CACHE_INTEGRITY_VIOLATION과 연결)
        """
        data_string = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(data_string.encode()).hexdigest()

    # ── SHA-256 서명 검증 ──────────────────────────────────────────────────
    def verify_signature(self, data: Any, expected_signature: str) -> bool:
        """
        캐시에서 로드한 데이터의 서명이 저장된 서명과 일치하는지 검증
        불일치 시 → LMD-CONST-005 트리거
        """
        computed = self.generate_signature(data)
        if computed != expected_signature:
            print("🚨 [LMD-CONST-005] CACHE_INTEGRITY_VIOLATION: 서명 불일치 감지")
            return False
        return True
