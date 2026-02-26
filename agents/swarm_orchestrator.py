#!/usr/bin/env python3
"""
Lawmadi OS Swarm Orchestrator
진정한 60 Leader 협업 아키텍처

Chapter 3 구현:
- 여러 Leader가 동시에 문제 분석
- 각 Leader의 전문 분야 사고방식 적용
- 결과를 조합하여 최종 판단 흐름 구성
"""
import json
import os
import logging
import time
import threading
from typing import Dict, List, Tuple, Optional
from google import genai
from google.genai import types as genai_types
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger("LawmadiOS.SwarmOrchestrator")

# Gemini 모델 상수 — core.constants 단일 소스
from core.constants import GEMINI_MODEL
from core.model_fallback import get_model, on_quota_error, is_quota_error
_DEFAULT_MODEL = GEMINI_MODEL  # 정적 기본값 (하위호환)

# =============================================================
# 📦 법률명 → 리더 매핑 (law_cache.json 기반)
# =============================================================
LAW_TO_LEADER = {
    # L01 휘율 (민사법)
    "민법": "L01", "민사소송법": "L01",
    # L02 보늬 (부동산법)
    "부동산등기법": "L02", "부동산실명법": "L02", "공인중개사법": "L02",
    # L03 담슬 (건설법)
    "건설산업기본법": "L03", "건축법": "L03", "하도급법": "L03",
    # L04 아키 (재개발·재건축)
    "도시정비법": "L04", "도시개발법": "L04",
    # L05 연우 (의료법)
    "의료법": "L05", "약사법": "L05",
    # L06 벼리 (손해배상)
    "국가배상법": "L06", "제조물책임법": "L06",
    # L07 하늬 (교통사고)
    "교통사고처리특례법": "L07", "도로교통법": "L07", "자동차손해배상보장법": "L07",
    # L08 온유 (임대차)
    "주택임대차보호법": "L08", "상가건물임대차보호법": "L08",
    # L09 한울 (국가계약)
    "국가계약법": "L09", "지방계약법": "L09",
    # L10 결휘 (민사집행)
    "민사집행법": "L10",
    # L12 아슬 (등기·경매)
    "부동산경매법": "L12",
    # L11 오름 (채권추심)
    "채권추심법": "L11", "신용정보법": "L11",
    # L13 누리 (상사법)
    "상법": "L13", "자본시장법": "L13",
    # L14 다솜 (회사법·M&A)
    "법인세법": "L14", "주식회사법": "L14",
    # L15 별하 (스타트업)
    "중소기업기본법": "L15", "외국인투자촉진법": "L15",
    # L16 슬아 (보험)
    "보험업법": "L16",
    # L17 미르 (국제거래)
    "국제사법": "L17", "대외무역법": "L17",
    # L18 다온 (에너지·자원)
    "에너지법": "L18", "전기사업법": "L18",
    # L19 슬옹 (해상·항공)
    "항공사업법": "L19", "해상교통안전법": "L19", "선박안전법": "L19", "해운법": "L19",
    # L20 찬솔 (조세·금융)
    "소득세법": "L20", "부가가치세법": "L20", "국세기본법": "L20", "지방세법": "L20",
    # L21 휘윤 (IT·보안)
    "정보통신망법": "L21", "전자서명법": "L21", "데이터산업법": "L21",
    # L22 무결 (형사법)
    "형법": "L22", "형사소송법": "L22",
    # L23 가비 (엔터테인먼트)
    "대중문화예술산업발전법": "L23", "공연법": "L23",
    # L24 도울 (조세불복)
    "조세범처벌법": "L24",
    # L25 강무 (군형법)
    "군형법": "L25", "군사법원법": "L25",
    # L26 루다 (지식재산권)
    "특허법": "L26", "디자인보호법": "L26", "상표법": "L26",
    # L27 수림 (환경법)
    "환경정책기본법": "L27", "환경영향평가법": "L27", "대기환경보전법": "L27",
    # L28 해슬 (무역·관세)
    "관세법": "L28", "자유무역협정관세특례법": "L28",
    # L29 라온 (게임·콘텐츠)
    "게임산업진흥법": "L29", "콘텐츠산업진흥법": "L29",
    # L30 담우 (노동법)
    "근로기준법": "L30", "노동조합법": "L30",
    # L31 로운 (행정법)
    "행정소송법": "L31", "행정심판법": "L31", "행정절차법": "L31",
    "국가공무원법": "L31", "지방공무원법": "L31",
    # L32 바름 (공정거래)
    "공정거래법": "L32", "하도급공정화법": "L32", "가맹사업법": "L32",
    # L33 별이 (우주항공)
    "우주개발진흥법": "L33", "우주손해배상법": "L33", "항공우주산업개발촉진법": "L33",
    # L34 지누 (개인정보)
    "개인정보보호법": "L34",
    # L35 마루 (헌법)
    "헌법": "L35", "헌법재판소법": "L35",
    # L36 단아 (문화·종교)
    "문화재보호법": "L36", "종교단체법": "L36",
    # L37 예솔 (소년법)
    "소년법": "L37", "청소년보호법": "L37", "아동학대처벌법": "L37", "아동복지법": "L37",
    # L38 슬비 (소비자)
    "소비자기본법": "L38", "전자상거래법": "L38",
    # L39 가온 (정보통신)
    "전기통신사업법": "L39", "전파법": "L39", "방송통신위원회법": "L39",
    # L40 한결 (인권)
    "국가인권위원회법": "L40",
    # L41 산들 (이혼·가족)
    "가사소송법": "L41", "가족관계등록법": "L41",
    # L42 하람 (저작권)
    "저작권법": "L42",
    # L43 해나 (산업재해)
    "산업재해보상보험법": "L43", "산업안전보건법": "L43", "중대재해처벌법": "L43",
    # L44 보람 (사회복지)
    "사회보장기본법": "L44", "국민기초생활보장법": "L44",
    # L45 이룸 (교육·청소년)
    "교육기본법": "L45", "초중등교육법": "L45", "학원법": "L45",
    # L46 다올 (보험·연금)
    "국민연금법": "L46", "국민건강보험법": "L46", "국민건강증진법": "L46",
    # L47 새론 (벤처·신산업)
    "규제자유특구법": "L47", "산업융합촉진법": "L47",
    # L48 나래 (문화예술)
    "문화예술진흥법": "L48", "예술인복지법": "L48",
    # L49 가람 (식품·보건)
    "식품위생법": "L49", "식품안전기본법": "L49",
    # L50 빛나 (다문화·이주)
    "다문화가족지원법": "L50", "출입국관리법": "L50", "국적법": "L50", "난민법": "L50",
    # L51 소울 (종교·전통)
    "전통사찰보존법": "L51",
    # L52 미소 (광고·언론·명예훼손)
    "언론중재법": "L52", "정보통신망이용촉진및정보보호등에관한법률": "L52", "정보통신망법": "L52",
    # L53 늘솔 (농림·축산)
    "농지법": "L53", "농업협동조합법": "L53", "축산법": "L53",
    # L54 이서 (해양·수산)
    "수산업법": "L54", "해양환경관리법": "L54",
    # L55 윤빛 (과학기술)
    "과학기술기본법": "L55", "국가연구개발혁신법": "L55", "발명진흥법": "L55",
    # L56 다인 (장애인·복지)
    "장애인복지법": "L56", "장애인차별금지법": "L56", "장애인고용촉진법": "L56",
    # L57 세움 (상속·신탁)
    "상속세및증여세법": "L57", "신탁법": "L57",
    # L58 예온 (스포츠·레저)
    "국민체육진흥법": "L58", "스포츠기본법": "L58", "체육시설법": "L58",
    # L59 한빛 (데이터·AI윤리)
    "인공지능법": "L59", "데이터산업기본법": "L59",
}

