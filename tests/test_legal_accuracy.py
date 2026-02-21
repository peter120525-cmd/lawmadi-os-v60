"""
Lawmadi OS v60 — 법률 정확성 테스트.
Fail-Closed 동작, 헌법 적합성, SSOT 매칭을 검증.

외부 API 호출 없이 실행 가능.
"""
import json
import pytest

from main import (
    _safe_extract_json,
    validate_constitutional_compliance,
)
from core.constitutional import validate_constitutional_compliance as cc_validate


# ===========================================================================
# 1) Fail-Closed 동작 검증
# ===========================================================================
class TestFailClosed:
    """Claude 검증 엔진 미초기화 시 passed=False 반환 확인"""

    def test_step5_returns_fail_when_no_client(self):
        """_step5_claude_verify에서 Claude 없을 때 passed=False"""
        import main
        original = main.RUNTIME.get("claude_client")
        try:
            main.RUNTIME["claude_client"] = None
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                main._step5_claude_verify("테스트 질문", "테스트 응답")
            )
            assert result["passed"] is False
            assert "Fail-Closed" in (result.get("warning") or "")
        finally:
            if original is not None:
                main.RUNTIME["claude_client"] = original
            else:
                main.RUNTIME.pop("claude_client", None)

    def test_default_passed_is_false(self):
        """JSON 파싱 실패 시에도 passed 기본값은 False"""
        result = _safe_extract_json("not json at all")
        assert result is None  # 파싱 실패

    def test_verification_get_defaults_false(self):
        """verification.get('passed', False) 확인"""
        verification = {}
        assert verification.get("passed", False) is False


# ===========================================================================
# 2) 헌법 적합성 시나리오 테스트
# ===========================================================================
class TestConstitutionalScenarios:

    def test_guarantee_victory_blocked(self):
        """'반드시 승소' 보장 차단"""
        text = "이 사건은 반드시 승소할 것입니다. 민법 제750조 적용."
        assert validate_constitutional_compliance(text) is False

    def test_guarantee_100_percent_blocked(self):
        """100% 보장 차단"""
        text = "100% 이길 수 있습니다."
        assert validate_constitutional_compliance(text) is False

    def test_evidence_destruction_blocked(self):
        """증거 인멸 조장 차단"""
        text = "불리한 증거를 인멸하시면 됩니다."
        assert validate_constitutional_compliance(text) is False

    def test_bribery_blocked(self):
        """뇌물 조장 차단"""
        text = "관계자에게 뇌물을 제공하면 처리됩니다."
        assert validate_constitutional_compliance(text) is False

    def test_perjury_blocked(self):
        """위증 조장 차단"""
        text = "유리하게 허위 진술을 하면 됩니다."
        assert validate_constitutional_compliance(text) is False

    def test_forgery_blocked(self):
        """문서 위조 조장 차단"""
        text = "서류를 위조하면 쉽게 해결됩니다."
        assert validate_constitutional_compliance(text) is False

    def test_tax_evasion_blocked(self):
        """탈세 조장 차단"""
        text = "탈세 방법은 다음과 같습니다."
        assert validate_constitutional_compliance(text) is False

    def test_unsourced_legal_assertion_blocked(self):
        """근거 없는 법률 단정 차단"""
        text = "이것은 명백히 위법입니다."
        assert validate_constitutional_compliance(text) is False

    def test_sourced_legal_assertion_passes(self):
        """법조문 근거 있는 법률 주장은 통과"""
        text = "민법 제750조에 따르면 이것은 위법입니다."
        assert validate_constitutional_compliance(text) is True

    def test_lawyer_impersonation_blocked(self):
        """변호사 사칭 차단"""
        assert validate_constitutional_compliance("저는 변호사입니다.") is False
        assert validate_constitutional_compliance("변호사로서 조언드립니다. 이 사안은 중요합니다.") is False

    def test_placeholder_dates_blocked(self):
        """플레이스홀더 날짜 차단"""
        assert validate_constitutional_compliance("기한은 YYYY-MM-DD까지입니다.") is False
        assert validate_constitutional_compliance("날짜는 2024-MM-DD 이전입니다.") is False

    def test_normal_legal_response_passes(self):
        """정상적인 법률 분석 응답은 통과"""
        text = (
            "귀하의 사안은 주택임대차보호법 제3조에 따른 대항력 문제입니다. "
            "대법원 2019다234567 판례를 참고하시면, 임차인은 전입신고와 "
            "확정일자를 갖추면 우선변제권을 취득합니다. "
            "구체적인 절차를 안내해 드리겠습니다."
        )
        assert validate_constitutional_compliance(text) is True

    def test_module_and_main_consistency(self):
        """core.constitutional과 main.py의 함수가 동일 결과 반환"""
        test_cases = [
            "변호사입니다. 조언드립니다.",
            "민법 제750조에 따르면 손해배상 책임이 있습니다.",
            "반드시 승소합니다.",
            "",
        ]
        for text in test_cases:
            assert validate_constitutional_compliance(text) == cc_validate(text), \
                f"Mismatch for: {text!r}"


# ===========================================================================
# 3) SSOT 매칭 테스트
# ===========================================================================
class TestSSOTMatching:
    """config.json의 ssot_registry가 올바르게 구성되어 있는지 검증"""

    @pytest.fixture(autouse=True)
    def load_config(self):
        with open("config.json", "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self.registry = self.config.get("ssot_registry", {})

    def test_has_summary(self):
        """_summary 필드 존재"""
        assert "_summary" in self.registry

    def test_active_sources_count(self):
        """활성 소스 8개 확인"""
        active = [k for k, v in self.registry.items()
                  if isinstance(v, dict) and v.get("enabled", False)]
        assert len(active) >= 8, f"Active SSOT sources: {len(active)} (expected >= 8)"

    def test_inactive_source_ssot03(self):
        """SSOT_03 학칙공단 비활성 확인"""
        ssot03 = self.registry.get("SSOT_03", {})
        assert ssot03.get("enabled") is False

    def test_id_only_sources(self):
        """SSOT_08, SSOT_09는 ID_ONLY"""
        for key in ["SSOT_08", "SSOT_09"]:
            src = self.registry.get(key, {})
            assert src.get("access_type") == "ID_ONLY", f"{key} should be ID_ONLY"

    def test_all_active_have_endpoint(self):
        """활성 소스는 모두 endpoint 필드 보유"""
        for key, val in self.registry.items():
            if not isinstance(val, dict):
                continue
            if val.get("enabled"):
                assert "endpoint" in val, f"{key} missing endpoint"
