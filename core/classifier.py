"""
Lawmadi OS v60 -- 질문 분류/티어 라우팅 엔진.
main.py에서 분리됨.

사용법:
    from core.classifier import set_runtime, set_leader_registry
    from core.classifier import _claude_analyze_query, _fallback_tier_classification, select_swarm_leader
    set_runtime(RUNTIME)
    set_leader_registry(LEADER_REGISTRY)
"""
import logging
from typing import Any, Dict, List, Optional

from utils.helpers import _safe_extract_json

logger = logging.getLogger("LawmadiOS.Classifier")

# ---------------------------------------------------------------------------
# Setter pattern: RUNTIME and LEADER_REGISTRY injected at startup
# ---------------------------------------------------------------------------
_RUNTIME: Dict[str, Any] = {}
_LEADER_REGISTRY: Dict[str, Any] = {}


def set_runtime(runtime: Dict[str, Any]) -> None:
    """main.py startup에서 RUNTIME 딕셔너리를 주입"""
    global _RUNTIME
    _RUNTIME = runtime


def set_leader_registry(registry: Dict[str, Any]) -> None:
    """main.py startup에서 LEADER_REGISTRY를 주입"""
    global _LEADER_REGISTRY
    _LEADER_REGISTRY = registry


# =============================================================
# [L2 SWARM] 리더 라우팅
# =============================================================