# 키워드 기반 리더 매핑 패턴 (exact match 실패 시 fallback)
# (substring_keyword, leader_id) — 우선순위 순서
_LEADER_KEYWORD_PATTERNS = [
    ("민법", "L01"), ("민사", "L01"),
    ("부동산등기", "L02"), ("부동산실명", "L02"), ("공인중개사", "L02"),
    ("부동산", "L02"), ("토지", "L02"),
    ("건설산업", "L03"), ("건축법", "L03"), ("하도급", "L03"),
    ("건설", "L03"), ("건축", "L03"),
    ("도시정비", "L04"), ("도시개발", "L04"), ("재개발", "L04"), ("재건축", "L04"),
    ("의료법", "L05"), ("약사법", "L05"), ("의료", "L05"), ("약사", "L05"),
    ("국가배상", "L06"), ("손해배상", "L06"),
    ("교통사고처리", "L07"), ("도로교통", "L07"), ("자동차손해", "L07"), ("교통", "L07"),
    ("주택임대차", "L08"), ("상가건물임대차", "L08"), ("임대차", "L08"), ("임대", "L08"),
    ("국가계약", "L09"), ("지방계약", "L09"), ("조달", "L09"),
    ("민사집행", "L10"), ("강제집행", "L10"),
    ("채권추심", "L11"), ("신용정보", "L11"),
    ("경매", "L12"), ("법원경매", "L12"), ("공매", "L12"), ("임의경매", "L12"),
    ("상법", "L13"), ("자본시장", "L13"), ("상사", "L13"),
    ("법인세", "L14"), ("법인", "L14"), ("합병", "L14"),
    ("중소기업", "L15"), ("외국인투자", "L15"), ("스타트업", "L15"), ("벤처", "L15"),
    ("보험업", "L16"), ("보험", "L16"),
    ("국제사법", "L17"), ("대외무역", "L17"), ("국제", "L17"),
    ("에너지법", "L18"), ("전기사업", "L18"), ("에너지", "L18"), ("원자력", "L18"),
    ("항공사업", "L19"), ("항공", "L19"), ("해운", "L19"),
    ("소득세", "L20"), ("부가가치세", "L20"), ("국세기본", "L20"),
    ("지방세", "L20"), ("조세", "L20"), ("세금", "L20"),
    ("정보통신망", "L21"), ("전자서명", "L21"), ("데이터산업", "L21"),
    ("정보보호", "L21"), ("사이버", "L21"),
    ("형법", "L22"), ("형사소송", "L22"), ("형사", "L22"),
    ("대중문화예술", "L23"), ("공연법", "L23"), ("연예", "L23"), ("엔터테인먼트", "L23"),
    ("조세범처벌", "L24"), ("조세불복", "L24"),
    ("군형법", "L25"), ("군사법원", "L25"), ("군사", "L25"),
    ("특허법", "L26"), ("디자인보호", "L26"), ("상표법", "L26"),
    ("특허", "L26"), ("상표", "L26"),
    ("환경정책", "L27"), ("환경영향", "L27"), ("대기환경", "L27"),
    ("수질환경", "L27"), ("폐기물", "L27"), ("환경", "L27"),
    ("관세법", "L28"), ("관세", "L28"), ("무역", "L28"), ("수출입", "L28"),
    ("게임산업", "L29"), ("게임", "L29"), ("콘텐츠", "L29"),
    ("근로기준", "L30"), ("노동조합", "L30"),
    ("근로", "L30"), ("노동", "L30"),
    ("행정소송", "L31"), ("행정심판", "L31"), ("행정절차", "L31"),
    ("국가공무원", "L31"), ("지방공무원", "L31"), ("행정", "L31"),
    ("공정거래", "L32"), ("독점규제", "L32"), ("가맹", "L32"),
    ("우주항공", "L33"), ("항공우주", "L33"), ("드론", "L33"), ("우주", "L33"),
    ("개인정보보호", "L34"), ("개인정보", "L34"),
    ("헌법재판소", "L35"), ("헌법", "L35"),
    ("문화재보호", "L36"), ("문화재", "L36"), ("문화유산", "L36"),
    ("소년법", "L37"), ("청소년보호", "L37"), ("아동학대", "L37"), ("아동복지", "L37"),
    ("아동", "L37"), ("청소년", "L37"),
    ("소비자기본", "L38"), ("전자상거래", "L38"), ("소비자", "L38"),
    ("전기통신사업", "L39"), ("전기통신", "L39"), ("통신", "L39"),
    ("국가인권위원회", "L40"), ("인권", "L40"), ("차별금지", "L40"),
    ("가사소송", "L41"), ("가족관계", "L41"), ("혼인", "L41"), ("가사", "L41"),
    ("저작권법", "L42"), ("저작권", "L42"), ("저작", "L42"),
    ("산업안전보건", "L43"), ("중대재해", "L43"),
    ("산업재해보상", "L43"), ("산업재해", "L43"), ("산재", "L43"),
    ("사회보장기본", "L44"), ("국민기초생활", "L44"), ("사회보장", "L44"), ("복지", "L44"),
    ("교육기본", "L45"), ("학교폭력", "L45"), ("교육", "L45"),
    ("국민연금", "L46"), ("국민건강보험", "L46"), ("건강보험", "L46"), ("연금", "L46"),
    ("규제샌드박스", "L47"), ("신산업특례", "L47"), ("혁신", "L47"),
    ("문화예술진흥", "L48"), ("예술인", "L48"), ("문화예술", "L48"),
    ("식품위생", "L49"), ("식품안전", "L49"), ("식품", "L49"), ("보건", "L49"),
    ("다문화가족", "L50"), ("출입국관리", "L50"), ("국적법", "L50"),
    ("출입국", "L50"), ("이민", "L50"), ("난민", "L50"), ("비자", "L50"),
    ("전통사찰", "L51"), ("종교", "L51"), ("사찰", "L51"),
    ("언론중재", "L52"), ("방송법", "L52"), ("광고", "L52"), ("언론", "L52"), ("명예훼손", "L52"), ("정보통신망", "L52"), ("비방", "L52"),
    ("농지법", "L53"), ("농업협동", "L53"), ("축산법", "L53"),
    ("농지", "L53"), ("농업", "L53"), ("축산", "L53"),
    ("수산업", "L54"), ("해양환경", "L54"), ("어업", "L54"), ("수산", "L54"),
    ("과학기술기본", "L55"), ("연구개발", "L55"), ("과학기술", "L55"),
    ("장애인복지", "L56"), ("장애인차별", "L56"), ("장애인", "L56"),
    ("상속세및증여세", "L57"), ("신탁법", "L57"), ("상속", "L57"), ("증여", "L57"),
    ("국민체육진흥", "L58"), ("체육", "L58"), ("스포츠", "L58"),
    ("인공지능", "L59"), ("AI윤리", "L59"), ("알고리즘", "L59"),
    ("데이터기본법", "L59"), ("AI규제", "L59"),
]


def resolve_leaders_from_ssot(ssot_sources: list) -> Dict[str, int]:
    """
    SSOT 매칭 결과에서 리더별 점수를 산출 (3-tier 매칭).
    Returns: {leader_id: boost_score}
    """
    leader_boost = {}
    if not ssot_sources:
        return leader_boost
    for src in ssot_sources:
        law_name = src.get("law", "")
        ssot_score = src.get("score", 0)
        boost = 30 if ssot_score >= 50 else 20

        # Tier 1: exact match
        leader_id = LAW_TO_LEADER.get(law_name)

        # Tier 2: prefix/base match (시행령/시행규칙 등 하위법령)
        if not leader_id:
            for base_law, lid in LAW_TO_LEADER.items():
                if law_name.startswith(base_law) or base_law.startswith(law_name):
                    leader_id = lid
                    break

        # Tier 3: keyword fallback
        if not leader_id:
            for keyword, lid in _LEADER_KEYWORD_PATTERNS:
                if keyword in law_name:
                    leader_id = lid
                    break

        if leader_id:
            leader_boost[leader_id] = leader_boost.get(leader_id, 0) + boost
    return leader_boost


# 동일 도메인 충돌 방지: 같은 그룹에서 최고점 1명만 선택
_LEADER_EXCLUSION_GROUPS: List[frozenset] = [
    frozenset({"L20", "L24"}),   # 조세 vs 조세불복
    frozenset({"L26", "L42"}),   # IP/특허 vs 저작권
    frozenset({"L30", "L43"}),   # 노동법 vs 산업재해
    frozenset({"L44", "L46"}),   # 사회복지 vs 연금/건강보험
    frozenset({"L22", "L25"}),   # 형사법 vs 군형법
    frozenset({"L27", "L54"}),   # 환경법 vs 해양환경
    frozenset({"L31", "L35"}),   # 행정법 vs 헌법
]
_MIN_LEADER_SCORE = 10          # 최소 점수 임계값
_SCORE_RATIO_THRESHOLD = 0.45   # 2위 이하: 1위 점수의 45% 이상


