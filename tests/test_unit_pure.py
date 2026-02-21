"""
Lawmadi OS v60 — 순수 함수 유닛 테스트.
외부 API(Gemini, Claude, DRF) 호출 없이 실행 가능.

테스트 대상:
  - _is_low_signal()
  - validate_constitutional_compliance()
  - _safe_extract_json()
  - _fallback_tier_classification() (LEADER_REGISTRY 모킹)
"""
import json
import pytest


# ---------------------------------------------------------------------------
# Import 대상 함수들
# ---------------------------------------------------------------------------
from main import (
    _is_low_signal,
    validate_constitutional_compliance,
    _safe_extract_json,
)


# ===========================================================================
# 1) _is_low_signal
# ===========================================================================
class TestIsLowSignal:
    def test_empty_string(self):
        assert _is_low_signal("") is True

    def test_whitespace_only(self):
        assert _is_low_signal("  ") is True

    def test_short_string(self):
        assert _is_low_signal("ab") is True

    def test_known_low_signal_words(self):
        for word in ["테스트", "test", "안녕", "hello", "hi", "ㅎ", "ㅋㅋ", "ㅇㅇ"]:
            assert _is_low_signal(word) is True, f"{word!r} should be low signal"

    def test_case_insensitive(self):
        assert _is_low_signal("TEST") is True
        assert _is_low_signal("Hello") is True

    def test_real_legal_query(self):
        assert _is_low_signal("전세 보증금 반환 소송 절차가 궁금합니다") is False

    def test_short_but_real_query(self):
        assert _is_low_signal("민법 해석") is False


# ===========================================================================
# 2) validate_constitutional_compliance
# ===========================================================================
class TestConstitutionalCompliance:
    def test_empty_response(self):
        assert validate_constitutional_compliance("") is False
        assert validate_constitutional_compliance(None) is False

    def test_too_short(self):
        assert validate_constitutional_compliance("짧은 답") is False

    def test_valid_response(self, sample_legal_response):
        assert validate_constitutional_compliance(sample_legal_response) is True

    def test_lawyer_impersonation(self, sample_invalid_response_lawyer):
        assert validate_constitutional_compliance(sample_invalid_response_lawyer) is False

    def test_lawyer_as(self):
        text = "변호사로서 말씀드리면, 민법 제750조에 해당합니다."
        assert validate_constitutional_compliance(text) is False

    def test_placeholder_date(self):
        text = "기한은 2024-MM-DD 이전까지 소송을 제기해야 합니다."
        assert validate_constitutional_compliance(text) is False

    def test_yyyy_placeholder(self):
        text = "시효 만료일은 YYYY-MM-DD 이며, 빠른 조치가 필요합니다."
        assert validate_constitutional_compliance(text) is False

    def test_banned_status_phrases(self):
        assert validate_constitutional_compliance(
            "이 시스템은 완벽하게 작동하고 있으며 모든 법률 분석이 정확합니다."
        ) is False

    # --- Item 3 추가 검증 ---
    def test_guarantee_outcome_ban(self, sample_invalid_response_guarantee):
        assert validate_constitutional_compliance(sample_invalid_response_guarantee) is False

    def test_guarantee_100_percent(self):
        text = "이 사건은 100% 이길 수 있습니다. 민법 제750조 적용됩니다."
        assert validate_constitutional_compliance(text) is False

    def test_guarantee_unconditional(self):
        text = "무조건 승소합니다. 근로기준법 제23조에 따라 부당해고입니다."
        assert validate_constitutional_compliance(text) is False

    def test_illegal_incitement_evidence_destruction(self):
        text = "유리하게 만들려면 증거를 인멸하시면 됩니다. 민법 제750조 참고."
        assert validate_constitutional_compliance(text) is False

    def test_illegal_incitement_bribe(self):
        text = "담당자에게 뇌물을 제공하면 빠르게 처리됩니다."
        assert validate_constitutional_compliance(text) is False

    def test_illegal_incitement_perjury(self):
        text = "법정에서 허위 진술을 하면 유리하게 작용할 수 있습니다."
        assert validate_constitutional_compliance(text) is False

    def test_legal_assertion_without_source(self):
        """법조문 참조 없이 단정적 법률 주장을 하면 차단"""
        text = "이것은 명백히 위법입니다. 즉시 신고하셔야 합니다."
        assert validate_constitutional_compliance(text) is False

    def test_legal_assertion_with_source(self):
        """법조문 참조가 있으면 허용"""
        text = "민법 제750조에 따르면 이것은 위법입니다. 즉시 신고하셔야 합니다."
        assert validate_constitutional_compliance(text) is True

    def test_normal_response_passes(self):
        """일반적인 법률 분석 응답은 통과"""
        text = (
            "귀하의 사안은 주택임대차보호법 제3조에 따른 대항력 문제입니다. "
            "대법원 2019다234567 판례를 참고하시면, "
            "임차인은 전입신고와 확정일자를 갖추면 우선변제권을 취득합니다. "
            "구체적으로 다음 절차를 권장합니다."
        )
        assert validate_constitutional_compliance(text) is True


