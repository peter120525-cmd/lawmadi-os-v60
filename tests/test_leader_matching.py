"""
Lawmadi OS v60 — 리더 매칭 정확성 & 답변 품질 검증
외부 API 호출 없이 오프라인으로 실행 가능한 순수 테스트.

테스트 범주:
  1. NLU 패턴 매칭 (자연어 → 리더 ID)
  2. 도메인 키워드 매칭 (키워드 → 리더)
  3. select_swarm_leader 통합 (이름 → NLU → 키워드 → 폴백)
  4. 교차 도메인 우선순위 (맥락 특정 > 포괄 형사)
  5. 티어 분류 (simple / complex / critical)
  6. 비법률 질문 감지
  7. 답변 품질 검증 (헌법 적합성 + 구조 + 인용)
"""
import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.classifier import (
    _nlu_detect_intent,
    select_swarm_leader,
    _fallback_tier_classification,
    set_leader_registry,
)
from core.constitutional import validate_constitutional_compliance


# ─── Fixtures ────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def leaders():
    with open("leaders.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    set_leader_registry(data)
    return data


@pytest.fixture(scope="session")
def registry(leaders):
    return leaders.get("swarm_engine_config", {}).get("leader_registry", {})


def _get_leader_id(registry: dict, result: dict) -> str:
    """select_swarm_leader가 반환한 info dict에서 리더 ID 역추적"""
    name = result.get("name", "")
    for lid, info in registry.items():
        if info.get("name") == name:
            return lid
    # CCO 폴백
    if name == "유나":
        return "CCO"
    return "UNKNOWN"


# ═══════════════════════════════════════════════════════════════════
# 1. NLU 패턴 매칭 — 자연어 질문 → 리더 ID
# ═══════════════════════════════════════════════════════════════════

class TestNLUPatternMatching:
    """_nlu_detect_intent: 구어체 한국어 질문을 정확하게 분류"""

    # (질문, 기대 리더 ID)
    @pytest.mark.parametrize("query, expected_leader", [
        # L08: 임대차
        ("보증금을 안 돌려줘요", "L08"),
        ("집주인이 수리를 안 해줘요", "L08"),
        ("전세금 못 받았어요", "L08"),
        ("계약 만료됐는데 재계약 거절당했어요", "L08"),
        ("이사 나가라고 강요해요", "L08"),
        # L22: 형사법
        ("친구한테 맞았어요", "L22"),
        ("스토킹 당하고 있어요", "L22"),
        ("빌려준 돈을 안 갚아요 사기인 것 같아요", "L22"),
        ("고소 방법 알려주세요", "L22"),
        ("몰카 피해를 당했어요", "L22"),
        # L30: 노동법
        ("회사에서 갑자기 잘렸어요", "L30"),
        ("월급을 3달째 못 받고 있어요", "L30"),
        ("야근 수당을 안 줘요", "L30"),
        ("상사가 직장에서 괴롭혀요", "L30"),
        ("퇴직금을 못 받았어요", "L30"),
        # L41: 가사법
        ("이혼하고 싶어요", "L41"),
        ("양육권 어떻게 해야 하나요", "L41"),
        ("남편이 바람을 피웠어요", "L41"),
        ("재산 분할 방법이 궁금해요", "L41"),
        ("가정 폭력 피해인데 어떻게 해야 해요", "L41"),
        # L57: 상속
        ("아버지가 돌아가셨는데 유산 어떻게 나눠요", "L57"),
        ("상속 포기하고 싶어요 빚이 있어요", "L57"),
        ("부모님 재산 상속 어떻게 해야 해요", "L57"),
        # L38: 소비자
        ("환불 요청했는데 안 해줘요", "L38"),
        ("불량 제품 교환 안 해줘요", "L38"),
        # L07: 교통사고
        ("차 사고가 났어요", "L07"),
        ("교통사고 보험 처리 어떻게 해요", "L07"),
        # L05: 의료법
        ("수술 실수로 부작용이 생겼어요", "L05"),
        ("의료사고 당했어요", "L05"),
        # L11: 채권추심
        ("추심 전화가 매일 와요 어떻게 해야 해요", "L11"),
        ("개인회생 신청하고 싶어요", "L11"),
        # L10: 민사집행
        ("통장이 압류됐어요 어떻게 해야 해요", "L10"),
        # L34: 개인정보
        ("개인정보 유출 피해를 당했어요", "L34"),
    ], ids=lambda x: x if isinstance(x, str) and len(x) > 3 else "")
    def test_nlu_intent(self, query, expected_leader):
        result = _nlu_detect_intent(query)
        assert result == expected_leader, (
            f"질문 '{query}' → 기대: {expected_leader}, 실제: {result}"
        )


# ═══════════════════════════════════════════════════════════════════
# 2. 교차 도메인 우선순위 — 맥락 특정 > 포괄 형사
# ═══════════════════════════════════════════════════════════════════

class TestCrossDomainPriority:
    """가사 폭력은 L41(가사법), 직장 폭언은 L30(노동법)으로 라우팅"""

    @pytest.mark.parametrize("query, expected, not_expected", [
        # 남편/아내 폭력 → L41 (가사법), NOT L22 (형사)
        ("남편이 때렸어요", "L41", "L22"),
        ("아내가 때린 적이 있어요", "L41", "L22"),
        ("배우자가 폭력을 휘둘러요", "L41", "L22"),
        # 직장 문제 → L30 (노동법), NOT L22 (형사)
        ("회사에서 잘렸어요", "L30", "L22"),
        ("사장이 괴롭혀요", "L30", "L22"),
        # 집주인 문제 → L08 (임대차), NOT 기타
        ("집주인이 보증금을 안 돌려줘요", "L08", "L22"),
    ])
    def test_context_beats_generic(self, query, expected, not_expected):
        result = _nlu_detect_intent(query)
        assert result == expected, (
            f"'{query}' → 기대: {expected}, 실제: {result} "
            f"(포괄 도메인 {not_expected}으로 잘못 라우팅 의심)"
        )


# ═══════════════════════════════════════════════════════════════════
# 3. select_swarm_leader 통합 테스트
# ═══════════════════════════════════════════════════════════════════

class TestSelectSwarmLeader:
    """전체 파이프라인: 이름 호출 → NLU → 키워드 → 폴백"""

    # 3-1. 이름 호출 우선
    @pytest.mark.parametrize("query, expected_name", [
        ("휘율아 계약 해지 방법 알려줘", "휘율"),
        ("온유야 전세 보증금 문제야", "온유"),
        ("무결아 사기 고소하고 싶어", "무결"),
    ])
    def test_name_call_priority(self, query, expected_name, leaders, registry):
        result = select_swarm_leader(query, leaders)
        assert result.get("name") == expected_name, (
            f"'{query}' → 기대 이름: {expected_name}, 실제: {result.get('name')}"
        )

    # 3-2. NLU 패턴 → 올바른 전문 분야 리더
    @pytest.mark.parametrize("query, expected_id, description", [
        ("보증금을 떼였어요", "L08", "임대차"),
        ("갑자기 해고 통보 받았어요", "L30", "노동법"),
        ("남편이 외도했어요", "L41", "가사법"),
        ("아버지 돌아가시고 유산 문제예요", "L57", "상속"),
        ("사기를 당했어요 고소할까요", "L22", "형사법"),
        ("교통사고 과실비율 분쟁이에요", "L07", "교통사고"),
        ("의료사고 당했어요", "L05", "의료법"),
    ])
    def test_nlu_to_correct_leader(self, query, expected_id, description, leaders, registry):
        result = select_swarm_leader(query, leaders)
        actual_id = _get_leader_id(registry, result)
        assert actual_id == expected_id, (
            f"[{description}] '{query}' → 기대: {expected_id}, 실제: {actual_id} ({result.get('name')})"
        )

    # 3-3. 키워드 매칭 (NLU 패턴에 없는 도메인)
    @pytest.mark.parametrize("query, expected_id, description", [
        ("특허 침해 소송 방법", "L26", "지식재산권"),
        ("스타트업 투자계약서 검토", "L15", "스타트업"),
        ("FTA 관세 혜택 문의", "L28", "관세"),
        ("환경오염 폐기물 토양 오염 피해", "L27", "환경법"),
        ("해양 수산 어업 분쟁", "L54", "수산"),
    ])
    def test_keyword_matching(self, query, expected_id, description, leaders, registry):
        result = select_swarm_leader(query, leaders)
        actual_id = _get_leader_id(registry, result)
        assert actual_id == expected_id, (
            f"[{description}] '{query}' → 기대: {expected_id}, 실제: {actual_id} ({result.get('name')})"
        )

    # 3-4. 비법률 질문 → CCO 폴백
    @pytest.mark.parametrize("query", [
        "오늘 날씨 어때요?",
        "맛있는 파스타 레시피 알려줘",
        "영화 추천해줘",
    ])
    def test_non_legal_fallback_to_cco(self, query, leaders, registry):
        result = select_swarm_leader(query, leaders)
        actual_id = _get_leader_id(registry, result)
        assert actual_id == "CCO" or result.get("_clevel") == "CCO", (
            f"비법률 질문 '{query}' → CCO 폴백 기대, 실제: {actual_id} ({result.get('name')})"
        )


# ═══════════════════════════════════════════════════════════════════
# 4. 티어 분류 (fallback)
# ═══════════════════════════════════════════════════════════════════

class TestTierClassification:
    """_fallback_tier_classification 정확성 검증"""

    @pytest.mark.parametrize("query, expected_tier, expected_complexity", [
        # Tier 1 — 단순 법률 질문
        ("전세 보증금 반환 절차", 1, "simple"),
        ("교통사고 합의금 기준", 1, "simple"),
        ("임대차 계약 해지 절차", 1, "simple"),
        # Tier 2 — 복합 법률 질문
        ("대법원 판례에 따른 임대차 분쟁 해결", 2, "complex"),
        ("대법원 판례에 따른 노동 관련 사례", 2, "complex"),
        # Tier 3 — 문서 작성 / 헌법 쟁점
        ("고소장 작성해줘", 3, "critical"),
        ("내용증명 초안 만들어줘", 3, "critical"),
        ("헌법소원 심판 청구 방법", 3, "critical"),
        ("위헌 심사 기준", 3, "critical"),
    ])
    def test_tier_assignment(self, query, expected_tier, expected_complexity, leaders):
        result = _fallback_tier_classification(query)
        assert result["tier"] == expected_tier, (
            f"'{query}' → 기대 tier: {expected_tier}, 실제: {result['tier']}"
        )
        assert result["complexity"] == expected_complexity, (
            f"'{query}' → 기대 complexity: {expected_complexity}, 실제: {result['complexity']}"
        )

    def test_tier_result_has_required_fields(self, leaders):
        result = _fallback_tier_classification("임대차 보증금 문제")
        required = ["tier", "complexity", "is_document", "leader_id", "leader_name",
                     "leader_specialty", "summary", "is_legal"]
        for field in required:
            assert field in result, f"필수 필드 '{field}' 누락"

    @pytest.mark.parametrize("query", [
        "고소장 써줘",
        "내용증명 작성해줘",
        "합의서 초안 만들어줘",
        "계약서 양식 필요해요",
    ])
    def test_document_detection(self, query, leaders):
        result = _fallback_tier_classification(query)
        assert result["is_document"] is True, (
            f"'{query}' → 문서 작성 요청인데 is_document={result['is_document']}"
        )

    @pytest.mark.parametrize("query, expected_legal", [
        ("보증금 반환 소송 절차", True),
        ("교통사고 과실 비율", True),
        ("이혼 재산 분할", True),
        ("오늘 날씨 어때", False),
        ("맛집 추천해줘", False),
        ("영화 추천 부탁", False),
    ])
    def test_legal_vs_non_legal(self, query, expected_legal, leaders):
        result = _fallback_tier_classification(query)
        assert result["is_legal"] == expected_legal, (
            f"'{query}' → 기대 is_legal: {expected_legal}, 실제: {result['is_legal']}"
        )


# ═══════════════════════════════════════════════════════════════════
# 5. 리더 커버리지 — 60개 도메인 빈틈 검사
# ═══════════════════════════════════════════════════════════════════

class TestLeaderCoverage:
    """각 주요 도메인에 대해 최소 1개 질문이 올바르게 라우팅되는지 검증"""

    @pytest.mark.parametrize("query, expected_id, domain", [
        ("민법 채권 채무 불법행위 보증인", "L01", "민사법"),
        ("소유권이전등기 절차", "L02", "부동산법"),
        ("건축허가 절차 문의", "L03", "건설법"),
        ("재개발 조합 분담금", "L04", "재개발"),
        ("의료분쟁 조정 방법", "L05", "의료법"),
        ("손해배상 금액 산정 기준", "L06", "손해배상"),
        ("교통사고 과실비율 기준", "L07", "교통사고"),
        ("전세 보증금 반환 절차", "L08", "임대차"),
        ("민사집행 강제집행 방법", "L10", "민사집행"),
        ("채권추심 독촉 대응", "L11", "채권추심"),
        ("경매 낙찰 후 명도", "L12", "경매"),
        ("회사법 이사회 책임", "L14", "회사법"),
        ("스타트업 투자계약 검토", "L15", "스타트업"),
        ("보험금 청구 거절 사유", "L16", "보험"),
        ("세금 체납 과세 문의", "L20", "세금"),
        ("형사 고소 방법 절차", "L22", "형사법"),
        ("병역 면제 조건 요건", "L25", "군형법"),
        ("특허 침해 소송", "L26", "지식재산권"),
        ("환경오염 폐기물 처리", "L27", "환경법"),
        ("노동법 부당해고 구제", "L30", "노동법"),
        ("행정처분 영업정지 이의", "L31", "행정법"),
        ("개인정보 유출 보호", "L34", "개인정보"),
        ("헌법소원 기본권 침해", "L35", "헌법"),
        ("소비자 환불 청약철회", "L38", "소비자"),
        ("이혼 양육권 친권", "L41", "가사법"),
        ("산업재해 요양급여 청구", "L43", "산재"),
        ("상속 유산 상속포기", "L57", "상속"),
    ])
    def test_domain_routing(self, query, expected_id, domain, leaders, registry):
        result = select_swarm_leader(query, leaders)
        actual_id = _get_leader_id(registry, result)
        assert actual_id == expected_id, (
            f"[{domain}] '{query}' → 기대: {expected_id}, 실제: {actual_id} ({result.get('name')})"
        )


# ═══════════════════════════════════════════════════════════════════
# 5-2. 60개 리더 전체 1:1 매칭 — 리더당 대표 질문 1개
# ═══════════════════════════════════════════════════════════════════

class TestAllLeaderRouting:
    """60개 리더 전체 — 리더당 대표 질문 1개씩 정확 라우팅 검증 (L60 제외: 폴백 전용)"""

    @pytest.mark.parametrize("query, expected_id, leader_name", [
        # L01 휘율 — 민사법
        ("민법 채권 채무 불법행위 보증인 물권", "L01", "휘율"),
        # L02 보늬 — 부동산법
        ("소유권이전등기 부동산법 절차", "L02", "보늬"),
        # L03 담슬 — 건설법
        ("건설법 건축허가 착공 시공 절차", "L03", "담슬"),
        # L04 아키 — 재개발·재건축
        ("재개발 재건축 정비사업 조합 분담금", "L04", "아키"),
        # L05 연우 — 의료법
        ("의료사고 의료분쟁 조정 병원 과오", "L05", "연우"),
        # L06 벼리 — 손해배상
        ("손해배상 위자료 배상금 과실 책임", "L06", "벼리"),
        # L07 하늬 — 교통사고
        ("교통사고 자동차 과실비율 보험금", "L07", "하늬"),
        # L08 온유 — 임대차
        ("임대차 전세 보증금 반환 세입자", "L08", "온유"),
        # L09 한울 — 국가계약
        ("국가계약 조달 입찰 낙찰 공사계약", "L09", "한울"),
        # L10 결휘 — 민사집행
        ("민사집행 강제집행 압류 가압류 배당", "L10", "결휘"),
        # L11 오름 — 채권추심
        ("채권추심 독촉 지급명령 개인회생 채무조정", "L11", "오름"),
        # L12 아슬 — 등기·경매
        ("등기 경매 공매 낙찰 명도 유찰", "L12", "아슬"),
        # L13 누리 — 상사법
        ("상사법 상법 상거래 어음 수표 상인", "L13", "누리"),
        # L14 다솜 — 회사법·M&A
        ("회사법 M&A 인수합병 이사회 주주총회", "L14", "다솜"),
        # L15 별하 — 스타트업
        ("스타트업 벤처 투자계약 스톡옵션 시드", "L15", "별하"),
        # L16 슬아 — 보험
        ("보험 보험계약 피보험자 보험사고 보험금", "L16", "슬아"),
        # L17 미르 — 국제거래
        ("국제거래 수출 수입 무역 중재 국제계약", "L17", "미르"),
        # L18 다온 — 에너지·자원
        ("에너지 자원 전력 가스 석유 신재생", "L18", "다온"),
        # L19 슬옹 — 해상·항공
        ("해상 항공 선박 항공기 운송 해운", "L19", "슬옹"),
        # L20 찬솔 — 조세·금융
        ("조세 금융 세금 국세 소득세 양도소득세", "L20", "찬솔"),
        # L21 휘윤 — IT·보안
        ("IT 보안 정보보호 해킹 사이버 네트워크", "L21", "휘윤"),
        # L22 무결 — 형사법
        ("형사 형법 고소 고발 처벌 사기 횡령", "L22", "무결"),
        # L23 가비 — 엔터테인먼트
        ("엔터테인먼트 연예 매니지먼트 방송 연예인", "L23", "가비"),
        # L24 도울 — 조세불복
        ("조세불복 조세심판 세무조사 부과처분 경정청구", "L24", "도울"),
        # L25 강무 — 군형법
        ("군형법 군대 병역 군사법원 영창 복무", "L25", "강무"),
        # L26 루다 — 지식재산권
        ("지식재산권 특허 상표 디자인 저작권 영업비밀", "L26", "루다"),
        # L27 수림 — 환경법
        ("환경법 환경오염 대기 수질 토양 폐기물", "L27", "수림"),
        # L28 해슬 — 무역·관세
        ("무역 관세 통관 수입신고 FTA", "L28", "해슬"),
        # L29 라온 — 게임·콘텐츠
        ("게임 콘텐츠 게임물 등급분류 아이템", "L29", "라온"),
        # L30 담우 — 노동법
        ("노동법 근로 해고 임금 퇴직금 근로기준법", "L30", "담우"),
        # L31 로운 — 행정법
        ("행정법 인허가 과태료 행정처분 영업정지", "L31", "로운"),
        # L32 바름 — 공정거래
        ("공정거래 독점 담합 불공정거래 시장지배적지위", "L32", "바름"),
        # L33 별이 — 우주항공
        ("우주항공 위성 발사체 궤도 항공우주", "L33", "별이"),
        # L34 지누 — 개인정보
        ("개인정보 개인정보보호 유출 GDPR 정보주체", "L34", "지누"),
        # L35 마루 — 헌법
        ("헌법 위헌 헌법소원 기본권 헌법재판소", "L35", "마루"),
        # L36 단아 — 문화·종교
        ("문화 종교 문화재 전통 사찰 교회", "L36", "단아"),
        # L37 예솔 — 소년법
        ("소년법 청소년 미성년자 소년범 보호처분", "L37", "예솔"),
        # L38 슬비 — 소비자
        ("소비자 소비자보호 제조물책임 환불 약관", "L38", "슬비"),
        # L39 가온 — 정보통신
        ("정보통신 통신 전기통신 방송통신", "L39", "가온"),
        # L40 한결 — 인권
        ("인권 차별 평등 인권침해", "L40", "한결"),
        # L41 산들 — 이혼·가족
        ("이혼 가족 양육권 양육비 친권 재산분할", "L41", "산들"),
        # L42 하람 — 저작권
        ("저작권 저작물 저작자 복제 전송", "L42", "하람"),
        # L43 해나 — 산업재해
        ("산업재해 산재 업무상재해 요양급여 장해급여", "L43", "해나"),
        # L44 보람 — 사회복지
        ("사회복지 복지 사회보장 기초생활 복지시설", "L44", "보람"),
        # L45 이룸 — 교육·청소년
        ("교육 학교 학교폭력 교육청 학생", "L45", "이룸"),
        # L46 다올 — 보험·연금
        ("연금 국민연금 퇴직연금 기금", "L46", "다올"),
        # L47 새론 — 벤처·신산업
        ("벤처 신산업 규제샌드박스 신기술", "L47", "새론"),
        # L48 나래 — 문화예술
        ("문화예술 예술 예술인 공연 전시", "L48", "나래"),
        # L49 가람 — 식품·보건
        ("식품 보건 식약처 위생 의약품", "L49", "가람"),
        # L50 빛나 — 다문화·이주
        ("다문화 이주 외국인 결혼이민 난민", "L50", "빛나"),
        # L51 소울 — 종교·전통
        ("종교 전통 사찰 교회 종단", "L51", "소울"),
        # L52 미소 — 광고·언론
        ("광고 언론 방송 신문 명예훼손 SNS", "L52", "미소"),
        # L53 늘솔 — 농림·축산
        ("농림 축산 농업 축산업 농지 가축", "L53", "늘솔"),
        # L54 이서 — 해양·수산
        ("해양 수산 어업 어선 수산물", "L54", "이서"),
        # L55 윤빛 — 과학기술
        ("과학기술 연구개발 R&D 기술이전", "L55", "윤빛"),
        # L56 다인 — 장애인·복지
        ("장애인 복지 장애 장애인권익", "L56", "다인"),
        # L57 세움 — 상속·신탁
        ("상속 신탁 유산 유언장 상속포기 유류분", "L57", "세움"),
        # L58 예온 — 스포츠·레저
        ("스포츠 레저 체육 운동선수 도핑", "L58", "예온"),
        # L59 한빛 — 데이터·AI윤리
        ("데이터 AI윤리 인공지능 알고리즘 빅데이터", "L59", "한빛"),
    ])
    def test_leader_routing(self, query, expected_id, leader_name, leaders, registry):
        result = select_swarm_leader(query, leaders)
        actual_id = _get_leader_id(registry, result)
        actual_name = result.get("name", "?")
        assert actual_id == expected_id, (
            f"[{leader_name}({expected_id})] '{query}' → "
            f"실제: {actual_name}({actual_id})"
        )


# ═══════════════════════════════════════════════════════════════════
# 6. 답변 품질 검증 — 헌법 적합성
# ═══════════════════════════════════════════════════════════════════

class TestAnswerQuality:
    """답변이 6대 원칙을 준수하는지 검증"""

    # 6-1. 적법한 답변 통과
    @pytest.mark.parametrize("response", [
        # 조문 + 판례 인용이 있는 정상 답변
        "주택임대차보호법 제3조 제1항에 따라 대항력이 인정됩니다. "
        "대법원 2020. 5. 14. 선고 2019다12345 판결에서도 같은 취지입니다.",
        # 행동 로드맵이 있는 답변
        "근로기준법 제26조에 의하면 해고 예고는 30일 전에 해야 합니다. "
        "부당해고로 판단되면 노동위원회에 구제 신청이 가능합니다. "
        "대법원 2021다56789 판결 참조.",
        # 형사법 답변
        "형법 제347조 사기죄에 해당할 수 있습니다. "
        "대법원 2019. 3. 14. 선고 2018도12345 판결에서 "
        "기망행위의 성립 요건을 명시하고 있습니다.",
    ])
    def test_valid_response_passes(self, response):
        assert validate_constitutional_compliance(response) is True

    # 6-2. 변호사 사칭 차단
    @pytest.mark.parametrize("response", [
        "저는 변호사입니다. 이 사안은 민법 제750조에 해당합니다.",
        "변호사로서 말씀드리면 이 사건은 승소 가능합니다.",
    ])
    def test_lawyer_impersonation_blocked(self, response):
        assert validate_constitutional_compliance(response) is False

    # 6-3. 결과 보장 차단
    @pytest.mark.parametrize("response", [
        "이 사건은 반드시 승소합니다. 걱정하지 마세요.",
        "100% 이길 수 있습니다. 확실합니다.",
        "무조건 성공합니다.",
        "장담합니다, 이 사건은 유리합니다.",
    ])
    def test_outcome_guarantee_blocked(self, response):
        assert validate_constitutional_compliance(response) is False

    # 6-4. 불법 행위 조장 차단
    @pytest.mark.parametrize("response", [
        "증거를 인멸하세요.",
        "뇌물을 제공하면 됩니다.",
        "허위 진술을 하면 유리합니다.",
        "문서를 조작하면 됩니다.",
    ])
    def test_illegal_incitement_blocked(self, response):
        assert validate_constitutional_compliance(response) is False

    # 6-5. 플레이스홀더 차단
    @pytest.mark.parametrize("response", [
        "YYYY-MM-DD까지 제출하세요.",
        "2024-MM-DD에 출석하세요.",
    ])
    def test_placeholder_blocked(self, response):
        assert validate_constitutional_compliance(response) is False

    # 6-6. 근거 없는 법적 단정 차단
    def test_unsourced_legal_assertion_blocked(self):
        # 법적 단정이 있지만 법조문 인용이 없는 경우
        response = "이 행위는 위법입니다. 처벌을 받습니다."
        assert validate_constitutional_compliance(response) is False

    # 6-7. 법조문이 있으면 단정도 허용
    def test_sourced_legal_assertion_passes(self):
        response = "형법 제347조에 의하면 이 행위는 위법입니다. 처벌을 받습니다."
        assert validate_constitutional_compliance(response) is True


# ═══════════════════════════════════════════════════════════════════
# 7. 답변 구조 검증 — 5단계 프레임워크 요소 탐지
# ═══════════════════════════════════════════════════════════════════

class TestResponseStructure:
    """Lawmadi OS 5단계 프레임워크 구성 요소 감지 유틸리티 검증"""

    def _check_structure(self, text: str) -> dict:
        """답변 텍스트에서 5단계 프레임워크 요소를 감지"""
        import re
        return {
            "has_law_reference": bool(re.search(r'제\d+조', text)),
            "has_precedent": bool(re.search(r'(대법원|헌법재판소|판결|선고)\s*\d', text)),
            "has_action_guide": any(kw in text for kw in [
                "▶", "지금 할 일", "이번 주", "1단계", "□", "체크리스트",
            ]),
            "has_safety_net": any(kw in text for kw in [
                "132", "법률구조공단", "무료 상담", "나홀로소송", "110",
            ]),
            "has_empathy": any(kw in text for kw in [
                "당연합니다", "충분히", "걱정", "불안", "어려우",
            ]),
        }

    def test_ideal_response_has_all_elements(self):
        """claude.md 응답 예시 수준의 답변이 모든 요소를 포함"""
        response = (
            "지금 많이 답답하시죠. 당연합니다. "
            "주택임대차보호법 제3조 제1항에 따라 대항력이 인정됩니다. "
            "대법원 2020. 5. 14. 선고 2019다12345 판결 참조. "
            "▶ 지금 할 일: 내용증명 발송 "
            "혼자 어려우시면 대한법률구조공단(132)에 무료 상담 신청하세요."
        )
        result = self._check_structure(response)
        assert result["has_law_reference"], "법조문 인용 없음"
        assert result["has_precedent"], "판례 인용 없음"
        assert result["has_action_guide"], "행동 로드맵 없음"
        assert result["has_safety_net"], "안전망 안내 없음"
        assert result["has_empathy"], "감정 수용 없음"

    def test_law_only_response_partial(self):
        """법조문만 있는 답변은 부분 통과"""
        response = "민법 제750조에 따라 손해배상이 가능합니다."
        result = self._check_structure(response)
        assert result["has_law_reference"]
        assert not result["has_action_guide"]

    def test_empathy_only_response_partial(self):
        """감정만 있는 답변은 부분 통과"""
        response = "많이 걱정되시죠. 충분히 그러실 수 있습니다."
        result = self._check_structure(response)
        assert result["has_empathy"]
        assert not result["has_law_reference"]


# ═══════════════════════════════════════════════════════════════════
# 8. 교차 도메인 충돌 해결 — 7개 충돌 쌍 정밀 검증
# ═══════════════════════════════════════════════════════════════════

class TestCrossDomainConflictResolution:
    """7개 교차 도메인 충돌 쌍에서 정확한 우선순위 적용 검증"""

    # ── 1. L01(민사) vs L06(손해배상) ──
    @pytest.mark.parametrize("query, expected", [
        ("피해 배상 방법 알려주세요", "L06"),
        ("불법행위로 다친 피해 보상", "L06"),
        ("계약 위반으로 손해배상 소송", "L01"),
    ])
    def test_civil_vs_damages(self, query, expected):
        result = _nlu_detect_intent(query)
        assert result == expected, f"'{query}' → 기대: {expected}, 실제: {result}"

    # ── 2. L08(임대차) vs L02(부동산) ──
    @pytest.mark.parametrize("query, expected", [
        ("아파트 전세 보증금 반환", "L08"),
        ("아파트 매매 명의이전", "L02"),
        ("건물 명의 이전 절차", "L02"),
    ])
    def test_lease_vs_property(self, query, expected, leaders, registry):
        result = select_swarm_leader(query, leaders)
        actual = _get_leader_id(registry, result)
        assert actual == expected, f"'{query}' → 기대: {expected}, 실제: {actual}"

    # ── 3. L22(형사) vs L11(채권추심) — 사기 vs 채무불이행 ──
    @pytest.mark.parametrize("query, expected", [
        ("돈 빌려줬는데 안 갚아요", "L22"),
        ("돈 빌려줬는데 갚을 생각이 없었대요", "L22"),
        ("빚이 많아서 못 갚겠다고 해요", "L11"),
        ("사채업자가 독촉 전화를 매일 해요", "L11"),
    ])
    def test_fraud_vs_debt(self, query, expected, leaders, registry):
        result = select_swarm_leader(query, leaders)
        actual = _get_leader_id(registry, result)
        assert actual == expected, f"'{query}' → 기대: {expected}, 실제: {actual}"

    # ── 4. L30(노동) vs L43(산재) ──
    @pytest.mark.parametrize("query, expected", [
        ("직장 내 괴롭힘으로 우울증 산재 신청", "L43"),
        ("직장에서 괴롭힘 당했어요", "L30"),
        ("과로로 쓰러졌는데 산재 인정되나요", "L43"),
        ("회사에서 부당해고 당했어요", "L30"),
    ])
    def test_labor_vs_industrial(self, query, expected, leaders, registry):
        result = select_swarm_leader(query, leaders)
        actual = _get_leader_id(registry, result)
        assert actual == expected, f"'{query}' → 기대: {expected}, 실제: {actual}"

    # ── 5. L20(세금) vs L57(상속) ──
    @pytest.mark.parametrize("query, expected", [
        ("상속세 신고 방법", "L20"),
        ("부모님 유산 상속 절차", "L57"),
        ("상속 포기하면 상속세 안 내도 되나요", "L57"),
    ])
    def test_tax_vs_inheritance(self, query, expected, leaders, registry):
        result = select_swarm_leader(query, leaders)
        actual = _get_leader_id(registry, result)
        assert actual == expected, f"'{query}' → 기대: {expected}, 실제: {actual}"

    # ── 6. L37(학교폭력) vs L22(형사) ──
    @pytest.mark.parametrize("query, expected", [
        ("학교에서 아이가 맞았어요", "L37"),
        ("학폭 가해자 형사처벌 가능한가요", "L37"),
        ("미성년자가 폭행당했어요", "L37"),
        ("성인한테 폭행당했어요", "L22"),
    ])
    def test_school_violence_vs_criminal(self, query, expected, leaders, registry):
        result = select_swarm_leader(query, leaders)
        actual = _get_leader_id(registry, result)
        assert actual == expected, f"'{query}' → 기대: {expected}, 실제: {actual}"

    # ── 7. L42(저작권) vs L52(광고·언론) ──
    @pytest.mark.parametrize("query, expected", [
        ("블로그 사진을 업체가 광고에 무단 사용", "L42"),
        ("SNS에 허위사실 유포", "L52"),
        ("유튜브 영상을 무단 복제", "L42"),
        ("인터넷 블로그에서 명예훼손", "L52"),
    ])
    def test_copyright_vs_media(self, query, expected, leaders, registry):
        result = select_swarm_leader(query, leaders)
        actual = _get_leader_id(registry, result)
        assert actual == expected, f"'{query}' → 기대: {expected}, 실제: {actual}"


# ═══════════════════════════════════════════════════════════════════
# 9. 새로 추가된 NLU 패턴 검증
# ═══════════════════════════════════════════════════════════════════

class TestNewNLUPatterns:
    """L04(재개발), L14(회사법), L16(보험), L26(지식재산권) NLU 패턴 + L02/L22 보강"""

    # ── L04: 재개발·재건축 ──
    @pytest.mark.parametrize("query, expected", [
        ("재개발 조합 분담금 문제", "L04"),
        ("재건축 입주권 문제", "L04"),
        ("정비사업 조합원 분쟁 어떻게", "L04"),
    ])
    def test_redevelopment(self, query, expected, leaders, registry):
        result = select_swarm_leader(query, leaders)
        actual = _get_leader_id(registry, result)
        assert actual == expected, f"'{query}' → 기대: {expected}, 실제: {actual}"

    # ── L14: 회사법 ──
    @pytest.mark.parametrize("query, expected", [
        ("이사 배임 책임 어떻게", "L14"),
        ("소수주주 대표소송 방법 어떻게", "L14"),
        ("회사 합병 절차 어떻게", "L14"),
    ])
    def test_corporate_law(self, query, expected, leaders, registry):
        result = select_swarm_leader(query, leaders)
        actual = _get_leader_id(registry, result)
        assert actual == expected, f"'{query}' → 기대: {expected}, 실제: {actual}"

    # ── L16: 보험 ──
    @pytest.mark.parametrize("query, expected", [
        ("보험금 거절당했어요 어떻게", "L16"),
        ("보험사가 지급 거부해요 어떻게", "L16"),
        ("보험 약관 불공정 분쟁", "L16"),
    ])
    def test_insurance(self, query, expected, leaders, registry):
        result = select_swarm_leader(query, leaders)
        actual = _get_leader_id(registry, result)
        assert actual == expected, f"'{query}' → 기대: {expected}, 실제: {actual}"

    # ── L26: 지식재산권 ──
    @pytest.mark.parametrize("query, expected", [
        ("특허 침해 소송 어떻게", "L26"),
        ("상표 도용 침해 어떻게", "L26"),
        ("영업 비밀 유출 어떻게", "L26"),
    ])
    def test_intellectual_property(self, query, expected, leaders, registry):
        result = select_swarm_leader(query, leaders)
        actual = _get_leader_id(registry, result)
        assert actual == expected, f"'{query}' → 기대: {expected}, 실제: {actual}"

    # ── L02: 부동산 보강 (분양권·재건축입주권) ──
    @pytest.mark.parametrize("query, expected", [
        ("분양권 전매 방법", "L02"),
        ("아파트 분양권 전매", "L02"),
    ])
    def test_property_enhanced(self, query, expected, leaders, registry):
        result = select_swarm_leader(query, leaders)
        actual = _get_leader_id(registry, result)
        assert actual == expected, f"'{query}' → 기대: {expected}, 실제: {actual}"

    # ── L22: 형사법 보강 (음주운전·양형) ──
    @pytest.mark.parametrize("query, expected", [
        ("음주운전 적발됐어요 어떻게", "L22"),
        ("자수하면 양형 어떻게 되나요", "L22"),
    ])
    def test_criminal_enhanced(self, query, expected, leaders, registry):
        result = select_swarm_leader(query, leaders)
        actual = _get_leader_id(registry, result)
        assert actual == expected, f"'{query}' → 기대: {expected}, 실제: {actual}"

    # ── L10: 민사집행 vs L01 키워드 충돌 해결 ──
    def test_civil_execution_not_civil(self, leaders, registry):
        result = select_swarm_leader("민사집행 강제집행 방법", leaders)
        actual = _get_leader_id(registry, result)
        assert actual == "L10", f"'민사집행 강제집행 방법' → 기대: L10, 실제: {actual}"


# ═══════════════════════════════════════════════════════════════════
# 10. 엣지 케이스 — 경계 상황 처리
# ═══════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """비정상/경계 입력 안정성 검증"""

    def test_empty_query_does_not_crash(self, leaders):
        result = select_swarm_leader("", leaders)
        assert result is not None
        assert "name" in result or "_clevel" in result

    def test_very_long_query(self, leaders):
        query = "보증금 반환 " * 500  # 3000자 이상
        result = select_swarm_leader(query, leaders)
        assert result is not None

    def test_special_characters(self, leaders):
        result = select_swarm_leader("!@#$%^&*()_+{}|:<>?", leaders)
        assert result is not None

    def test_mixed_domains_query(self, leaders, registry):
        """여러 도메인이 섞인 질문 — 크래시 없이 어떤 리더든 반환"""
        query = "남편이 사업하다 세금 체납되고 이혼하려는데 아파트 경매"
        result = select_swarm_leader(query, leaders)
        assert result is not None
        leader_id = _get_leader_id(registry, result)
        assert leader_id != "UNKNOWN", f"리더 미매칭: {result}"

    def test_nlu_returns_none_for_gibberish(self):
        assert _nlu_detect_intent("ㅋㅋㅋㅋ") is None
        assert _nlu_detect_intent("asdfghjkl") is None

    def test_constitutional_empty_response(self):
        assert validate_constitutional_compliance("") is False
        assert validate_constitutional_compliance("짧음") is False
        assert validate_constitutional_compliance(None) is False