def _resolve_leader_conflicts(
    domains: List[Tuple[str, int]]
) -> List[Tuple[str, int]]:
    """충돌 리더 제거: exclusion group에서 최고점 1명만 유지"""
    if not domains:
        return domains
    group_winners: Dict[int, Tuple[str, int]] = {}
    for leader_id, score in domains:
        for g_idx, group in enumerate(_LEADER_EXCLUSION_GROUPS):
            if leader_id in group:
                if g_idx not in group_winners or score > group_winners[g_idx][1]:
                    group_winners[g_idx] = (leader_id, score)
                break
    winner_ids = {v[0] for v in group_winners.values()}
    result = []
    for leader_id, score in domains:
        in_group = any(leader_id in g for g in _LEADER_EXCLUSION_GROUPS)
        if not in_group or leader_id in winner_ids:
            result.append((leader_id, score))
    return result


class GeminiCircuitBreaker:
    """Gemini API Circuit Breaker — CLOSED/OPEN/HALF_OPEN 3-state"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self._lock = threading.Lock()
        self._failure_count = 0
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._last_failure_time = 0.0

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == "OPEN" and time.time() - self._last_failure_time >= self._recovery_timeout:
                self._state = "HALF_OPEN"
            return self._state

    def allow_request(self) -> bool:
        s = self.state
        return s in ("CLOSED", "HALF_OPEN")

    def record_success(self):
        with self._lock:
            self._failure_count = 0
            self._state = "CLOSED"

    def record_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self._failure_threshold:
                self._state = "OPEN"
                logger.warning(f"🔴 [CircuitBreaker] OPEN — {self._failure_count}회 연속 실패, {self._recovery_timeout}초 후 재시도")


# 전역 Circuit Breaker 인스턴스 (config.json 값으로 초기화됨 — SwarmOrchestrator.__init__에서 갱신)
_gemini_cb = GeminiCircuitBreaker(failure_threshold=3, recovery_timeout=30)


class SwarmOrchestrator:
    """
    60 Leader Swarm 오케스트레이터

    역할:
    1. Query 분석 → 관련 법률 도메인 탐지
    2. 도메인별 전문 Leader 자동 선택
    3. 다중 Leader 병렬 분석 실행
    4. 결과 통합 → 종합 판단 흐름 생성
    """

    def __init__(self, leaders_registry: Dict, config: Dict = None, genai_client=None):
        global _gemini_cb
        self.leaders = leaders_registry
        self.config = config or {}
        self.genai_client = genai_client

        # config.json의 circuit_breaker 설정 읽기
        cb_config = (self.config
                     .get("network_security", {})
                     .get("circuit_breaker", {})
                     .get("per_provider", {})
                     .get("LAW_GO_KR_DRF", {}))
        cb_threshold = cb_config.get("failure_threshold", 3)
        cb_timeout_s = cb_config.get("reset_timeout_ms", 30000) // 1000
        _gemini_cb = GeminiCircuitBreaker(failure_threshold=cb_threshold, recovery_timeout=cb_timeout_s)

        # Leader별 도메인 키워드 매핑
        self._build_domain_index()

        # Swarm 모드 설정
        self.swarm_enabled = os.getenv("SWARM_ENABLED", "true").lower() == "true"
        self.max_leaders = int(os.getenv("SWARM_MAX_LEADERS", "3"))
        self.min_leaders = int(os.getenv("SWARM_MIN_LEADERS", "1"))

        logger.info(f"✅ SwarmOrchestrator initialized: {len(self.leaders)} leaders, swarm={self.swarm_enabled}")

    def _build_domain_index(self):
        """각 Leader의 specialty를 기반으로 3계층 가중 키워드 인덱스 구축
        primary(+20): 해당 리더의 핵심 독점 키워드
        secondary(+10): 관련 일반 키워드
        contextual(+5): 문맥 보조 키워드
        """
        self.domain_keywords = {
            "L01": {"primary": ["민사", "민법", "불법행위", "부당이득"], "secondary": ["계약", "채무불이행", "채권", "물권"], "contextual": ["이행", "해제", "해지", "위약금", "약정"]},
            "L02": {"primary": ["부동산", "토지", "건물매매", "소유권이전"], "secondary": ["등기", "소유권", "지분", "매매", "건물", "아파트", "주택", "근저당"], "contextual": ["명의", "이중매매", "중개", "감정평가", "투기과열지구", "대출승계"]},
            "L03": {"primary": ["건설", "시공", "건설산업"], "secondary": ["공사", "하자", "설계", "건축"], "contextual": ["도급", "하도급", "공사대금", "준공", "시공사"]},
            "L04": {"primary": ["재개발", "재건축", "정비사업"], "secondary": ["조합", "분양", "도시정비"], "contextual": ["관리처분", "조합원", "이주비"]},
            "L05": {"primary": ["의료사고", "의료과실", "오진", "수술사고"], "secondary": ["의료", "진료", "수술", "병원", "의사", "환자"], "contextual": ["합병증", "후유증", "진료기록", "의료분쟁"]},
            "L06": {"primary": ["영업손실", "국가배상"], "secondary": ["손해배상", "배상", "보상", "위자료", "과실상계"], "contextual": ["일실수익", "재산피해", "정신적 고통"]},
            "L07": {"primary": ["교통사고", "자동차사고", "차량사고"], "secondary": ["과실비율", "합의금", "자동차", "보험사", "교통"], "contextual": ["신호위반", "음주운전", "뺑소니", "후유장해", "자배법"]},
            "L08": {"primary": ["임대차", "전세", "월세", "보증금반환"], "secondary": ["보증금", "임차", "임대", "집주인", "세입자"], "contextual": ["전입신고", "확정일자", "갱신", "묵시적", "계약갱신", "나가달라", "퇴거"]},
            "L09": {"primary": ["국가계약", "조달", "관급공사"], "secondary": ["입찰", "공공계약", "부정당업자"], "contextual": ["낙찰", "제재", "정부조달"]},
            "L10": {"primary": ["민사집행", "강제집행", "재산조회"], "secondary": ["압류", "배당", "집행", "가압류"], "contextual": ["채권압류", "급여압류", "재산명시"]},
            "L11": {"primary": ["채권추심", "추심", "빚독촉"], "secondary": ["채권", "변제", "빚", "상환"], "contextual": ["채무자", "채권자", "독촉", "변제기"]},
            "L12": {"primary": ["부동산경매", "낙찰", "경매법원"], "secondary": ["경매", "등기", "배당", "부동산등기"], "contextual": ["최저매각가", "매각허가", "인도명령", "명도"]},
            "L13": {"primary": ["상사", "상법", "상행위", "주주대표소송"], "secondary": ["회사", "주주", "이사", "이사회"], "contextual": ["대표이사", "감사", "총회", "결의"]},
            "L14": {"primary": ["m&a", "인수합병", "기업인수"], "secondary": ["회사법", "주식", "법인", "합병"], "contextual": ["실사", "주식양도", "경영권", "우선주"]},
            "L15": {"primary": ["스타트업", "스톡옵션", "공동창업"], "secondary": ["투자", "벤처", "창업", "투자유치"], "contextual": ["지분", "엔젤투자", "시드", "시리즈", "주주간계약"]},
            "L16": {"primary": ["보험금청구", "보험사기", "면책사유"], "secondary": ["보험", "보험금", "피보험자", "보험사", "보험약관"], "contextual": ["보장", "해약환급금", "보험료"]},
            "L17": {"primary": ["국제거래", "국제중재", "icc"], "secondary": ["무역분쟁", "중재", "외국", "국제"], "contextual": ["해외바이어", "외국기업", "통상"]},
            "L18": {"primary": ["에너지", "전력", "발전소"], "secondary": ["자원", "광업", "전기", "태양광"], "contextual": ["신재생", "인허가", "전기사업"]},
            "L19": {"primary": ["해상운송", "항공운송", "선박"], "secondary": ["해상", "항공", "운송", "물류"], "contextual": ["화물", "선하증권", "항공화물"]},
            "L20": {"primary": ["세무조사", "세금", "과세"], "secondary": ["조세", "금융", "은행", "국세", "지방세"], "contextual": ["소득세", "부가세", "종합소득", "탈세"]},
            "L21": {"primary": ["해킹", "정보유출", "사이버범죄"], "secondary": ["it", "보안", "정보보호", "사이버"], "contextual": ["서버", "취약점", "디도스"]},
            "L22": {"primary": ["형사", "고소", "기소", "구속", "수사", "도주치상", "특정범죄가중처벌"], "secondary": ["처벌", "범죄", "형법", "사기", "횡령", "폭행", "절도", "검찰", "음주운전", "도주"], "contextual": ["갚을 생각", "빌려줬", "차용증", "공증", "떼먹", "먹튀", "배임", "허위사실", "모욕", "비방", "악플", "sns", "자수", "양형", "집행유예"]},
            "L23": {"primary": ["엔터테인먼트", "연예", "전속계약"], "secondary": ["방송", "영화", "기획사"], "contextual": ["매니지먼트", "출연료", "연예인"]},
            "L24": {"primary": ["조세불복", "과세전적부심사"], "secondary": ["심판", "이의신청", "조세심판"], "contextual": ["경정청구", "부과처분", "국세청"]},
            "L25": {"primary": ["군형법", "군사법원", "군대폭력"], "secondary": ["군대", "군사", "군인"], "contextual": ["상관", "가혹행위", "군복무", "병역"]},
            "L26": {"primary": ["특허", "상표", "디자인권", "특허침해"], "secondary": ["지식재산권", "ip", "상표권", "특허권", "발명", "변리사"], "contextual": ["출원", "등록", "심사", "무효심판"]},
            "L27": {"primary": ["환경오염", "폐기물", "환경법"], "secondary": ["환경", "오염", "배출"], "contextual": ["소음", "악취", "수질", "대기오염"]},
            "L28": {"primary": ["관세", "수입통관", "fta"], "secondary": ["무역", "수입", "수출"], "contextual": ["관세분류", "반덤핑", "원산지"]},
            "L29": {"primary": ["게임", "게임아이템", "게임물"], "secondary": ["콘텐츠", "아이템"], "contextual": ["인게임", "현금거래", "게임사"]},
            "L30": {"primary": ["부당해고", "임금체불", "근로기준법", "노동조합"], "secondary": ["노동", "해고", "임금", "근로", "퇴직"], "contextual": ["급여", "연장근로", "야근", "통상임금", "퇴직금"]},
            "L31": {"primary": ["행정소송", "행정심판", "행정처분취소"], "secondary": ["행정", "행정처분", "취소", "허가", "행정청"], "contextual": ["인허가", "과징금", "영업정지"]},
            "L32": {"primary": ["공정거래", "담합", "독점"], "secondary": ["불공정", "경쟁제한", "시장지배"], "contextual": ["과징금", "공정위", "끼워팔기"]},
            "L33": {"primary": ["우주항공", "위성", "발사체"], "secondary": ["항공우주", "드론"], "contextual": ["우주산업", "항공규제"]},
            "L34": {"primary": ["개인정보", "개인정보보호", "gdpr"], "secondary": ["정보주체", "개인정보유출"], "contextual": ["동의", "수집", "제3자 제공"]},
            "L35": {"primary": ["헌법", "위헌", "헌법소원"], "secondary": ["기본권", "헌재", "헌법재판소", "위헌법률"], "contextual": ["기본권 침해", "법률심판"]},
            "L36": {"primary": ["문화재", "문화유산"], "secondary": ["문화", "종교", "문화재보호"], "contextual": ["지정구역", "보존"]},
            "L37": {"primary": ["소년법", "소년범", "미성년범죄"], "secondary": ["청소년", "미성년"], "contextual": ["학교폭력", "보호처분", "소년심판"]},
            "L38": {"primary": ["소비자보호", "환불거부", "소비자피해"], "secondary": ["소비자", "환불", "소비자기본법"], "contextual": ["하자", "불량", "제품결함", "청약철회"]},
            "L39": {"primary": ["정보통신", "전기통신", "통신사"], "secondary": ["통신", "망", "위약금"], "contextual": ["약정", "회선", "전파"]},
            "L40": {"primary": ["인권침해", "차별금지", "평등권"], "secondary": ["인권", "차별", "평등"], "contextual": ["성차별", "장애차별", "혐오"]},
            "L41": {"primary": ["이혼", "양육권", "재산분할"], "secondary": ["가족", "양육", "위자료", "혼인", "친권"], "contextual": ["면접교섭", "협의이혼", "소송이혼", "아이"]},
            "L42": {"primary": ["저작권침해", "저작물도용", "표절"], "secondary": ["저작권", "표절", "침해", "저작물", "사진도용"], "contextual": ["무단", "허락 없이", "워터마크", "도용", "복제", "블로그", "카피"]},
            "L43": {"primary": ["산업재해", "산재", "업무상재해", "업무상질병", "과로사"], "secondary": ["산업안전", "업무상", "괴롭힘", "과로", "중대재해", "산업안전보건"], "contextual": ["공장", "작업장", "산재보험", "추락", "직장내", "우울증", "뇌출혈", "안전난간"]},
            "L44": {"primary": ["사회복지", "사회보장", "기초생활수급"], "secondary": ["복지", "수급자"], "contextual": ["생계급여", "의료급여"]},
            "L45": {"primary": ["교육법", "학교폭력대책"], "secondary": ["교육", "학교", "학생"], "contextual": ["교사", "징계", "자퇴", "휴대폰압수"]},
            "L46": {"primary": ["국민연금", "4대보험", "건강보험"], "secondary": ["연금", "보험료"], "contextual": ["수급나이", "납입", "건강보험료"]},
            "L47": {"primary": ["규제샌드박스", "신산업특례"], "secondary": ["벤처", "신산업", "혁신"], "contextual": ["규제특례", "실증특례"]},
            "L48": {"primary": ["문화예술", "예술인권리"], "secondary": ["예술", "미술"], "contextual": ["예술인복지", "갤러리"]},
            "L49": {"primary": ["식중독", "식품안전", "식품위생"], "secondary": ["식품", "보건", "위생"], "contextual": ["음식점", "위해식품"]},
            "L50": {"primary": ["다문화", "체류자격", "영주권"], "secondary": ["이주", "외국인", "이민"], "contextual": ["비자", "귀화", "결혼이민"]},
            "L51": {"primary": ["종교법인", "사찰", "전통사찰"], "secondary": ["종교", "전통"], "contextual": ["종교단체", "교회재산"]},
            "L52": {"primary": ["언론중재", "정정보도", "보도피해", "명예훼손", "비방", "모욕"], "secondary": ["광고", "언론", "출판", "언론사", "기사", "보도", "정보통신망", "허위사실"], "contextual": ["오보", "반론보도", "명예", "악플", "댓글", "SNS", "인터넷"]},
            "L53": {"primary": ["농지", "농업법", "축산업법"], "secondary": ["농림", "축산", "농업", "축산업"], "contextual": ["농지매매", "축사"]},
            "L54": {"primary": ["해양", "수산업", "어업면허"], "secondary": ["수산", "어업", "어선", "수산물"], "contextual": ["양식", "불법조업"]},
            "L55": {"primary": ["과학기술", "r&d", "연구비"], "secondary": ["연구", "기술개발"], "contextual": ["국가과제", "연구부정"]},
            "L56": {"primary": ["장애인차별", "편의시설미비"], "secondary": ["장애인", "편의시설", "장애", "장애인차별금지"], "contextual": ["접근성", "이동권"]},
            "L57": {"primary": ["상속분쟁", "유언장", "유언무효", "신탁"], "secondary": ["상속", "유언", "유산", "상속세", "증여"], "contextual": ["유류분", "특별수익", "기여분", "상속포기"]},
            "L58": {"primary": ["스포츠사고", "체육진흥"], "secondary": ["스포츠", "레저", "체육", "운동"], "contextual": ["경기중부상", "도핑"]},
            "L59": {"primary": ["ai윤리", "알고리즘편향", "ai저작권"], "secondary": ["데이터", "알고리즘", "인공지능", "ai"], "contextual": ["생성ai", "딥페이크", "ai규제"]},
            # L60(마디)은 도메인 매칭에서 제외 — 기본 응답은 유나(CCO)가 담당
        }

    def detect_name_call(self, query: str) -> Optional[str]:
        """
        Query에서 리더 이름 직접 호출 감지

        "휘율아 계약 해지 방법" → "L01"
        "무결아 사기죄 질문" → "L22"
        "하율 리더님 자기소개" → "_UNKNOWN_NAME" (미등록)

        Returns:
            매칭된 leader_id, "_UNKNOWN_NAME" (미등록 이름 호출), 또는 None
        """
        import re

        # 모든 매칭 후보를 수집한 뒤, 긴 이름 우선 + 같은 길이면 앞쪽 위치 우선
        matches = []
        for leader_id, info in self.leaders.items():
            name = info.get("name", "")
            if not name:
                continue
            pos = query.find(name)
            if pos >= 0:
                matches.append((leader_id, name, pos))

        if matches:
            # 정렬: ① 이름 길이 내림차순 ② 출현 위치 오름차순
            matches.sort(key=lambda x: (-len(x[1]), x[2]))
            best_id, best_name, _ = matches[0]
            logger.info(f"🎯 이름 호출 감지: '{best_name}' → {best_id}")
            return best_id

        # 매칭 실패 시: "X 리더님", "X님" 등 호출 패턴 감지 → 미등록 이름
        name_call_pattern = re.search(r'(\S+)\s*(?:리더님|리더|님)', query)
        if name_call_pattern:
            called_name = name_call_pattern.group(1).rstrip(',.')
            # C-Level 직함 제거
            for title in ['CSO', 'CTO', 'CCO']:
                called_name = called_name.replace(title, '').strip()
            if called_name and len(called_name) >= 2:
                logger.info(f"⚠️ 미등록 이름 호출 감지: '{called_name}' → _UNKNOWN_NAME")
                return "_UNKNOWN_NAME"

        return None

    def detect_domains(self, query: str, ssot_sources: list = None) -> List[Tuple[str, int]]:
        """
        Query에서 관련 법률 도메인 탐지 (3계층 가중 키워드 + SSOT 부스트)

        Returns:
            List[Tuple[leader_id, score]] - 점수 순으로 정렬
        """
        domain_scores = {}

        query_lower = query.lower()

        for leader_id, kw_data in self.domain_keywords.items():
            # 해당 leader_id가 실제 registry에 있는지 확인
            if leader_id not in self.leaders:
                continue

            score = 0
            matched_keywords = []

            # 3계층 가중치 키워드 매칭
            for keyword in kw_data.get("primary", []):
                if keyword in query_lower:
                    score += 20
                    matched_keywords.append(f"{keyword}(P)")
            for keyword in kw_data.get("secondary", []):
                if keyword in query_lower:
                    score += 10
                    matched_keywords.append(f"{keyword}(S)")
            for keyword in kw_data.get("contextual", []):
                if keyword in query_lower:
                    score += 5
                    matched_keywords.append(f"{keyword}(C)")

            if score > 0:
                domain_scores[leader_id] = score
                leader_name = self.leaders[leader_id].get('name', '?')
                logger.debug(f"🎯 {leader_id} ({leader_name}): score={score}, matched={matched_keywords}")

        # SSOT 법률 매칭 부스트 (law_cache 기반)
        if ssot_sources:
            ssot_boost = resolve_leaders_from_ssot(ssot_sources)
            for leader_id, boost in ssot_boost.items():
                if leader_id in self.leaders:
                    domain_scores[leader_id] = domain_scores.get(leader_id, 0) + boost
                    logger.info(f"📦 SSOT 부스트: {leader_id} +{boost}")

        # 점수순 정렬
        sorted_domains = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)

        return sorted_domains

    def classify_domain_with_gemini(self, query: str) -> Optional[str]:
        """키워드 매칭 실패/동점 시 Gemini로 법률 분야 분류하여 leader_id 반환"""
        if not self.genai_client:
            return None

        # specialty 목록 생성
        specialty_list = []
        for lid, info in self.leaders.items():
            if lid == "L60":
                continue
            sp = info.get("specialty", "")
            if sp:
                specialty_list.append(f"{lid}:{sp}")

        if not specialty_list:
            return None

        prompt = (
            f"다음 질문의 법률 분야를 아래 목록에서 **하나만** 골라 코드(예: L22)만 답하세요.\n"
            f"해당 없으면 NONE이라고 답하세요.\n\n"
            f"질문: {query[:500]}\n\n"
            f"분야 목록:\n" + "\n".join(specialty_list)
        )

        if not _gemini_cb.allow_request():
            logger.warning(f"⚠️ Gemini Circuit Breaker OPEN — 도메인 분류 스킵")
            return None

        try:
            gc = self.genai_client
            if gc is None:
                logger.warning("⚠️ genai_client is None — 도메인 분류 스킵")
                return None
            # 429 시 자동 모델 전환
            for _attempt in range(3):
                model = get_model()
                try:
                    resp = gc.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=genai_types.GenerateContentConfig(max_output_tokens=50, temperature=0.0),
                    )
                    break
                except Exception as e:
                    if is_quota_error(e) and _attempt < 2:
                        on_quota_error()
                        continue
                    raise
            text = (resp.text or "").strip().upper()
            _gemini_cb.record_success()
            # L01~L60 형식 추출
            import re
            match = re.search(r'L(\d{2})', text)
            if match:
                leader_id = f"L{match.group(1)}"
                if leader_id in self.leaders and leader_id != "L60":
                    logger.info(f"🤖 Gemini 도메인 분류: '{query[:30]}...' → {leader_id} ({self.leaders[leader_id].get('specialty', '')})")
                    return leader_id
            logger.info(f"🤖 Gemini 도메인 분류 결과 없음: {text[:50]}")
            return None
        except Exception as e:
            _gemini_cb.record_failure()
            logger.warning(f"⚠️ Gemini 도메인 분류 실패 (무시): {e}")
            return None

    def select_leaders(self, query: str, detected_domains: List[Tuple[str, int]] = None, ssot_sources: list = None) -> List[Dict]:
        """
        Query에 적합한 Leader 선택

        Args:
            query: 사용자 질문
            detected_domains: 사전 탐지된 도메인 (None이면 자동 탐지)
            ssot_sources: SSOT 매칭 결과 (law_cache 기반 부스트용)

        Returns:
            List[Dict] - 선택된 Leader 정보 리스트
        """
        if not self.swarm_enabled:
            # Swarm 비활성화 시 기본 리더(L60)만 반환
            return [self.leaders.get("L60", {"name": "마디", "role": "시스템 총괄", "specialty": "통합"})]

        # 이름 호출 감지 (도메인 매칭보다 우선)
        named_leader_id = self.detect_name_call(query)
        if named_leader_id == "_UNKNOWN_NAME":
            # 미등록 리더 이름 → 유나(CCO)가 안내
            logger.info("⚠️ 미등록 리더 이름 호출 → 유나(CCO) 안내")
            return [{"name": "유나", "role": "Chief Content Officer", "specialty": "콘텐츠 설계", "_clevel": "CCO", "_unknown_name": True}]
        if named_leader_id:
            leader_info = self.leaders.get(named_leader_id, {})
            leader_info["_id"] = named_leader_id
            leader_info["_score"] = 100  # 이름 호출은 최고 우선순위
            logger.info(f"✅ 이름 호출 리더 단독 선택: {leader_info.get('name', '?')}({named_leader_id})")
            return [leader_info]

        if detected_domains is None:
            detected_domains = self.detect_domains(query, ssot_sources=ssot_sources)

        if not detected_domains:
            # 도메인 미탐지 → Gemini 1차 분류 시도
            gemini_leader_id = self.classify_domain_with_gemini(query)
            if gemini_leader_id:
                leader_info = self.leaders.get(gemini_leader_id, {})
                leader_info["_id"] = gemini_leader_id
                leader_info["_score"] = 50  # Gemini 분류
                logger.info(f"✅ Gemini 분류 리더 선택: {leader_info.get('name', '?')}({gemini_leader_id})")
                return [leader_info]
            # Gemini도 실패 → 유나(CCO)가 따뜻하게 맞이
            logger.info("🎯 도메인 미탐지 → 유나(CCO) 응대")
            return [{"name": "유나", "role": "Chief Content Officer", "specialty": "콘텐츠 설계", "_clevel": "CCO"}]

        # 상위 2개 동점 검사 → Gemini 분류로 해소
        if len(detected_domains) >= 2 and detected_domains[0][1] == detected_domains[1][1]:
            gemini_leader_id = self.classify_domain_with_gemini(query)
            if gemini_leader_id:
                # Gemini가 선택한 리더를 최상위로
                leader_info = self.leaders.get(gemini_leader_id, {})
                leader_info["_id"] = gemini_leader_id
                leader_info["_score"] = detected_domains[0][1] + 5  # 동점 해소
                logger.info(f"✅ Gemini 동점 해소: {leader_info.get('name', '?')}({gemini_leader_id})")
                return [leader_info]

        # 최소 점수 필터링
        detected_domains = [(lid, s) for lid, s in detected_domains if s >= _MIN_LEADER_SCORE]
        # 점수 비율 필터링 (1위 기준)
        if detected_domains:
            top_score = detected_domains[0][1]
            detected_domains = [(lid, s) for lid, s in detected_domains
                                if s >= top_score * _SCORE_RATIO_THRESHOLD]
        # 충돌 방지
        detected_domains = _resolve_leader_conflicts(detected_domains)

        # 상위 N개 도메인의 Leader 선택
        selected_leaders = []
        for leader_id, score in detected_domains[:self.max_leaders]:
            leader_info = self.leaders.get(leader_id, {})
            leader_info["_id"] = leader_id
            leader_info["_score"] = score
            selected_leaders.append(leader_info)

        # 최소 리더 수 보장
        if len(selected_leaders) < self.min_leaders:
            default_leader = {"name": "유나", "role": "Chief Content Officer", "specialty": "콘텐츠 설계", "_clevel": "CCO"}
            default_leader["_id"] = "CCO"
            default_leader["_score"] = 5
            selected_leaders.append(default_leader)

        leader_names = [f"{l.get('name', '?')}({l.get('specialty', '?')})" for l in selected_leaders]
        logger.info(f"✅ {len(selected_leaders)}명 리더 선택: {', '.join(leader_names)}")

        return selected_leaders

    def analyze_with_leader(
        self,
        leader: Dict,
        query: str,
        tools: List = None,
        system_instruction_base: str = "",
        model_name: str = _DEFAULT_MODEL
    ) -> Dict:
        """
        단일 Leader로 분석 실행

        Returns:
            Dict: {"leader": str, "specialty": str, "analysis": str, "success": bool}
        """
        leader_name = leader.get("name", "Unknown")
        leader_role = leader.get("role", "Unknown")
        leader_specialty = leader.get("specialty", "Unknown")

        try:
            # C-Level 여부 확인
            clevel_id = leader.get("_clevel")

            if clevel_id == "CCO":
                # 유나(CCO) 전용: 따뜻하고 친근한 톤 — 비법률 500자 제한
                system_instruction = (
                    f"{system_instruction_base}\n\n"
                    f"🎯 당신의 역할: 유나 (CCO, Chief Content Officer)\n"
                    f"🎯 전문 분야: 콘텐츠 설계 · 사용자 경험\n"
                    f"🎯 톤: 따뜻하고 친근하며, 사용자의 불안을 공감하고 행동으로 바꿔주는 스타일\n\n"
                    f"📏 **응답 길이 제한**: 비법률 질문은 반드시 500자 이내로 간결하게 답변하세요.\n\n"
                    f"사용자가 질문하면:\n"
                    f"1. 먼저 공감과 격려로 시작하세요\n"
                    f"2. 법률 관련이면 핵심 쟁점을 쉬운 말로 설명하세요\n"
                    f"3. 구체적인 행동 계획을 안내하세요\n"
                    f"4. 비법률 질문이면 친절하게 안내하되, 법률 상담도 가능함을 알려주세요\n\n"
                    f"**비법률 질문 목차 구조** (500자 이내):\n"
                    f"## 💡 핵심 답변\n"
                    f"(간결한 핵심 답변 1~3문장)\n\n"
                    f"## 📌 주요 포인트\n"
                    f"• 핵심 포인트 2~4개\n\n"
                    f"## 🔍 더 알아보기\n"
                    f"(관련 팁 또는 추가 안내 1~2문장)\n\n"
                    f"반드시 [유나 (CCO) 콘텐츠 설계]로 시작하세요."
                )
            elif clevel_id == "CSO":
                # 서연(CSO) 전용: 전략적 접근
                system_instruction = (
                    f"{system_instruction_base}\n\n"
                    f"🎯 당신의 역할: 서연 (CSO, Chief Strategy Officer)\n"
                    f"🎯 전문 분야: 전략 기획 · 법률 전략\n"
                    f"🎯 톤: 전략적이고 체계적이며, 큰 그림을 그려주는 스타일\n\n"
                    f"반드시 [서연 (CSO) 전략 분석]으로 시작하세요."
                )
            elif clevel_id == "CTO":
                # 지유(CTO) 전용
                system_instruction = (
                    f"{system_instruction_base}\n\n"
                    f"🎯 당신의 역할: 지유 (CTO, Chief Technology Officer)\n"
                    f"🎯 전문 분야: 기술 검증 · AI 무결성\n"
                    f"🎯 톤: 정확하고 논리적이며, 기술적 관점을 제공하는 스타일\n\n"
                    f"반드시 [지유 (CTO) 기술 분석]으로 시작하세요."
                )
            else:
                # 일반 법률 리더: 2000자 제한 + 법률 목차
                system_instruction = (
                    f"{system_instruction_base}\n\n"
                    f"🎯 당신의 역할: {leader_name} ({leader_role})\n"
                    f"🎯 전문 분야: {leader_specialty}\n"
                    f"🎯 관점: {leader_specialty} 전문가 관점에서 이 사안을 분석하세요.\n"
                    f"📏 **응답은 반드시 3000자 이내로 작성하세요.**\n\n"
                    f"**법률 분석 목차 구조**:\n"
                    f"## ⚖️ 핵심 쟁점\n"
                    f"(질문의 핵심 법률 쟁점 요약)\n\n"
                    f"## 📋 관련 법령\n"
                    f"(적용 법률·조문 + 핵심 내용)\n\n"
                    f"## 📌 판례·해석\n"
                    f"(관련 판례 또는 법령해석 핵심)\n\n"
                    f"## 🎯 실행 가이드\n"
                    f"(구체적 절차 + 대응 방안)\n\n"
                    f"## ℹ️ 참고\n"
                    f"(무료 법률 지원 기관, 추가 안내)\n\n"
                    f"반드시 [{leader_name} ({leader_specialty}) 분석]으로 시작하세요."
                )

            # 분석 실행 (Function Calling 활성화)
            # 비법률(CCO 단독) → 800 tokens (~500자), 법률 리더 → 4096 tokens (~2000자+)
            _max_tokens = 800 if clevel_id == "CCO" else 5500
            logger.info(f"🔄 {leader_name} ({leader_specialty}) 분석 시작... (max_tokens={_max_tokens})")

            if not _gemini_cb.allow_request():
                raise RuntimeError("Gemini Circuit Breaker OPEN")

            gc = self.genai_client
            if gc is None:
                raise RuntimeError("Gemini 클라이언트 미초기화 (GEMINI_KEY 확인 필요)")
            chat = gc.chats.create(
                model=model_name,
                config=genai_types.GenerateContentConfig(
                    tools=tools or [],
                    system_instruction=system_instruction,
                    max_output_tokens=_max_tokens,
                    automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=False),
                ),
            )
            response = chat.send_message(query)

            # 응답 텍스트 추출
            try:
                analysis_text = response.text
            except ValueError as e:
                # function_call이 포함되어 text 변환 실패 시
                logger.warning(f"⚠️ {leader_name} response.text 추출 실패: {e}")
                # 채팅 히스토리에서 마지막 텍스트 응답 찾기
                analysis_text = ""
                for part in response.parts:
                    if hasattr(part, 'text') and part.text:
                        analysis_text += part.text

                if not analysis_text:
                    analysis_text = f"[{leader_specialty} 분석 결과를 텍스트로 변환하지 못했습니다]"

            # 응답이 너무 짧으면 1회 재시도
            if len(analysis_text.strip()) < 50:
                logger.warning(f"⚠️ {leader_name} 응답 너무 짧음 ({len(analysis_text)}자), 재시도...")
                retry_response = chat.send_message(
                    f"이전 응답이 너무 짧습니다. 다음 질문에 대해 상세하게 분석해주세요:\n{query}"
                )
                try:
                    retry_text = retry_response.text
                except ValueError:
                    retry_text = ""
                    for part in retry_response.parts:
                        if hasattr(part, 'text') and part.text:
                            retry_text += part.text
                if len(retry_text.strip()) > len(analysis_text.strip()):
                    analysis_text = retry_text
                    logger.info(f"✅ {leader_name} 재시도 성공 ({len(analysis_text)} chars)")

            _gemini_cb.record_success()
            logger.info(f"✅ {leader_name} 분석 완료 ({len(analysis_text)} chars)")

            # chat.history에서 tool 호출 메타데이터 수집
            tools_used = []
            tool_results = []
            try:
                if hasattr(chat, 'history'):
                    for turn in chat.history:
                        if hasattr(turn, 'parts'):
                            for part in turn.parts:
                                if hasattr(part, 'function_call') and part.function_call:
                                    fc = part.function_call
                                    tools_used.append({
                                        "name": fc.name,
                                        "args": dict(fc.args) if fc.args else {}
                                    })
                                if hasattr(part, 'function_response') and part.function_response:
                                    fr = part.function_response
                                    response_data = dict(fr.response) if fr.response else {}
                                    tool_results.append(response_data)
            except Exception as te:
                logger.warning(f"⚠️ {leader_name} tool 메타데이터 수집 실패 (무시): {te}")

            return {
                "leader": leader_name,
                "specialty": leader_specialty,
                "role": leader_role,
                "analysis": analysis_text,
                "success": True,
                "tools_used": tools_used,
                "tool_results": tool_results
            }

        except Exception as e:
            _gemini_cb.record_failure()
            logger.error(f"❌ {leader_name} 분석 실패: {e}")
            return {
                "leader": leader_name,
                "specialty": leader_specialty,
                "role": leader_role,
                "analysis": f"[{leader_specialty} 분석 실패: {str(e)}]",
                "success": False
            }

    def parallel_swarm_analysis(
        self,
        query: str,
        selected_leaders: List[Dict],
        tools: List = None,
        system_instruction_base: str = "",
        model_name: str = _DEFAULT_MODEL
    ) -> List[Dict]:
        """
        여러 Leader로 병렬 분석 실행

        Returns:
            List[Dict] - 각 Leader의 분석 결과
        """
        results = []

        # 병렬 실행
        with ThreadPoolExecutor(max_workers=len(selected_leaders)) as executor:
            future_to_leader = {
                executor.submit(
                    self.analyze_with_leader,
                    leader,
                    query,
                    tools,
                    system_instruction_base,
                    model_name
                ): leader for leader in selected_leaders
            }

            for future in as_completed(future_to_leader):
                leader = future_to_leader[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"❌ {leader.get('name', '?')} 병렬 실행 오류: {e}")
                    results.append({
                        "leader": leader.get("name", "Unknown"),
                        "specialty": leader.get("specialty", "Unknown"),
                        "analysis": f"[실행 오류: {str(e)}]",
                        "success": False
                    })

        # 원래 순서 복원 (specialty 순서 유지)
        results_map = {r["leader"]: r for r in results}
        ordered_results = [results_map.get(l["name"], results_map[l["name"]]) for l in selected_leaders if l["name"] in results_map]

        return ordered_results

    def synthesize_swarm_results(
        self,
        query: str,
        swarm_results: List[Dict],
        model_name: str = _DEFAULT_MODEL
    ) -> str:
        """
        여러 Leader의 분석 결과를 통합하여 최종 판단 흐름 생성

        Args:
            query: 원본 질문
            swarm_results: 각 Leader의 분석 결과

        Returns:
            str: 통합된 최종 응답
        """
        # 성공한 분석만 필터링
        successful_analyses = [r for r in swarm_results if r.get("success", False)]

        if not successful_analyses:
            logger.warning("⚠️ 모든 Leader 분석 실패 - Fallback 응답 생성")
            return self._fallback_response(query)

        # 통합 프롬프트 생성
        synthesis_prompt = f"""
