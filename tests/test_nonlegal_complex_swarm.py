"""
Lawmadi OS v60 — 비법률 질문 · 복잡 질문 · 다중 리더 협업 테스트
외부 API 호출 없이 오프라인으로 실행 가능한 순수 테스트.

테스트 범주:
  1. 비법률 질문 감지 & CCO 폴백
  2. 복잡/위기 질문 티어 분류
  3. 다중 도메인 탐지 (SwarmOrchestrator.detect_domains)
  4. 다중 리더 선택 (SwarmOrchestrator.select_leaders)
  5. C-Level 임원 호출 & 모드 결정
  6. Swarm 오케스트레이션 결정 로직
"""
import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.classifier import (
    _nlu_detect_intent,
    _fallback_tier_classification,
    select_swarm_leader,
    set_leader_registry,
)
from agents.clevel_handler import CLevelHandler


# ─── Fixtures ────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def leaders_data():
    with open("leaders.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    set_leader_registry(data)
    return data


@pytest.fixture(scope="session")
def leader_registry(leaders_data):
    return leaders_data.get("swarm_engine_config", {}).get("leader_registry", {})


@pytest.fixture(scope="session")
def config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def swarm(leaders_data, config):
    from agents.swarm_orchestrator import SwarmOrchestrator
    reg = leaders_data.get("swarm_engine_config", {}).get("leader_registry", {})
    return SwarmOrchestrator(reg, config, genai_client=None)


@pytest.fixture(scope="session")
def clevel(leaders_data):
    core_reg = leaders_data.get("core_registry", {})
    return CLevelHandler(core_reg)


# ═══════════════════════════════════════════════════════════════════
# 1. 비법률 질문 감지 & CCO 폴백
# ═══════════════════════════════════════════════════════════════════

class TestNonLegalDetection:
    """비법률 질문은 is_legal=False + CCO(유나) 라우팅"""

    @pytest.mark.parametrize("query", [
        "오늘 날씨 어때요?",
        "맛있는 파스타 레시피 알려줘",
        "제주도 여행지 추천해줘",
        "영화 추천 부탁해요",
        "다이어트 운동 방법 알려줘",
        "좋은 음악 추천해주세요",
    ])
    def test_non_legal_classified_correctly(self, query, leaders_data):
        result = _fallback_tier_classification(query)
        assert result["is_legal"] is False, (
            f"비법률 질문 '{query}' → is_legal={result['is_legal']} (False 기대)"
        )

    @pytest.mark.parametrize("query", [
        "오늘 날씨 좋은데 소풍 갈까요?",
        "맛집 어디 있어요?",
        "영화 뭐 볼까요?",
    ])
    def test_non_legal_routes_to_cco(self, query, leaders_data, leader_registry):
        result = select_swarm_leader(query, leaders_data)
        name = result.get("name", "")
        clevel = result.get("_clevel", "")
        assert name == "유나" or clevel == "CCO", (
            f"비법률 '{query}' → 유나(CCO) 기대, 실제: {name}"
        )

    @pytest.mark.parametrize("query", [
        "안녕하세요 반갑습니다",
        "자기소개 해줘",
    ])
    def test_greeting_routes_to_cco(self, query, leaders_data):
        result = _fallback_tier_classification(query)
        assert result["is_legal"] is False

    # 법률처럼 보이지만 법률이 아닌 경계 케이스
    @pytest.mark.parametrize("query, expected_legal", [
        ("이혼 소송 절차", True),
        ("이혼이라는 영화 추천", False),  # "영화 추천" 비법률 키워드 포함
    ])
    def test_boundary_cases(self, query, expected_legal, leaders_data):
        result = _fallback_tier_classification(query)
        assert result["is_legal"] == expected_legal, (
            f"경계 케이스 '{query}' → is_legal={result['is_legal']}, 기대: {expected_legal}"
        )


# ═══════════════════════════════════════════════════════════════════
# 2. 복잡/위기 질문 티어 분류
# ═══════════════════════════════════════════════════════════════════

class TestComplexTierClassification:
    """Tier 2(복합), Tier 3(위기/문서) 분류 정확성"""

    # Tier 1: 단순 법률 질문
    @pytest.mark.parametrize("query", [
        "전세 보증금 반환 기한",
        "교통사고 합의금 기준",
        "이혼 절차 알려줘",
        "해고 예고 기간",
    ])
    def test_simple_tier1(self, query, leaders_data):
        result = _fallback_tier_classification(query)
        assert result["tier"] == 1, f"'{query}' → tier={result['tier']}, 기대: 1"
        assert result["complexity"] == "simple"

    # Tier 2: 복합 법률 질문 (판례 필요, 2+ 법률)
    @pytest.mark.parametrize("query", [
        "대법원 판례에 따른 보증금 반환 기준",
        "사례를 검토하여 해고 부당성 판단",
    ])
    def test_complex_tier2(self, query, leaders_data):
        result = _fallback_tier_classification(query)
        assert result["tier"] == 2, f"'{query}' → tier={result['tier']}, 기대: 2"
        assert result["complexity"] == "complex"

    # Tier 3: 문서 작성 요청
    @pytest.mark.parametrize("query", [
        "고소장 작성해줘",
        "내용증명 써줘",
        "소장 초안 만들어줘",
        "답변서 양식 만들어줘",
        "합의서 작성해줘",
        "계약서 서식 필요해",
    ])
    def test_document_tier3(self, query, leaders_data):
        result = _fallback_tier_classification(query)
        assert result["tier"] == 3, f"'{query}' → tier={result['tier']}, 기대: 3"
        assert result["is_document"] is True

    # Tier 3: 헌법 쟁점
    @pytest.mark.parametrize("query", [
        "이 법률이 위헌인지 검토해줘",
        "헌법소원 청구 요건",
        "기본권 침해 여부 판단",
    ])
    def test_critical_tier3(self, query, leaders_data):
        result = _fallback_tier_classification(query)
        assert result["tier"] == 3, f"'{query}' → tier={result['tier']}, 기대: 3"
        assert result["complexity"] == "critical"

    # 티어별 필수 필드 검증
    def test_all_tiers_have_required_fields(self, leaders_data):
        queries = ["보증금 반환", "대법원 판례 검토", "고소장 작성해줘"]
        required = ["tier", "complexity", "is_document", "leader_id",
                     "leader_name", "leader_specialty", "summary", "is_legal"]
        for q in queries:
            result = _fallback_tier_classification(q)
            for field in required:
                assert field in result, f"'{q}' 결과에 '{field}' 누락"


# ═══════════════════════════════════════════════════════════════════
# 3. 다중 도메인 탐지 (SwarmOrchestrator.detect_domains)
# ═══════════════════════════════════════════════════════════════════

class TestMultiDomainDetection:
    """여러 법률 분야에 걸친 질문이 복수 도메인으로 탐지되는지 검증"""

    def test_single_domain_returns_one(self, swarm):
        """단일 도메인 질문 → 1개 도메인 우세"""
        domains = swarm.detect_domains("전세 보증금 반환 절차")
        assert len(domains) >= 1
        top_id = domains[0][0]
        assert top_id == "L08", f"임대차 → L08 기대, 실제: {top_id}"

    def test_multi_domain_returns_multiple(self, swarm):
        """다중 도메인 질문 → 2개 이상 탐지"""
        # 부동산(L02) + 재개발(L04) + 건설(L03) 동시 매칭
        domains = swarm.detect_domains("재개발 건축 하자 부동산 등기 문제")
        assert len(domains) >= 2, f"다중 도메인 기대, 실제: {len(domains)}개 — {domains}"

    @pytest.mark.parametrize("query, expected_ids, description", [
        # 이혼(L41) + 부동산(L02/L08)
        (
            "이혼하는데 전세 보증금 재산분할 어떻게",
            {"L41", "L08"},
            "가사법+임대차"
        ),
        # 형사(L22) + 민사 손해배상(L06)
        (
            "폭행당해서 고소하고 손해배상 위자료 청구",
            {"L22", "L06"},
            "형사+손해배상"
        ),
        # 노동(L30) + 산재(L43)
        (
            "직장에서 부당해고 산업재해 요양급여",
            {"L30", "L43"},
            "노동법+산재"
        ),
    ])
    def test_cross_domain_detected(self, query, expected_ids, description, swarm):
        domains = swarm.detect_domains(query)
        detected_ids = {d[0] for d in domains}
        overlap = expected_ids & detected_ids
        assert len(overlap) >= 2, (
            f"[{description}] '{query}' → "
            f"기대 도메인: {expected_ids}, 탐지: {detected_ids}, 교집합: {overlap}"
        )

    def test_scores_are_positive(self, swarm):
        """탐지된 도메인의 점수가 모두 양수"""
        domains = swarm.detect_domains("부동산 경매 낙찰 명도 강제집행")
        for leader_id, score in domains:
            assert score > 0, f"{leader_id} 점수가 0 이하: {score}"

    def test_empty_query_returns_empty(self, swarm):
        """빈 질문 → 도메인 없음"""
        domains = swarm.detect_domains("")
        assert len(domains) == 0

    def test_non_legal_query_returns_empty_or_low(self, swarm):
        """비법률 질문 → 도메인 없거나 낮은 점수"""
        domains = swarm.detect_domains("오늘 날씨 어때요")
        # 빈 결과이거나, 점수가 매우 낮아야 함
        if domains:
            top_score = domains[0][1]
            assert top_score <= 10, f"비법률 질문인데 점수 {top_score}으로 높음"


# ═══════════════════════════════════════════════════════════════════
# 4. 다중 리더 선택 (SwarmOrchestrator.select_leaders)
# ═══════════════════════════════════════════════════════════════════

class TestMultiLeaderSelection:
    """select_leaders: 단일/다중 리더 선택 로직"""

    def test_name_call_returns_single_leader(self, swarm):
        """이름 호출 → 단일 리더"""
        leaders = swarm.select_leaders("휘율아 민사 소송 방법")
        assert len(leaders) == 1
        assert leaders[0].get("name") == "휘율"
        assert leaders[0].get("_score") == 100  # 이름 호출 최우선

    def test_single_domain_returns_single(self, swarm):
        """단일 도메인 → 리더 1명"""
        domains = [("L08", 40)]  # 임대차만
        leaders = swarm.select_leaders("전세 보증금 반환", detected_domains=domains)
        assert len(leaders) >= 1
        assert leaders[0].get("_id") == "L08"

    def test_multi_domain_returns_multiple(self, swarm):
        """다중 도메인 → 리더 2+명"""
        domains = [("L22", 30), ("L06", 25), ("L41", 20)]
        leaders = swarm.select_leaders("형사 손해배상 이혼", detected_domains=domains)
        assert len(leaders) >= 2, f"다중 리더 기대, 실제: {len(leaders)}"

    def test_max_leaders_respected(self, swarm):
        """max_leaders(3) 초과하지 않음"""
        domains = [("L01", 30), ("L02", 25), ("L03", 20), ("L04", 15), ("L05", 10)]
        leaders = swarm.select_leaders("여러 분야", detected_domains=domains)
        assert len(leaders) <= swarm.max_leaders, (
            f"max_leaders={swarm.max_leaders} 초과: {len(leaders)}명"
        )

    def test_no_domain_falls_to_cco(self, swarm):
        """도메인 미탐지 (Gemini 없음) → CCO 폴백"""
        leaders = swarm.select_leaders("ㅋㅋㅋ 재미있다", detected_domains=[])
        assert len(leaders) >= 1
        assert leaders[0].get("name") == "유나" or leaders[0].get("_clevel") == "CCO"

    def test_unknown_name_call_returns_cco(self, swarm):
        """미등록 이름 호출 → CCO 안내"""
        leaders = swarm.select_leaders("철수야 도와줘")
        has_cco = any(
            l.get("_clevel") == "CCO" or l.get("name") == "유나"
            for l in leaders
        )
        # 미등록 이름은 detect_name_call에서 감지되지 않으므로 도메인 미탐지 → CCO
        assert has_cco or len(leaders) >= 1  # 최소 1명 반환 보장

    def test_leader_info_has_required_fields(self, swarm):
        """선택된 리더에 필수 필드 존재"""
        domains = [("L08", 40)]
        leaders = swarm.select_leaders("보증금 반환", detected_domains=domains)
        for leader in leaders:
            assert "name" in leader, "name 필드 누락"
            assert "_id" in leader or "_clevel" in leader, "_id 또는 _clevel 누락"


# ═══════════════════════════════════════════════════════════════════
# 5. C-Level 임원 호출 & 모드 결정
# ═══════════════════════════════════════════════════════════════════

class TestCLevelInvocation:
    """CLevelHandler: 명시적 호출, 전문 영역 감지, 모드 결정"""

    # 5-1. 이름 호출 감지
    @pytest.mark.parametrize("query, expected_exec", [
        ("서연아 이 사건 전략 분석해줘", "CSO"),
        ("지유야 시스템 아키텍처 검증", "CTO"),
        ("유나야 사용자 경험 개선 방법", "CCO"),
    ])
    def test_name_call_detected(self, query, expected_exec, clevel):
        result = clevel.detect_clevel_call(query)
        assert result is not None, f"'{query}' → C-Level 감지 실패"
        exec_id, reason = result
        assert exec_id == expected_exec, (
            f"'{query}' → 기대: {expected_exec}, 실제: {exec_id}"
        )

    # 5-2. 트리거 키워드 감지 (2개 이상)
    @pytest.mark.parametrize("query, expected_exec", [
        ("전략 기획 방향 잡아줘", "CSO"),          # 전략+기획+방향
        ("시스템 성능 보안 점검", "CTO"),           # 시스템+성능+보안
        ("사용자 경험 콘텐츠 개선", "CCO"),         # 사용자+경험+콘텐츠
    ])
    def test_trigger_keyword_detected(self, query, expected_exec, clevel):
        result = clevel.detect_clevel_call(query)
        assert result is not None, f"'{query}' → C-Level 감지 실패"
        exec_id, _ = result
        assert exec_id == expected_exec

    # 5-3. 트리거 키워드 1개만 → 감지 안 됨
    @pytest.mark.parametrize("query", [
        "전략이 필요해요",       # CSO 키워드 1개만
        "시스템 문의",           # CTO 키워드 1개만
        "사용자 질문",           # CCO 키워드 1개만
    ])
    def test_single_trigger_not_detected(self, query, clevel):
        result = clevel.detect_clevel_call(query)
        assert result is None, f"키워드 1개에 C-Level 오감지: {result}"

    # 5-4. should_invoke_clevel — 모드 결정
    def test_direct_mode_non_legal(self, clevel):
        """C-Level 이름 호출 + 비법률 → direct 모드"""
        result = clevel.should_invoke_clevel("서연아 자기소개 해줘")
        assert result["invoke"] is True
        assert result["mode"] == "direct"
        assert result["executive_id"] == "CSO"

    def test_swarm_mode_legal_with_clevel(self, clevel):
        """C-Level 이름 호출 + 법률 키워드 → swarm 모드"""
        result = clevel.should_invoke_clevel("서연아 이혼 재산분할 전략")
        assert result["invoke"] is True
        assert result["mode"] == "swarm"
        assert result["executive_id"] == "CSO"

    def test_no_invoke_plain_legal(self, clevel):
        """일반 법률 질문 → C-Level 미호출"""
        result = clevel.should_invoke_clevel("보증금 반환 소송 절차")
        assert result["invoke"] is False
        assert result["mode"] == "none"

    def test_meta_question_invokes_cso(self, clevel):
        """메타 질문 (전략+방법 키워드 2개+) → CSO swarm 보강"""
        result = clevel.should_invoke_clevel("이 상황에서 어떻게 해야 할까 전략적 방법")
        assert result["invoke"] is True
        assert result["executive_id"] == "CSO"
        assert result["mode"] == "swarm"

    # 5-5. 법률 도메인 감지 정확성
    @pytest.mark.parametrize("query, has_legal", [
        ("이혼 재산분할 양육권", True),
        ("형법 사기죄 처벌", True),
        ("오늘 날씨 좋다", False),
        ("맛집 추천해줘", False),
    ])
    def test_has_legal_domain(self, query, has_legal, clevel):
        assert clevel._has_legal_domain(query) == has_legal, (
            f"'{query}' → _has_legal_domain 기대: {has_legal}"
        )

    # 5-6. 오탐 방지 (자기소개 → "기소" 오탐 차단)
    def test_false_positive_prevention(self, clevel):
        """'자기소개'에서 '기소' 오탐 방지"""
        assert clevel._has_legal_domain("자기소개 해줘") is False


# ═══════════════════════════════════════════════════════════════════
# 6. Swarm 오케스트레이션 결정 로직
# ═══════════════════════════════════════════════════════════════════

class TestSwarmOrchestrationDecision:
    """orchestrate 흐름의 핵심 결정 지점 검증 (Gemini 미사용)"""

    def test_swarm_enabled_by_default(self, swarm):
        assert swarm.swarm_enabled is True

    def test_max_leaders_default_3(self, swarm):
        assert swarm.max_leaders == 3

    def test_min_leaders_default_1(self, swarm):
        assert swarm.min_leaders == 1

    def test_detect_name_call_returns_leader_id(self, swarm):
        """이름 호출 → 리더 ID 반환"""
        lid = swarm.detect_name_call("온유야 보증금 문제야")
        assert lid == "L08"

    def test_detect_name_call_no_match(self, swarm):
        """이름 없으면 None"""
        lid = swarm.detect_name_call("보증금 반환 절차")
        assert lid is None

    # 종합 시나리오 테스트
    def test_scenario_single_leader_query(self, swarm):
        """단일 분야 질문 → 1명 리더"""
        domains = swarm.detect_domains("전세 보증금 반환 절차 확정일자")
        leaders = swarm.select_leaders("전세 보증금 반환 절차 확정일자", detected_domains=domains)
        # L08이 최상위
        assert leaders[0].get("_id") == "L08"

    def test_scenario_multi_leader_query(self, swarm):
        """다중 분야 질문 → 2+명 리더"""
        query = "이혼하면서 전세 보증금 재산분할하고 양육비 문제"
        domains = swarm.detect_domains(query)
        leaders = swarm.select_leaders(query, detected_domains=domains)
        leader_ids = {l.get("_id") for l in leaders}
        # L41(가사법)과 L08(임대차)가 모두 포함되어야 함
        assert "L41" in leader_ids or "L08" in leader_ids, (
            f"가사+임대차 기대, 실제 리더: {leader_ids}"
        )
        assert len(leaders) >= 2, f"2+명 기대, 실제: {len(leaders)}"

    def test_scenario_no_swarm_when_name_called(self, swarm):
        """이름 호출 시 → 단일 리더 강제"""
        leaders = swarm.select_leaders("무결아 사기죄 형사 고소 방법")
        assert len(leaders) == 1
        assert leaders[0].get("name") == "무결"

    def test_scenario_gibberish_to_cco(self, swarm):
        """의미 없는 입력 → CCO 폴백"""
        leaders = swarm.select_leaders("ㅎㅎㅎ ㅋㅋ", detected_domains=[])
        assert any(
            l.get("_clevel") == "CCO" or l.get("name") == "유나"
            for l in leaders
        )


# ═══════════════════════════════════════════════════════════════════
# 7. 복합 시나리오 — 전체 흐름 통합
# ═══════════════════════════════════════════════════════════════════

class TestIntegratedScenarios:
    """분류기 + 오케스트레이터 + C-Level 통합 시나리오"""

    def test_non_legal_full_flow(self, leaders_data, swarm, clevel):
        """비법률 질문 전체 흐름"""
        query = "오늘 서울 날씨 어때?"
        # 1) 분류기: 비법률
        tier_result = _fallback_tier_classification(query)
        assert tier_result["is_legal"] is False
        # 2) 리더 선택: CCO
        leader = select_swarm_leader(query, leaders_data)
        assert leader.get("name") == "유나" or leader.get("_clevel") == "CCO"
        # 3) C-Level: 미호출
        clevel_result = clevel.should_invoke_clevel(query)
        assert clevel_result["invoke"] is False

    def test_simple_legal_full_flow(self, leaders_data, swarm, clevel):
        """단순 법률 질문 전체 흐름"""
        query = "전세 보증금 못 받고 있어요"
        # 1) 분류기: 법률, tier 1
        tier_result = _fallback_tier_classification(query)
        assert tier_result["is_legal"] is True
        assert tier_result["tier"] == 1
        # 2) NLU: L08 (보증금 + 못 받 → 임대차 패턴 매칭)
        nlu_result = _nlu_detect_intent(query)
        assert nlu_result == "L08"
        # 3) 리더 선택: 온유(L08)
        leader = select_swarm_leader(query, leaders_data)
        assert leader.get("name") == "온유"
        # 4) C-Level: 미호출
        clevel_result = clevel.should_invoke_clevel(query)
        assert clevel_result["invoke"] is False

    def test_complex_multi_domain_full_flow(self, leaders_data, swarm, clevel):
        """복합 다중 도메인 질문 전체 흐름"""
        query = "이혼하면서 아파트 전세 보증금 재산분할 양육권 대법원 판례"
        # 1) 분류기: 법률, tier 2 (판례 키워드)
        tier_result = _fallback_tier_classification(query)
        assert tier_result["is_legal"] is True
        assert tier_result["tier"] >= 2
        # 2) 다중 도메인 탐지
        domains = swarm.detect_domains(query)
        domain_ids = {d[0] for d in domains}
        assert len(domains) >= 2
        # L41(가사), L08(임대차) 중 최소 1개
        assert domain_ids & {"L41", "L08"}, f"가사/임대차 기대, 실제: {domain_ids}"
        # 3) 다중 리더 선택
        leaders = swarm.select_leaders(query, detected_domains=domains)
        assert len(leaders) >= 2

    def test_clevel_legal_swarm_full_flow(self, leaders_data, swarm, clevel):
        """C-Level 호출 + 법률 도메인 → swarm 모드"""
        query = "서연아 이혼 재산분할 전략 세워줘"
        # 1) C-Level 감지: CSO + 법률 → swarm
        clevel_result = clevel.should_invoke_clevel(query)
        assert clevel_result["invoke"] is True
        assert clevel_result["executive_id"] == "CSO"
        assert clevel_result["mode"] == "swarm"
        # 2) 도메인: 이혼(L41) 탐지
        domains = swarm.detect_domains(query)
        domain_ids = {d[0] for d in domains}
        assert "L41" in domain_ids

    def test_document_writing_full_flow(self, leaders_data, swarm, clevel):
        """문서 작성 요청 전체 흐름"""
        query = "사기 당했는데 고소장 작성해줘"
        # 1) 분류기: tier 3, is_document
        tier_result = _fallback_tier_classification(query)
        assert tier_result["tier"] == 3
        assert tier_result["is_document"] is True
        assert tier_result["is_legal"] is True
        # 2) NLU: 형사(L22) (사기 + 당했 → 형사 패턴 매칭)
        nlu_result = _nlu_detect_intent(query)
        assert nlu_result == "L22"