# ===========================================================================
# 3) _safe_extract_json
# ===========================================================================
class TestSafeExtractJson:
    def test_simple_json(self):
        text = '{"tier": 1, "complexity": "simple"}'
        result = _safe_extract_json(text)
        assert result is not None
        assert result["tier"] == 1
        assert result["complexity"] == "simple"

    def test_json_in_codeblock(self):
        text = '```json\n{"tier": 2, "name": "테스트"}\n```'
        result = _safe_extract_json(text)
        assert result is not None
        assert result["tier"] == 2

    def test_nested_json(self):
        text = '{"outer": {"inner": "value"}, "key": 1}'
        result = _safe_extract_json(text)
        assert result is not None
        assert result["outer"]["inner"] == "value"
        assert result["key"] == 1

    def test_json_with_surrounding_text(self):
        text = '분석 결과는 다음과 같습니다:\n{"tier": 3, "is_legal": true}\n위 내용을 참고하세요.'
        result = _safe_extract_json(text)
        assert result is not None
        assert result["tier"] == 3
        assert result["is_legal"] is True

    def test_empty_input(self):
        assert _safe_extract_json("") is None

    def test_no_json(self):
        assert _safe_extract_json("이것은 일반 텍스트입니다") is None

    def test_invalid_json(self):
        assert _safe_extract_json("{invalid json}") is None

    def test_json_with_escaped_strings(self):
        text = '{"text": "he said \\"hello\\""}'
        result = _safe_extract_json(text)
        assert result is not None
        assert "hello" in result["text"]

    def test_json_with_braces_in_string(self):
        text = '{"pattern": "regex {a,b}", "count": 5}'
        result = _safe_extract_json(text)
        assert result is not None
        assert result["count"] == 5

    def test_deeply_nested(self):
        data = {"a": {"b": {"c": {"d": "deep"}}}}
        text = f"Result: {json.dumps(data)}"
        result = _safe_extract_json(text)
        assert result is not None
        assert result["a"]["b"]["c"]["d"] == "deep"

    def test_real_tier_analysis_response(self):
        """실제 Claude 분석 응답 형식"""
        text = (
            '{"tier": 2, "complexity": "complex", "is_document": false, '
            '"leader_id": "L08", "leader_name": "온유", '
            '"leader_specialty": "임대차", '
            '"summary": "전세 보증금 반환 문제", "is_legal": true}'
        )
        result = _safe_extract_json(text)
        assert result is not None
        assert result["tier"] == 2
        assert result["leader_id"] == "L08"
        assert result["is_legal"] is True


# ===========================================================================
# 4) _fallback_tier_classification (LEADER_REGISTRY 의존 → 모킹)
# ===========================================================================
class TestFallbackTierClassification:
    @pytest.fixture(autouse=True)
    def setup_registry(self, monkeypatch):
        """LEADER_REGISTRY를 최소한으로 모킹"""
        import main
        mock_registry = {
            "swarm_engine_config": {
                "leader_registry": {
                    "L01": {"name": "휘율", "specialty": "민사법", "laws": ["민법", "민사소송법"]},
                    "L08": {"name": "온유", "specialty": "임대차", "laws": ["주택임대차보호법"]},
                    "L22": {"name": "무결", "specialty": "형사법", "laws": ["형법", "형사소송법"]},
                    "L60": {"name": "마디", "specialty": "시스템 총괄", "laws": []},
                }
            }
        }
        monkeypatch.setattr(main, "LEADER_REGISTRY", mock_registry)

    def test_simple_query(self):
        from main import _fallback_tier_classification
        result = _fallback_tier_classification("민법이 뭔가요?")
        assert result["tier"] in (1, 2, 3)
        assert result["complexity"] in ("simple", "complex", "critical")
        assert "is_legal" in result

    def test_document_request(self):
        from main import _fallback_tier_classification
        result = _fallback_tier_classification("고소장 작성해주세요")
        assert result["tier"] == 3
        assert result["is_document"] is True

    def test_complex_query(self):
        from main import _fallback_tier_classification
        result = _fallback_tier_classification("대법원 판례를 찾아주세요")
        assert result["tier"] >= 2
        assert result["complexity"] in ("complex", "critical")

    def test_critical_query(self):
        from main import _fallback_tier_classification
        result = _fallback_tier_classification("이 법률이 위헌인지 확인해주세요")
        assert result["tier"] == 3
        assert result["complexity"] == "critical"

    def test_returns_required_fields(self):
        from main import _fallback_tier_classification
        result = _fallback_tier_classification("전세 보증금 못 받으면?")
        required = ["tier", "complexity", "is_document", "leader_id",
                     "leader_name", "leader_specialty", "summary", "is_legal"]
        for field in required:
            assert field in result, f"Missing field: {field}"