당신은 Lawmadi OS의 유나 (CCO, Chief Content Officer)입니다.
여러 전문 분야 리더들이 분석한 결과를 따뜻하고 이해하기 쉽게 통합하여 최종 판단 흐름을 생성하세요.
사용자의 불안에 공감하고, 구체적인 행동으로 바꿔주는 톤을 유지하세요.

[사용자 질문]
{query}

[전문 리더 분석 결과]
"""

        for idx, result in enumerate(successful_analyses, 1):
            synthesis_prompt += f"\n[{idx}. {result['leader']} ({result['specialty']})]\n"
            synthesis_prompt += result['analysis']
            synthesis_prompt += "\n"

        # 참여 리더 목록 생성
        leader_names = [f"{a['leader']} ({a['specialty']})" for a in successful_analyses]
        leader_list_str = ", ".join(leader_names)

        synthesis_prompt += f"""

[통합 지침]
📏 **전체 응답은 반드시 3000자 이내로 작성하세요.**

1. 모든 전문 리더의 분석을 고려하여 종합적인 답변을 작성하세요
2. 반드시 아래 헤더로 시작하세요:
   [유나 (CCO) 종합 판단]
   참여 전문가: {leader_list_str}

3. 반드시 다음 목차 구조를 유지하세요:

   ## ⚖️ 핵심 쟁점
   • 상황 진단 + 공감
   • 핵심 법률 쟁점 요약

   ## 📋 법률 근거 분석
   리더별 배지형 구분:
   👤 [리더명] 리더 ([전문분야] 전문)
   • 분야별 법률 근거 정리

   ## 🎯 실행 가이드
   • 즉시 조치 (24시간 내)
   • 단계별 가이드
   • □ 체크리스트 항목

   ## ℹ️ 참고
   • 무료 법률 지원 (기관명 + 전화번호)
   • 관련 법령 요약

