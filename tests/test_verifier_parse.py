"""Verifier JSON 파싱 복구 테스트"""
import sys
from unittest.mock import MagicMock

# google.genai 모듈 mock (로컬에 미설치)
mock_genai = MagicMock()
sys.modules["google"] = MagicMock()
sys.modules["google.genai"] = mock_genai
sys.modules["google.genai.types"] = MagicMock()

import pytest
from engines.response_verifier import ResponseVerifier


@pytest.fixture
def verifier():
    v = ResponseVerifier.__new__(ResponseVerifier)
    v.enabled = False
    return v


class TestExtractJsonBlock:
    def test_plain_json(self, verifier):
        text = '{"result": "PASS", "ssot_compliance_score": 95}'
        assert verifier._extract_json_block(text) == text

    def test_markdown_json_block(self, verifier):
        text = '```json\n{"result": "PASS"}\n```'
        assert verifier._extract_json_block(text) == '{"result": "PASS"}'

    def test_markdown_block(self, verifier):
        text = '```\n{"result": "FAIL"}\n```'
        assert verifier._extract_json_block(text) == '{"result": "FAIL"}'


class TestTryParse:
    def test_valid_json(self, verifier):
        assert verifier._try_parse('{"result": "PASS"}') == {"result": "PASS"}

    def test_invalid_json(self, verifier):
        assert verifier._try_parse('not json') is None

    def test_array_returns_none(self, verifier):
        assert verifier._try_parse('[1, 2, 3]') is None


class TestRepairJson:
    def test_newline_in_string(self, verifier):
        broken = '{"feedback": "줄바꿈\n포함된\n텍스트"}'
        repaired = verifier._repair_json(broken)
        import json
        parsed = json.loads(repaired)
        assert "줄바꿈" in parsed["feedback"]

    def test_unterminated_string(self, verifier):
        # 실제 에러 패턴: Unterminated string starting at line 5
        broken = '{\n  "result": "PASS",\n  "ssot_compliance_score": 85,\n  "issues": [],\n  "feedback": "DRF API를 통해 검증된 데이터만 사용'
        repaired = verifier._repair_json(broken)
        import json
        parsed = json.loads(repaired)
        assert parsed["result"] == "PASS"
        assert parsed["ssot_compliance_score"] == 85

    def test_unterminated_with_issues(self, verifier):
        broken = '{\n  "result": "WARNING",\n  "ssot_compliance_score": 70,\n  "issues": ["문제1", "문제2가 길어서 잘림'
        repaired = verifier._repair_json(broken)
        import json
        parsed = json.loads(repaired)
        assert parsed["result"] == "WARNING"


class TestExtractFieldsRegex:
    def test_basic_extraction(self, verifier):
        text = '{"result": "PASS", "ssot_compliance_score": 92, "issues": [], "feedback": "검증 통과"}'
        result = verifier._extract_fields_regex(text)
        assert result["result"] == "PASS"
        assert result["ssot_compliance_score"] == 92

    def test_broken_json_extraction(self, verifier):
        text = '{"result": "FAIL", "ssot_compliance_score": 30, "issues": ["환각 감지", "DRF 미사용"], "feedback": "심각한 문제...'
        result = verifier._extract_fields_regex(text)
        assert result["result"] == "FAIL"
        assert result["ssot_compliance_score"] == 30
        assert "환각 감지" in result["issues"]
        assert "DRF 미사용" in result["issues"]

    def test_no_fields_returns_none(self, verifier):
        assert verifier._extract_fields_regex("완전히 깨진 텍스트") is None


class TestParseVerificationResult:
    """실제 Gemini 출력 패턴에 대한 통합 테스트"""

    def test_clean_json(self, verifier):
        text = '{"result": "PASS", "ssot_compliance_score": 95, "issues": [], "feedback": "SSOT 준수 확인"}'
        result = verifier._parse_verification_result(text)
        assert result["result"] == "PASS"
        assert result["ssot_compliance_score"] == 95

    def test_unterminated_string_line5(self, verifier):
        """실제 에러: Unterminated string starting at: line 5 column 5 (char 71)"""
        text = '{\n  "result": "PASS",\n  "ssot_compliance_score": 90,\n  "issues": [],\n  "feedback": "DRF API(search_law, search_precedent)를 통해 형법 및 형사소송법을 검색하고, 판례 2017도12457을 검증하였습니다. 응답에 사용된 법령명과 조문이 Tool 결과와 일치하며, 출처도 명확합니다'
        result = verifier._parse_verification_result(text)
        assert result["result"] == "PASS"
        assert result["ssot_compliance_score"] == 90

    def test_unterminated_string_line7(self, verifier):
        """실제 에러: Unterminated string starting at: line 7 column 3 (char 134)"""
        text = '{\n  "result": "WARNING",\n  "ssot_compliance_score": 75,\n  "issues": [\n    "일부 조문 번호가 Tool 결과에 없음"\n  ],\n  "feedback": "전반적으로 DRF 데이터를 사용했으나 일부 조문에 대해 검증이 불완전합니다.\n추가 검증이 필요합니다'
        result = verifier._parse_verification_result(text)
        assert result["result"] == "WARNING"
        assert result["ssot_compliance_score"] == 75

    def test_totally_broken_with_result_field(self, verifier):
        """JSON이 심하게 깨졌지만 result/score 필드 추출 가능"""
        text = 'Some prefix {"result": "FAIL", "ssot_compliance_score": 20, broken stuff...'
        result = verifier._parse_verification_result(text)
        assert result["result"] == "FAIL"
        assert result["ssot_compliance_score"] == 20

    def test_totally_unrecoverable(self, verifier):
        """완전히 복구 불가능한 경우 — WARNING 반환 (ERROR 아님)"""
        text = "이것은 JSON이 아닙니다"
        result = verifier._parse_verification_result(text)
        assert result["result"] == "WARNING"
        assert result["ssot_compliance_score"] == 50

    def test_missing_fields_filled(self, verifier):
        text = '{"result": "PASS"}'
        result = verifier._parse_verification_result(text)
        assert result["ssot_compliance_score"] == 50
        assert result["issues"] == []
        assert result["feedback"] == "검증 완료"