def select_swarm_leader(query: str, leaders: Dict) -> Dict:
    raw = leaders if leaders else _LEADER_REGISTRY
    # leaders.json 구조: {swarm_engine_config: {leader_registry: {L01:..., L08:...}}}
    registry = raw.get("swarm_engine_config", {}).get("leader_registry", {})
    if not registry:
        # 직접 L01 키가 있는 경우 (flat 구조)
        registry = {k: v for k, v in raw.items() if k.startswith("L") and isinstance(v, dict)}

    # 1) 이름 또는 별칭 명시적 매칭 (긴 이름 우선 + 앞쪽 위치 우선 -> 오탐 방지)
    name_matches = []
    for leader_id, info in registry.items():
        name = info.get("name", "")
        if name:
            pos = query.find(name)
            if pos >= 0:
                name_matches.append((leader_id, info, name, pos))
        if any(alias in query for alias in info.get("aliases", [])):
            logger.info(f"[L2 Hot-Swap] '{name}' 노드 별칭 호출 감지")
            return info

    if name_matches:
        # 정렬: (1) 이름 길이 내림차순 (2) 출현 위치 오름차순
        name_matches.sort(key=lambda x: (-len(x[2]), x[3]))
        best_id, best_info, best_name, _ = name_matches[0]
        logger.info(f"[L2 Hot-Swap] '{best_name}'({best_id}) 이름 호출 감지")
        return best_info

    # 2) 도메인 키워드 매칭 (전체 60 Leader 매핑)
    domain_map = {
        # L01-L10
        "L01_CIVIL":        (["민법", "계약", "채권", "채무", "손해배상", "불법행위", "소유권", "물권", "용익물권", "담보물권"], "L01"),
        "L02_PROPERTY":     (["부동산법", "토지", "건물", "분양", "등기소", "소유권이전"], "L02"),
        "L03_CONSTRUCTION": (["건설법", "건축", "공사", "하자", "시공", "설계", "건축허가", "착공"], "L03"),
        "L04_REDEVEL":      (["재개발", "재건축", "정비사업", "조합", "분담금", "관리처분"], "L04"),
        "L05_MEDICAL":      (["의료법", "의료사고", "의료과오", "병원", "진료", "의사", "환자", "의료분쟁"], "L05"),
        "L06_DAMAGES":      (["손해배상", "위자료", "배상금", "과실", "책임", "보상"], "L06"),
        "L07_TRAFFIC":      (["교통사고", "자동차", "운전", "사고", "충돌", "보험금", "과실비율"], "L07"),
        "L08_LEASE":        (["임대차", "전세", "월세", "보증금", "임대", "임차", "계약갱신", "대항력"], "L08"),
        "L09_GOVCONTRACT":  (["국가계약", "조달", "입찰", "낙찰", "공사계약", "물품계약"], "L09"),
        "L10_EXECUTION":    (["민사집행", "강제집행", "배당", "압류", "가압류", "경매", "집행권원"], "L10"),

        # L11-L20
        "L11_COLLECTION":   (["채권추심", "추심", "채권", "변제", "독촉", "지급명령"], "L11"),
        "L12_AUCTION":      (["등기", "경매", "공매", "낙찰", "명도", "유찰"], "L12"),
        "L13_COMMERCIAL":   (["상사법", "상법", "상거래", "어음", "수표", "상인"], "L13"),
        "L14_CORP_MA":      (["회사법", "M&A", "인수합병", "주식양도", "법인", "이사회", "주주총회"], "L14"),
        "L15_STARTUP":      (["스타트업", "벤처", "투자계약", "스톡옵션", "엔젤", "시드"], "L15"),
        "L16_INSURANCE":    (["보험", "보험금", "보험계약", "피보험자", "보험사고", "면책"], "L16"),
        "L17_INTL_TRADE":   (["국제거래", "수출", "수입", "무역", "중재", "국제계약"], "L17"),
        "L18_ENERGY":       (["에너지", "자원", "전력", "가스", "석유", "신재생"], "L18"),
        "L19_MARINE_AIR":   (["해상", "항공", "선박", "항공기", "운송", "해운"], "L19"),
        "L20_TAX_FIN":      (["조세", "금융", "세금", "국세", "지방세", "은행", "금융거래"], "L20"),

        # L21-L30
        "L21_IT_SEC":       (["IT", "보안", "정보보호", "해킹", "사이버", "네트워크", "시스템"], "L21"),
        "L22_CRIMINAL":     (["형사", "형법", "고소", "고발", "처벌", "사기", "횡령", "배임", "폭행", "갚을 생각", "빌려줬", "차용증", "공증", "떼먹", "먹튀"], "L22"),
        "L23_ENTERTAIN":    (["엔터테인먼트", "연예", "연예인", "매니지먼트", "방송"], "L23"),
        "L24_TAX_APPEAL":   (["조세불복", "조세심판", "세무조사", "부과처분", "경정청구"], "L24"),
        "L25_MILITARY":     (["군형법", "군대", "군인", "병역", "군사법원", "영창"], "L25"),
        "L26_IP":           (["지식재산권", "특허", "상표", "디자인", "저작권", "영업비밀"], "L26"),
        "L27_ENVIRON":      (["환경법", "환경오염", "대기", "수질", "토양", "폐기물"], "L27"),
        "L28_CUSTOMS":      (["무역", "관세", "통관", "수입신고", "FTA"], "L28"),
        "L29_GAME":         (["게임", "콘텐츠", "게임물", "등급분류", "아이템"], "L29"),
        "L30_LABOR":        (["노동법", "근로", "해고", "임금", "퇴직금", "수당", "노동조합"], "L30"),

        # L31-L40
        "L31_ADMIN":        (["행정법", "행정", "인허가", "과태료", "행정처분", "영업정지", "행정소송"], "L31"),
        "L32_FAIRTRADE":    (["공정거래", "독점", "담합", "불공정거래", "시장지배적지위"], "L32"),
        "L33_SPACE":        (["우주항공", "위성", "발사체", "궤도", "항공우주"], "L33"),
        "L34_PRIVACY":      (["개인정보", "개인정보보호", "정보주체", "유출", "GDPR"], "L34"),
        "L35_CONSTITUTION": (["헌법", "위헌", "헌법소원", "기본권", "헌법재판소"], "L35"),
        "L36_CULTURE":      (["문화", "종교", "문화재", "전통", "사찰", "교회"], "L36"),
        "L37_JUVENILE":     (["소년법", "청소년", "미성년자", "소년범", "보호처분"], "L37"),
        "L38_CONSUMER":     (["소비자", "소비자보호", "제조물책임", "환불", "약관"], "L38"),
        "L39_TELECOM":      (["정보통신", "통신", "전기통신", "방송통신"], "L39"),
        "L40_HUMAN_RIGHTS": (["인권", "차별", "평등", "인권침해"], "L40"),

        # L41-L50
        "L41_DIVORCE":      (["이혼", "가족", "양육권", "양육비", "친권", "면접교섭", "재산분할"], "L41"),
        "L42_COPYRIGHT":    (["저작권", "저작물", "저작자", "복제", "공연", "전송"], "L42"),
        "L43_INDUSTRIAL":   (["산업재해", "산재", "업무상재해", "요양급여", "장해급여"], "L43"),
        "L44_WELFARE":      (["사회복지", "복지", "사회보장", "기초생활", "복지시설"], "L44"),
        "L45_EDUCATION":    (["교육", "청소년", "학교", "학교폭력", "교육청", "학생"], "L45"),
        "L46_PENSION":      (["보험", "연금", "국민연금", "퇴직연금", "기금"], "L46"),
        "L47_VENTURE":      (["벤처", "신산업", "규제샌드박스", "신기술"], "L47"),
        "L48_ARTS":         (["문화예술", "예술", "예술인", "공연", "전시"], "L48"),
        "L49_FOOD":         (["식품", "보건", "식약처", "위생", "의약품"], "L49"),
        "L50_MULTICUL":     (["다문화", "이주", "외국인", "결혼이민", "난민"], "L50"),

        # L51-L60
        "L51_RELIGION":     (["종교", "전통", "사찰", "교회", "종단"], "L51"),
        "L52_MEDIA":        (["광고", "언론", "방송", "신문", "기자", "명예훼손", "허위사실", "SNS", "게시글", "비방", "모욕", "악플"], "L52"),
        "L53_AGRI":         (["농림", "축산", "농업", "축산업", "농지", "가축"], "L53"),
        "L54_FISHERY":      (["해양", "수산", "어업", "어선", "수산물"], "L54"),
        "L55_SCIENCE":      (["과학기술", "연구개발", "R&D", "기술이전"], "L55"),
        "L56_DISABILITY":   (["장애인", "복지", "장애", "장애인권익"], "L56"),
        "L57_INHERITANCE":  (["상속", "신탁", "유산", "유언장", "상속포기", "한정승인", "신탁재산"], "L57"),
        "L58_SPORTS":       (["스포츠", "레저", "체육", "운동선수", "도핑"], "L58"),
        "L59_AI_ETHICS":    (["데이터", "AI윤리", "인공지능", "알고리즘", "빅데이터"], "L59"),
        # L60 마디는 fallback으로만 사용
    }

    # 키워드 매칭 (점수 기반 - 가장 많이 매칭된 도메인 선택)
    max_score = 0
    selected_leader = None

    for _, (keywords, leader_id) in domain_map.items():
        score = sum(1 for k in keywords if k in query)
        if score > max_score:
            max_score = score
            selected_leader = leader_id

    if max_score > 0 and selected_leader:
        logger.info(f"[L2] {selected_leader} 리더 자동 배정 (키워드 {max_score}개 매칭)")
        return registry.get(selected_leader, registry.get("L60", {"name": "마디 통합 리더", "role": "시스템 기본 분석"}))

    # 3) Fallback -> 유나(CCO)가 따뜻하게 맞이
    logger.info("[L2] 전문 리더 미매칭 -> 유나(CCO) 응대")
    return {"name": "유나", "role": "Chief Content Officer", "specialty": "콘텐츠 설계", "_clevel": "CCO"}