4. 여러 전문 분야가 교차하는 복합 사안임을 명시하세요
5. 전문가 간 의견이 다를 경우 양측 관점을 모두 제시하세요
6. 마무리에 재질문 유도 + 간결한 면책 포함

🚨 **CRITICAL**: 절대로 마크다운 표(table) 형식을 사용하지 마세요!
❌ 금지: | 구분 | 내용 | 형식
✅ 사용: • **항목** - 설명 형식 또는 번호 목록

[응답 형식]
반드시 "[유나 (CCO) 종합 판단]"으로 시작하세요.
"""

        try:
            # 통합 모델 실행
            logger.info(f"🔄 통합 분석 시작 ({len(successful_analyses)}개 리더 결과 통합)...")

            gc = self.genai_client
            if gc is None:
                raise RuntimeError("Gemini 클라이언트 미초기화 (GEMINI_KEY 확인 필요)")
            response = gc.models.generate_content(
                model=model_name,
                contents=synthesis_prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.3,
                    top_p=0.95,
                    max_output_tokens=4500,
                ),
            )
            final_response = response.text

            logger.info(f"✅ 통합 분석 완료 ({len(final_response)} chars)")

            return final_response

        except Exception as e:
            logger.error(f"❌ 통합 분석 실패: {e}")
            return self._fallback_response_with_analyses(query, successful_analyses)

    async def synthesize_swarm_results_stream(
        self,
        query: str,
        swarm_results: list,
        model_name: str = _DEFAULT_MODEL
    ):
        """
        여러 Leader의 분석 결과를 통합 — 스트리밍 버전 (async generator)
        yield: str (텍스트 청크)
        """
        import asyncio

        successful_analyses = [r for r in swarm_results if r.get("success", False)]

        if not successful_analyses:
            logger.warning("⚠️ 모든 Leader 분석 실패 - Fallback 응답 생성")
            yield self._fallback_response(query)
            return

        # 통합 프롬프트 생성 (기존 synthesize_swarm_results와 동일)
        leader_names = [f"{a['leader']} ({a['specialty']})" for a in successful_analyses]
        leader_list_str = ", ".join(leader_names)

        synthesis_prompt = f"""
당신은 Lawmadi OS의 유나 (CCO, Chief Content Officer)입니다.
여러 전문 분야 리더들이 분석한 결과를 따뜻하고 이해하기 쉽게 통합하여 최종 판단 흐름을 생성하세요.
사용자의 불안에 공감하고, 구체적인 행동으로 바꿔주는 톤을 유지하세요.

[사용자 질문]
{query}

[전문 리더 분석 결과]
"""

        for idx, result in enumerate(successful_analyses, 1):
            synthesis_prompt += f"\n[{idx}. {result['leader']} ({result['specialty']})]\n"
            synthesis_prompt += result['analysis']
            synthesis_prompt += "\n"

        synthesis_prompt += f"""

[통합 지침]
📏 **전체 응답은 반드시 3000자 이내로 작성하세요.**

1. 모든 전문 리더의 분석을 고려하여 종합적인 답변을 작성하세요
2. 반드시 아래 헤더로 시작하세요:
   [유나 (CCO) 종합 판단]
   참여 전문가: {leader_list_str}

3. 반드시 다음 목차 구조를 유지하세요:

   ## ⚖️ 핵심 쟁점
   • 상황 진단 + 공감
   • 핵심 법률 쟁점 요약

   ## 📋 법률 근거 분석
   리더별 배지형 구분:
   👤 [리더명] 리더 ([전문분야] 전문)
   • 분야별 법률 근거 정리

   ## 🎯 실행 가이드
   • 즉시 조치 (24시간 내)
   • 단계별 가이드
   • □ 체크리스트 항목

   ## ℹ️ 참고
   • 무료 법률 지원 (기관명 + 전화번호)
   • 관련 법령 요약