# =============================================================
# [TIER ROUTER] Claude 분석 -> 티어 분류 -> 리더 배정
# Gemini 98%, Claude 2% 구조
# T1(90%): Gemini Flash 단독 | T2(8%): Gemini+Claude 보강 | T3(2%): Claude 직접(법률충돌/문서작성)
# 모듈화: T1을 나중에 LawmadiLM으로 교체 가능
# =============================================================

def _build_leader_summary_for_claude() -> str:
    """리더 레지스트리에서 Claude 분석용 요약 생성"""
    lines = []
    reg = _LEADER_REGISTRY
    if not reg:
        return "리더 정보 없음"
    # leaders.json은 swarm_engine_config.leader_registry 또는 직접 L01 키 구조
    leader_data = reg.get("swarm_engine_config", {}).get("leader_registry", {})
    if not leader_data:
        # leaders_registry.json 형식 (leaders 키)
        leader_data = reg.get("leaders", {})
    if not leader_data:
        # 직접 L01 키가 있는 경우
        leader_data = {k: v for k, v in reg.items() if k.startswith("L")}
    for lid, info in sorted(leader_data.items()):
        name = info.get("name", "")
        spec = info.get("specialty", "")
        laws = info.get("laws", [])
        if isinstance(laws, list):
            laws_str = ", ".join(laws[:3])
        else:
            laws_str = str(laws)
        lines.append(f"{lid} {name} | {spec} | {laws_str}")
    return "\n".join(lines) if lines else "리더 정보 없음"