4. 여러 전문 분야가 교차하는 복합 사안임을 명시하세요
5. 전문가 간 의견이 다를 경우 양측 관점을 모두 제시하세요
6. 마무리에 재질문 유도 + 간결한 면책 포함

🚨 **CRITICAL**: 절대로 마크다운 표(table) 형식을 사용하지 마세요!
❌ 금지: | 구분 | 내용 | 형식
✅ 사용: • **항목** - 설명 형식 또는 번호 목록

[응답 형식]
반드시 "[유나 (CCO) 종합 판단]"으로 시작하세요.
"""

        try:
            logger.info(f"🔄 통합 분석 스트리밍 시작 ({len(successful_analyses)}개 리더 결과 통합)...")

            gc = self.genai_client
            if gc is None:
                raise RuntimeError("Gemini 클라이언트 미초기화 (GEMINI_KEY 확인 필요)")

            # generate_content_stream을 별도 스레드에서 실행
            loop = asyncio.get_event_loop()

            def _stream_sync():
                return gc.models.generate_content_stream(
                    model=model_name,
                    contents=synthesis_prompt,
                    config=genai_types.GenerateContentConfig(
                        temperature=0.3,
                        top_p=0.95,
                        max_output_tokens=4500,
                    ),
                )

            stream = await loop.run_in_executor(None, _stream_sync)

            total_chars = 0
            # 동기 이터레이터를 비동기로 소비 (이벤트 루프 블로킹 방지)
            queue = asyncio.Queue()

            def _consume_stream():
                try:
                    for chunk in stream:
                        text_part = ""
                        if hasattr(chunk, 'text') and chunk.text:
                            text_part = chunk.text
                        elif hasattr(chunk, 'parts'):
                            for part in chunk.parts:
                                if hasattr(part, 'text') and part.text:
                                    text_part += part.text
                        if text_part:
                            queue.put_nowait(text_part)
                    queue.put_nowait(None)  # sentinel
                except Exception as e:
                    queue.put_nowait(e)

            loop.run_in_executor(None, _consume_stream)

            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    raise item
                total_chars += len(item)
                yield item

            logger.info(f"✅ 통합 분석 스트리밍 완료 ({total_chars} chars)")

        except Exception as e:
            logger.error(f"❌ 통합 분석 스트리밍 실패: {e}")
            yield self._fallback_response_with_analyses(query, successful_analyses)

    def _fallback_response(self, query: str) -> str:
        """Fallback 응답 생성"""
        return f"""[유나 (CCO) 종합 판단]

1. 핵심 요약
   1.1 상황 진단
   분석 중 시스템 오류가 발생하여 일부 기능이 제한되었습니다.

   1.2 결론 및 전략 방향
   아래 지원 기관을 통해 직접 상담을 받으시길 권장합니다.

2. 법률 근거 분석
   현재 법률 데이터 검색이 제한되어 있습니다.
   질문: {query[:100]}...

3. 시간축 전략
   3.1 현재 (골든타임)
   • 아래 무료 상담 기관에 즉시 연락하세요.

4. 실행 계획
   4.1 즉시 조치
   • 대한법률구조공단 ☎ 132 — 무료 법률 상담
   • 관할 법원/기관에 문의

   4.3 체크리스트
   □ 관련 서류 정리
   □ 상담 기관 연락

5. 추가 정보
   5.1 무료 법률 지원
   • 대한법률구조공단 ☎ 132 (klac.or.kr)
   • 국민권익위원회 ☎ 110 (epeople.go.kr)

> ℹ️ 본 시스템은 법률 자문이 아닌 정보 제공 시스템입니다.
"""

    def _fallback_response_with_analyses(self, query: str, analyses: List[Dict]) -> str:
        """분석 결과 포함 Fallback 응답"""
        leader_names = [f"{a['leader']} ({a['specialty']})" for a in analyses]
        leader_list_str = ", ".join(leader_names)

        response = "[유나 (CCO) 종합 판단]\n\n"
        response += f"참여 전문가: {leader_list_str}\n\n"

        response += "1. 핵심 요약\n"
        response += f"   1.1 상황 진단\n"
        response += f"   본 사안은 {', '.join([a['specialty'] for a in analyses])} 등 복합 법률 영역에 관한 질문입니다.\n\n"

        response += "2. 법률 근거 분석\n\n"
        for idx, analysis in enumerate(analyses, 1):
            response += f"   👤 {analysis['leader']} 리더 ({analysis['specialty']} 전문)\n\n"
            response += f"   2.{idx} {analysis['specialty']} 검토\n"
            response += analysis['analysis']
            response += "\n\n"

        response += "5. 추가 정보\n"
        response += "   5.1 무료 법률 지원\n"
        response += "   • 대한법률구조공단 ☎ 132 (klac.or.kr)\n"
        response += "   • 국민권익위원회 ☎ 110 (epeople.go.kr)\n\n"
        response += "여러 전문 분야의 분석이 제공되었습니다. 종합적인 판단을 위해 전문가 상담을 권장합니다.\n"

        return response

    def orchestrate(
        self,
        query: str,
        tools: List = None,
        system_instruction_base: str = "",
        model_name: str = _DEFAULT_MODEL,
        force_single: bool = False,
        ssot_sources: list = None
    ) -> Dict:
        """
        Swarm 전체 오케스트레이션

        Args:
            query: 사용자 질문
            tools: Function calling tools
            system_instruction_base: 기본 시스템 지시
            model_name: Gemini 모델명
            force_single: True면 단일 리더만 사용 (테스트용)
            ssot_sources: SSOT 매칭 결과 (law_cache 기반 부스트용)

        Returns:
            Dict: {
                "response": str,
                "leaders": List[str],
                "domains": List[str],
                "swarm_mode": bool
            }
        """
        # 1. 도메인 탐지 (SSOT 부스트 포함)
        detected_domains = self.detect_domains(query, ssot_sources=ssot_sources)

        # 2. Leader 선택 (SSOT 부스트 포함)
        selected_leaders = self.select_leaders(query, detected_domains, ssot_sources=ssot_sources)

        # 3. 단일 vs 다중 모드 결정
        use_swarm = (
            self.swarm_enabled
            and not force_single
            and len(selected_leaders) > 1
        )

        # 법률/비법률 판단: CCO 단독이면 비법률
        _is_legal = not (len(selected_leaders) == 1 and selected_leaders[0].get("_clevel") == "CCO")

        if not use_swarm:
            # 단일 리더 모드
            logger.info(f"🔄 단일 리더 모드: {selected_leaders[0]['name']} (is_legal={_is_legal})")
            result = self.analyze_with_leader(
                selected_leaders[0],
                query,
                tools,
                system_instruction_base,
                model_name
            )

            return {
                "response": result["analysis"],
                "leaders": [result["leader"]],
                "domains": [result["specialty"]],
                "swarm_mode": False,
                "leader_count": 1,
                "is_legal": _is_legal,
                "tools_used": result.get("tools_used", []),
                "tool_results": result.get("tool_results", [])
            }

        # 4. Swarm 모드: 병렬 분석
        logger.info(f"🔄 Swarm 모드: {len(selected_leaders)}명 리더 병렬 분석")
        swarm_results = self.parallel_swarm_analysis(
            query,
            selected_leaders,
            tools,
            system_instruction_base,
            model_name
        )

        # 5. 결과 통합 (성공한 리더가 1명뿐이면 synthesis 스킵 → ~8초 절약)
        successful = [r for r in swarm_results if r.get("success", False)]

        if len(successful) == 1:
            logger.info(f"⚡ 성공 리더 1명 — synthesis 스킵 ({successful[0]['leader']})")
            final_response = successful[0]["analysis"]
        else:
            final_response = self.synthesize_swarm_results(
                query,
                swarm_results,
                model_name
            )

        # 모든 리더의 tool 메타데이터 합산
        all_tools_used = []
        all_tool_results = []
        for r in swarm_results:
            all_tools_used.extend(r.get("tools_used", []))
            all_tool_results.extend(r.get("tool_results", []))

        return {
            "response": final_response,
            "leaders": [r["leader"] for r in swarm_results],
            "domains": [r["specialty"] for r in swarm_results],
            "swarm_mode": len(successful) > 1,
            "leader_count": len(swarm_results),
            "is_legal": _is_legal,
            "detailed_results": swarm_results,
            "tools_used": all_tools_used,
            "tool_results": all_tool_results
        }