TIER_ANALYSIS_PROMPT = """당신은 Lawmadi OS의 질문 분류 엔진입니다.
사용자의 법률 질문을 분석하여 JSON으로 응답하세요. 답변은 절대 하지 마세요.

## 60인 리더 목록
{leader_summary}

## 분류 기준
- complexity: "simple" (단일 법률, 조문 확인, 용어 설명) | "complex" (2개 이상 법률, 판례 필요) | "critical" (법률 간 충돌, 헌법 쟁점, 다중 이해관계)
- is_document: true (고소장/소장/답변서/내용증명/고소취하서/합의서/계약서 등 법률문서 작성 요청인 경우)
- tier: 1 (simple이고 문서작성 아님) | 2 (complex이고 문서작성 아님) | 3 (critical이거나 문서작성 요청)
- leader_id: 가장 적합한 리더 1명의 ID (예: "L08")
- leader_name: 해당 리더 이름
- leader_specialty: 전문 분야
- summary: 질문 핵심 요약 (1문장)
- is_legal: true (법률 질문) | false (비법률 질문)

반드시 아래 JSON 형식만 출력하세요:
{{"tier": 1, "complexity": "simple", "is_document": false, "leader_id": "L08", "leader_name": "온유", "leader_specialty": "임대차", "summary": "전세 보증금 반환 문제", "is_legal": true}}"""


async def _claude_analyze_query(query: str) -> Optional[Dict[str, Any]]:
    """Claude로 질문 분석/분류/리더 배정 (답변 X)"""
    claude_client = _RUNTIME.get("claude_client")
    if not claude_client:
        logger.warning("Claude 클라이언트 없음 -> 키워드 기반 fallback")
        return None

    leader_summary = _build_leader_summary_for_claude()
    try:
        resp = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": f"질문: {query}"}],
            system=TIER_ANALYSIS_PROMPT.format(leader_summary=leader_summary),
        )
        text = resp.content[0].text.strip()
        # JSON 추출 (중첩 JSON 및 코드블록 지원)
        result = _safe_extract_json(text)
        if result:
            logger.info(f"[Tier Router] Claude 분석: tier={result.get('tier')}, "
                       f"leader={result.get('leader_name')}({result.get('leader_id')}), "
                       f"complexity={result.get('complexity')}, is_document={result.get('is_document')}")
            return result
        logger.warning(f"Claude 분석 JSON 파싱 실패: {text[:200]}")
        return None
    except Exception as e:
        logger.warning(f"Claude 분석 실패: {e}")
        return None


def _fallback_tier_classification(query: str) -> Dict[str, Any]:
    """Claude 실패 시 키워드 기반 fallback 분류"""
    leader = select_swarm_leader(query, _LEADER_REGISTRY)
    leader_name = leader.get("name", "마디")
    leader_specialty = leader.get("specialty", "시스템 총괄")

    # 문서 작성 키워드 감지
    doc_keywords = ["작성해", "써줘", "만들어", "초안", "양식", "서식",
                     "고소장", "소장", "답변서", "내용증명", "고소취하서", "합의서", "계약서"]
    is_document = any(kw in query for kw in doc_keywords)

    # 복잡도 판단
    complex_keywords = ["판례", "사례", "대법원", "헌법재판소", "법률 충돌", "위헌"]
    critical_keywords = ["헌법", "위헌", "기본권", "법률 간 충돌", "헌법소원"]

    if is_document or any(kw in query for kw in critical_keywords):
        tier = 3
        complexity = "critical"
    elif sum(1 for kw in complex_keywords if kw in query) >= 1:
        tier = 2
        complexity = "complex"
    else:
        tier = 1
        complexity = "simple"

    # CCO fallback은 비법률
    is_legal = leader.get("_clevel") != "CCO"

    return {
        "tier": tier,
        "complexity": complexity,
        "is_document": is_document,
        "leader_id": "L60",
        "leader_name": leader_name,
        "leader_specialty": leader_specialty,
        "summary": query[:50],
        "is_legal": is_legal,
    }
