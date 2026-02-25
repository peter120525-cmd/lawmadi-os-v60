"""
Lawmadi OS v60 -- 질문 분류/티어 라우팅 엔진.
main.py에서 분리됨.

사용법:
    from core.classifier import set_runtime, set_leader_registry
    from core.classifier import _gemini_analyze_query, _fallback_tier_classification, select_swarm_leader
    set_runtime(RUNTIME)
    set_leader_registry(LEADER_REGISTRY)
"""
import os
import re
import logging
import asyncio
from typing import Any, Dict, List, Optional

from core.constants import GEMINI_MODEL
from core.model_fallback import get_model, on_quota_error, is_quota_error
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
# [NLU] 자연어 패턴 기반 법적 의도 감지
# 키워드 매칭보다 정확한 문맥 매칭 — 대화체 한국어 질문 지원.
# 패턴은 (상황/주체) + (행위/상태) 조합으로 법률 도메인을 감지.
# =============================================================

_NLU_INTENT_PATTERNS: Dict[str, List[str]] = {
    # L22: 형사법 — 폭행·협박·사기·절도·성범죄 등
    "L22": [
        r"(?:누군가|친구|사람|남자|여자|상대|옆\s*사람|동네|이웃).*(?:때리|때려|때렸|때린|맞|맞은|폭행|위협|협박|치|구타|밀치|밀친)",
        r"(?:때리|때려|때렸|때린|맞|폭행|위협|협박|구타).*(?:었|았|당했|어요|습니다|는데|인데)",
        r"(?:스토킹|따라다니|미행|쫓아).*(?:당하|받|해요|하는데|어요|인데)",
        r"(?:훔치|훔친|훔쳤|훔쳐|도둑|도난).*(?:당|갔|어요|는데|했|잡)",
        r"(?:사기|속이|속인|속았|갈취|뜯기|뜯긴|피싱|보이스피싱).*(?:당했|봤|어요|쳤|인데|는데)",
        r"(?:몰카|불법\s*촬영|성추행|성폭행|성희롱).*(?:당|피해|했|어요|는데)",
        r"(?:빌려준|빌려줬)\s*(?:돈|금액).*(?:안\s*갚|안\s*줘|연락|먹튀|떼먹)",
        r"(?:빌려줬|빌려준).*(?:갚을\s*생각|갚을\s*의사|안\s*갚|먹튀|떼먹|사기)",
        r"(?:고소|고발|형사).*(?:하고|할까|싶|방법|해야|어떻게)",
        r"(?:명예\s*훼손|모욕|비방|욕설|악플).*(?:당하|받|어요|는데|했|어떻게)",
        r"(?:감금|납치|강도|방화).*(?:당|했|피해|어요|어떻게)",
        # 자립 패턴: 단어 자체가 충분히 특이 — 끝말 불필요
        r"(?:훔친|훔쳤|훔쳐간|도난당|도둑맞|속인|속았|사기친|밀친|밀쳤)",
    ],
    # L08: 임대차 — 보증금·전세·월세·집주인·세입자
    "L08": [
        r"(?:보증금|전세금|월세).*(?:안\s*돌려|못\s*받|안\s*줘|떼|돌려받|어떻게)",
        r"(?:집주인|임대인|건물주).*(?:안\s*줘|연락|수리\s*안|돌려\s*안|안\s*해|어떻게)",
        r"(?:전세|월세|보증금|임대차).*(?:문제|분쟁|피해|걱정|어떻게|해야)",
        r"(?:이사|퇴거|내보내|나가라|비워).*(?:하라|강요|어떻게|해야|는데)",
        r"(?:계약\s*만료|재계약|갱신|연장).*(?:거절|안\s*해|어떻게|거부)",
        r"(?:수리|누수|곰팡이|하자).*(?:안\s*해|요구|책임|집주인|어떻게)",
    ],
    # L30: 노동법 — 해고·임금체불·직장 내 괴롭힘
    "L30": [
        r"(?:해고|잘리|잘린|잘렸|잘려|짤리|짤린|짤렸|짤려|나가라|그만두|그만뒀|그만둔|퇴사).*(?:었|당했|시켰|강요|는데|어요|습니다)",
        # 자립 패턴: 해고/해직 관련 관형사형 — 끝말 불필요
        r"(?:잘린|짤린|해고된|해고당한|해고시킨)",
        r"(?:월급|급여|임금|수당).*(?:안\s*줘|못\s*받|밀려|체불|안\s*나|어요|어떻게)",
        r"(?:야근|초과\s*근무|휴일\s*출근).*(?:수당|돈|안\s*줘|안\s*나|어요)",
        r"(?:직장|회사|상사|사장|팀장|부장).*(?:괴롭|폭언|갑질|부당|모욕|차별|어떻게)",
        r"(?:퇴직금|퇴직).*(?:안\s*줘|못\s*받|계산|어떻게|해야)",
        r"(?:부당\s*해고|권고\s*사직|해고\s*통보).*(?:어떻게|방법|구제|해야)",
        r"(?:근로\s*계약서|계약서).*(?:안\s*써|없|안\s*줘|미작성|어떻게)",
    ],
    # L41: 가사법 — 이혼·양육·가정폭력
    "L41": [
        r"(?:남편|아내|배우자|남친|여친|남자\s*친구|여자\s*친구).*(?:때리|때려|때렸|때린|폭력|외도|바람|불륜|가출|숨기|숨긴)",
        r"(?:이혼|갈라서|헤어지).*(?:하고|할까|싶|방법|절차|어떻게|해야|조건)",
        r"(?:양육권|양육비|아이|자녀|애).*(?:데려|뺏|안\s*줘|보내|어떻게|해야)",
        r"(?:재산\s*분할|위자료|합의금).*(?:얼마|방법|청구|받을|어떻게)",
        r"(?:가정\s*폭력|가폭).*(?:어떻게|신고|방법|해야|신청|피해)",
        # 자립 패턴: 가사 맥락의 재산·폭력
        r"(?:재산|돈|통장).*(?:숨긴|감춘|빼돌린).*(?:남편|아내|배우자)",
        r"(?:남편|아내|배우자).*(?:재산|돈|통장).*(?:숨기|숨긴|감추|감춘|빼돌리|빼돌린)",
    ],
    # L57: 상속·신탁
    "L57": [
        r"(?:부모|아버지|어머니|할머니|할아버지|형|동생|아빠|엄마).*(?:돌아가|사망|유산|상속|재산|물려)",
        r"(?:유산|상속|재산).*(?:나누|분배|포기|빚|어떻게|얼마|받을|해야)",
        r"(?:빚|채무|부채).*(?:상속|물려).*(?:어떻게|해야|포기|거부)",
    ],
    # L38: 소비자법 — 환불·반품·사기구매
    "L38": [
        r"(?:환불|반품|교환).*(?:안\s*해|거절|안\s*돼|못\s*받|어떻게)",
        r"(?:불량|하자|고장|망가).*(?:제품|상품|물건|가전).*(?:어떻게|교환|환불)",
        r"(?:해지|해약|취소).*(?:안\s*해줘|거절|위약금|어떻게)",
        r"(?:구매|결제|주문).*(?:취소|사기|피해|환불|어떻게)",
    ],
    # L07: 교통사고
    "L07": [
        r"(?:차|자동차|오토바이|자전거|킥보드).*(?:사고|부딪|충돌|박|받|치었|넘어)",
        r"(?:교통\s*사고|뺑소니|음주\s*운전|접촉\s*사고)",
        r"(?:보험\s*처리|보험금|과실\s*비율).*(?:어떻게|안\s*해|분쟁|해야)",
    ],
    # L05: 의료법
    "L05": [
        r"(?:병원|의사|수술|진료|시술).*(?:실수|잘못|사고|피해|부작용|후유증)",
        r"(?:의료\s*사고|의료\s*과오|오진|수술\s*실패)",
        r"(?:성형|시술|약|치료).*(?:부작용|잘못|실패|하자)",
    ],
    # L11: 채권추심·개인회생
    "L11": [
        r"(?:빚|대출|이자|채무).*(?:갚을\s*수|탕감|조정|회생|파산|어떻게|못\s*갚)",
        r"(?:추심|독촉|전화).*(?:계속|매일|괴롭|어떻게|그만|해야)",
        r"(?:개인\s*회생|개인\s*파산|채무\s*조정|신용\s*회복)",
        r"면책.*(?:결정|허가|신청|받|채무|파산)",
    ],
    # L01: 민사법 — 계약·채권·민사소송
    "L01": [
        r"(?:계약|약정|합의).*(?:위반|불이행|파기|해제|해지|취소|분쟁|어떻게)",
        r"(?:돈|금전|채권|채무|대여금).*(?:돌려|받|갚|청구|변제|소멸|어떻게)",
        r"(?:내용증명|지급명령|소장|민사소송).*(?:보내|신청|제기|방법|어떻게)",
        r"(?:손해|피해).*(?:배상|청구|소송).*(?:어떻게|절차|방법|해야)",
        r"(?:가압류|가처분|민사집행).*(?:신청|방법|해야|어떻게)",
    ],
    # L06: 손해배상
    "L06": [
        r"(?:피해|손해|다쳤|망가|파손).*(?:보상|배상|물어|책임|얼마|어떻게)",
        r"(?:배상|보상|합의금).*(?:요구|청구|방법|얼마|어떻게|받을)",
        r"(?:위자료|정신적\s*피해|정신적\s*손해).*(?:청구|받을|얼마|어떻게)",
        r"(?:불법\s*행위|불법행위).*(?:손해|배상|책임|어떻게)",
    ],
    # L10: 민사집행 — 압류·경매
    "L10": [
        r"(?:압류|가압류|차압).*(?:당했|됐|어떻게|해제|이의|해야)",
        r"(?:통장|계좌|월급).*(?:압류|동결|묶|못\s*써|어떻게)",
    ],
    # L34: 개인정보
    "L34": [
        r"(?:개인\s*정보|내\s*정보).*(?:유출|도용|피해|어떻게|보호)",
        r"(?:CCTV|감시|도청).*(?:불법|사생활|침해|어떻게)",
    ],
    # L02: 부동산
    "L02": [
        r"(?:등기|소유권|명의).*(?:이전|변경|문제|어떻게|해야)",
        r"(?:분양|아파트|토지|건물).*(?:사기|하자|문제|분쟁|어떻게)",
        r"(?:명의|명의신탁).*(?:빌려|빌린|신탁|아파트|등기|문제|어떻게|해야|경매)",
        r"(?:아파트|부동산|토지|건물).*(?:명의|구입|매매|매수|경매|등기)",
        r"(?:부동산|토지|건물|아파트).*(?:매매|거래|계약|중개|사기|어떻게)",
        r"(?:매매\s*계약|부동산\s*계약|토지\s*거래).*(?:문제|분쟁|해제|취소|어떻게)",
    ],
    # L20: 세금
    "L20": [
        r"(?:세금|종소세|양도세|증여세|상속세).*(?:얼마|신고|납부|어떻게|해야|체납)",
    ],
    # L52: 미디어·명예훼손 (온라인/SNS 명예훼손)
    "L52": [
        r"(?:인터넷|SNS|게시글|댓글|유튜브|블로그).*(?:명예\s*훼손|비방|모욕|삭제|피해|악플|허위\s*사실|허위)",
        r"(?:허위\s*사실|가짜\s*뉴스|루머|소문).*(?:유포|퍼|신고|고소|어떻게)",
        r"(?:SNS|인터넷|온라인|게시글|블로그|유튜브|댓글).*(?:허위|거짓|올려|올렸).*(?:어떻게|대응|신고|고소|해야)",
    ],
    # L37: 학교폭력·소년법
    "L37": [
        r"(?:학교\s*폭력|학폭|왕따|따돌림|괴롭힘).*(?:당했|피해|어떻게|신고)",
        r"(?:미성년자|청소년|아이).*(?:범죄|사건|피해|가해|어떻게)",
    ],
    # L43: 산업재해
    "L43": [
        r"(?:산재|산업\s*재해|일하다\s*다침|작업\s*중\s*사고)",
        r"(?:공장|현장|작업장).*(?:사고|다침|부상|화상|어떻게)",
    ],
    # L25: 군형법
    "L25": [
        r"(?:군대|군인|병역|입대|전역|복무).*(?:문제|부당|어떻게|거부|면제|연기)",
        r"(?:군\s*내\s*폭력|군\s*내\s*사고|가혹\s*행위)",
    ],
    # L31: 행정법
    "L31": [
        r"(?:과태료|행정\s*처분|영업\s*정지|인허가).*(?:이의|억울|부당|어떻게|취소)",
    ],
    # L42: 저작권 — 사진·글·영상 무단 사용
    "L42": [
        r"(?:사진|그림|글|영상|동영상|음악|노래|작품|콘텐츠).*(?:허락\s*없이|무단|도용|복제|베끼|훔쳐|가져다|갖다|쓰고|사용)",
        r"(?:블로그|유튜브|인스타|SNS).*(?:사진|글|영상|콘텐츠).*(?:무단|허락\s*없이|도용|가져|사용)",
        r"(?:워터마크|저작권|저작물|표절|원작).*(?:지우|삭제|침해|위반|도용|베끼|어떻게)",
    ],
    # L15: 스타트업·창업 — 동업·법인설립·소규모 사업
    "L15": [
        r"(?:동업|공동\s*운영|공동\s*창업|같이\s*하|함께\s*하).*(?:계약|계약서|법인|설립|주의|어떻게|해야)",
        r"(?:카페|가게|음식점|식당|매장|가맹).*(?:창업|열|차리|하려|설립|운영|개업|어떻게)",
        r"(?:투자\s*비율|지분|출자).*(?:나누|정하|어떻게|계약|해야)",
    ],
}

# Pre-compile NLU patterns for performance
_NLU_COMPILED: Dict[str, List[re.Pattern]] = {
    lid: [re.compile(p) for p in patterns]
    for lid, patterns in _NLU_INTENT_PATTERNS.items()
}

# 도메인 우선순위: 문맥 특정 도메인 > 일반 형사.
# 값이 작을수록 우선순위 높음. "남편이 때려요" → L41(가사) 우선, L22(형사)가 아님.
_NLU_PRIORITY: Dict[str, int] = {
    "L08": 1,   # 임대차 (집주인/보증금 문맥)
    "L30": 1,   # 노동법 (회사/직장 문맥)
    "L41": 1,   # 가사법 (남편/아내/배우자 문맥)
    "L57": 1,   # 상속 (부모/유산 문맥)
    "L52": 1,   # 온라인 명예훼손 (SNS/인터넷 문맥 — L22보다 우선)
    "L02": 2,   # 부동산법 (명의신탁/부동산 문맥 — L10/L12보다 우선)
    "L05": 2,   # 의료법
    "L07": 2,   # 교통사고
    "L38": 2,   # 소비자법
    "L43": 2,   # 산업재해
    "L37": 2,   # 학교폭력
    "L42": 1,   # 저작권 (블로그/사진 문맥 — L52 광고·언론보다 우선)
    "L15": 2,   # 스타트업/창업 (동업/카페 문맥 — L14 회사법보다 우선)
    "L22": 5,   # 형사법 (포괄적 — 최하위 우선순위)
    # 기본값: 3
}


def _nlu_detect_intent(query: str) -> Optional[str]:
    """자연어 패턴 기반 법적 의도 감지 → 리더 ID 반환 (L01~L60).

    키워드 매칭과 달리, (상황+행위) 조합 정규식을 사용하여
    "친구한테 맞았어요" → L22, "보증금을 안 돌려줘요" → L08 등
    구어체 질문을 정확하게 분류합니다.

    여러 도메인이 매칭되면 (1) 매칭 패턴 수, (2) 우선순위로 결정.
    예: "남편이 때린 적 있어요" → L41(가사, 1매칭, 우선1) > L22(형사, 1매칭, 우선5)
    """
    matches: List[tuple] = []  # (leader_id, match_count)

    for leader_id, compiled_patterns in _NLU_COMPILED.items():
        match_count = sum(1 for p in compiled_patterns if p.search(query))
        if match_count > 0:
            matches.append((leader_id, match_count))

    if not matches:
        return None

    # 정렬: (1) 매칭 패턴 수 내림차순 (2) 우선순위 오름차순 (작을수록 우선)
    matches.sort(key=lambda x: (-x[1], _NLU_PRIORITY.get(x[0], 3)))
    best_id, best_count = matches[0]

    if len(matches) > 1:
        runner_up = matches[1]
        logger.info(
            f"[NLU] 의도 감지: {best_id}({best_count}건) > {runner_up[0]}({runner_up[1]}건) | "
            f"총 {len(matches)}개 도메인 매칭"
        )
    else:
        logger.info(f"[NLU] 의도 감지: {best_id} ({best_count}건 매칭)")

    return best_id


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

    # 2) NLU 패턴 기반 의도 감지 (키워드보다 정확한 문맥 매칭)
    nlu_leader_id = _nlu_detect_intent(query)
    if nlu_leader_id:
        nlu_leader = registry.get(nlu_leader_id)
        if nlu_leader:
            logger.info(f"[L2 NLU] {nlu_leader_id} 리더 자동 배정 (패턴 매칭)")
            return nlu_leader

    # 3) 도메인 키워드 매칭 (전체 60 Leader 매핑)
    domain_map = {
        # L01-L10
        "L01_CIVIL":        (["민법", "계약", "채권", "채무", "손해배상", "불법행위", "소유권", "물권", "용익물권", "담보물권",
                              "보증인", "위약금", "묘지", "분묘기지권", "시효",
                              "내용증명", "지급명령", "민사소송", "계약불이행", "계약해제", "대여금",
                              "부당이득", "불법행위", "하자담보", "민사조정"], "L01"),
        "L02_PROPERTY":     (["부동산법", "토지", "건물", "분양", "등기소", "소유권이전",
                              "부동산", "아파트", "명의", "명의신탁", "공인중개사", "중개"], "L02"),
        "L03_CONSTRUCTION": (["건설법", "건축", "공사", "하자", "시공", "설계", "건축허가", "착공"], "L03"),
        "L04_REDEVEL":      (["재개발", "재건축", "정비사업", "조합", "분담금", "관리처분"], "L04"),
        "L05_MEDICAL":      (["의료법", "의료사고", "의료과오", "병원", "진료", "의사", "환자", "의료분쟁",
                              "성형수술", "부작용", "수술", "오진", "설명의무"], "L05"),
        "L06_DAMAGES":      (["손해배상", "위자료", "배상금", "과실", "책임", "보상"], "L06"),
        "L07_TRAFFIC":      (["교통사고", "자동차", "운전", "사고", "충돌", "보험금", "과실비율"], "L07"),
        "L08_LEASE":        (["임대차", "전세", "월세", "보증금", "임대", "임차", "계약갱신", "대항력",
                              "집주인", "세입자", "이사", "전세금", "월세금", "방 빼", "방빼",
                              "보증금 안 돌려", "보증금 못 받", "계약 만료", "재계약"], "L08"),
        "L09_GOVCONTRACT":  (["국가계약", "조달", "입찰", "낙찰", "공사계약", "물품계약"], "L09"),
        "L10_EXECUTION":    (["민사집행", "강제집행", "배당", "압류", "가압류", "경매", "집행권원"], "L10"),

        # L11-L20
        "L11_COLLECTION":   (["채권추심", "추심", "채권", "변제", "독촉", "지급명령",
                              "개인회생", "개인파산", "채무조정", "신용회복", "사채", "보이스피싱",
                              "소멸시효", "대출", "이자 제한"], "L11"),
        "L12_AUCTION":      (["등기", "경매", "공매", "낙찰", "명도", "유찰"], "L12"),
        "L13_COMMERCIAL":   (["상사법", "상법", "상거래", "어음", "수표", "상인"], "L13"),
        "L14_CORP_MA":      (["회사법", "M&A", "인수합병", "주식양도", "법인", "이사회", "주주총회",
                              "이사", "대표이사", "합병", "충실의무", "경업금지",
                              "주주대표소송", "주식매수청구권", "배임", "회사기회유용"], "L14"),
        "L15_STARTUP":      (["스타트업", "벤처", "투자계약", "스톡옵션", "엔젤", "시드",
                              "동업", "공동 운영", "공동 창업", "카페 창업", "가게", "소규모",
                              "투자 비율", "출자", "개인사업자", "공동사업"], "L15"),
        "L16_INSURANCE":    (["보험", "보험금", "보험계약", "피보험자", "보험사고", "면책"], "L16"),
        "L17_INTL_TRADE":   (["국제거래", "수출", "수입", "무역", "중재", "국제계약"], "L17"),
        "L18_ENERGY":       (["에너지", "자원", "전력", "가스", "석유", "신재생"], "L18"),
        "L19_MARINE_AIR":   (["해상", "항공", "선박", "항공기", "운송", "해운"], "L19"),
        "L20_TAX_FIN":      (["조세", "금융", "세금", "국세", "지방세", "은행", "금융거래",
                              "소득세", "양도소득세", "종합소득세", "부가가치세", "증여세", "상속세",
                              "세율", "세액", "납세", "과세", "비과세", "면세", "환급"], "L20"),

        # L21-L30
        "L21_IT_SEC":       (["IT", "보안", "정보보호", "해킹", "사이버", "네트워크", "시스템"], "L21"),
        "L22_CRIMINAL":     (["형사", "형법", "고소", "고발", "처벌", "사기", "횡령", "배임", "폭행",
                              "갚을 생각", "빌려줬", "차용증", "공증", "떼먹", "먹튀",
                              "정당방위", "상해", "절도", "명예훼손", "모욕",
                              "맞았", "때렸", "때리", "두들겨", "구타", "폭력",
                              "협박", "위협", "스토킹", "따라다", "도둑", "훔쳤",
                              "몰카", "불법촬영", "성추행", "성폭행", "성희롱",
                              "사기당", "사기를", "돈을 안 갚", "돈을 안갚",
                              "신고", "경찰", "고소할", "고소하고", "처벌받",
                              "감금", "납치", "강도",
                              "음주운전", "도주", "도주치상", "특정범죄가중처벌",
                              "자수", "양형", "집행유예", "보이스피싱"], "L22"),
        "L23_ENTERTAIN":    (["엔터테인먼트", "연예", "연예인", "매니지먼트", "방송"], "L23"),
        "L24_TAX_APPEAL":   (["조세불복", "조세심판", "세무조사", "부과처분", "경정청구"], "L24"),
        "L25_MILITARY":     (["군형법", "군대", "군인", "병역", "군사법원", "영창",
                              "대체복무", "예비군", "복무", "입영", "전역", "군복무"], "L25"),
        "L26_IP":           (["지식재산권", "특허", "상표", "디자인", "저작권", "영업비밀"], "L26"),
        "L27_ENVIRON":      (["환경법", "환경오염", "대기", "수질", "토양", "폐기물",
                              "소음", "층간소음", "진동", "악취", "미세먼지", "환경영향평가"], "L27"),
        "L28_CUSTOMS":      (["무역", "관세", "통관", "수입신고", "FTA"], "L28"),
        "L29_GAME":         (["게임", "콘텐츠", "게임물", "등급분류", "아이템"], "L29"),
        "L30_LABOR":        (["노동법", "근로", "해고", "임금", "퇴직금", "수당", "노동조합",
                              "연차", "유급휴가", "괴롭힘", "직장 내", "최저임금", "근로기준법",
                              "잘렸", "짤렸", "해고당", "월급", "급여", "야근", "초과근무",
                              "부당해고", "직장", "회사에서", "사장님", "상사"], "L30"),

        # L31-L40
        "L31_ADMIN":        (["행정법", "행정", "인허가", "과태료", "행정처분", "영업정지", "행정소송",
                              "행정심판", "과징금", "정보공개", "처분", "이의신청"], "L31"),
        "L32_FAIRTRADE":    (["공정거래", "독점", "담합", "불공정거래", "시장지배적지위"], "L32"),
        "L33_SPACE":        (["우주항공", "위성", "발사체", "궤도", "항공우주"], "L33"),
        "L34_PRIVACY":      (["개인정보", "개인정보보호", "정보주체", "유출", "GDPR",
                              "CCTV", "감시", "이메일 감시", "잊힐 권리", "삭제 요청"], "L34"),
        "L35_CONSTITUTION": (["헌법", "위헌", "헌법소원", "기본권", "헌법재판소",
                              "집회", "시위", "표현의 자유", "양심", "긴급권", "국가긴급권"], "L35"),
        "L36_CULTURE":      (["문화", "종교", "문화재", "전통", "사찰", "교회"], "L36"),
        "L37_JUVENILE":     (["소년법", "청소년", "미성년자", "소년범", "보호처분"], "L37"),
        "L38_CONSUMER":     (["소비자", "소비자보호", "제조물책임", "환불", "약관",
                              "청약철회", "교환", "반품", "중도 해지", "불량 제품"], "L38"),
        "L39_TELECOM":      (["정보통신", "통신", "전기통신", "방송통신"], "L39"),
        "L40_HUMAN_RIGHTS": (["인권", "차별", "평등", "인권침해"], "L40"),

        # L41-L50
        "L41_DIVORCE":      (["이혼", "가족", "양육권", "양육비", "친권", "면접교섭", "재산분할",
                              "사실혼", "위자료", "혼인",
                              "남편", "아내", "배우자", "이혼하고", "이혼할", "갈라서",
                              "헤어지", "외도", "바람", "불륜", "가정폭력"], "L41"),
        "L42_COPYRIGHT":    (["저작권", "저작물", "저작자", "복제", "공연", "전송",
                              "사진 무단", "무단 사용", "허락 없이", "워터마크", "표절", "도용",
                              "원작", "2차 창작", "배포"], "L42"),
        "L43_INDUSTRIAL":   (["산업재해", "산재", "업무상재해", "요양급여", "장해급여",
                              "중대재해", "산업안전", "괴롭힘", "과로", "과로사",
                              "추락", "뇌출혈", "업무상질병"], "L43"),
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
        "L57_INHERITANCE":  (["상속", "신탁", "유산", "유언장", "상속포기", "한정승인", "신탁재산",
                              "유류분", "상속순위", "상속비율", "법정상속"], "L57"),
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

    # 4) Fallback -> 유나(CCO)가 따뜻하게 맞이
    logger.info("[L2] 전문 리더 미매칭 -> 유나(CCO) 응대")
    return {"name": "유나", "role": "Chief Content Officer", "specialty": "콘텐츠 설계", "_clevel": "CCO"}


# =============================================================
# [TIER ROUTER] Gemini 분석 -> 티어 분류 -> 리더 배정
# Gemini 100% 구조
# T1(90%): Gemini Flash 단독 | T2(8%): Gemini 보강 | T3(2%): Gemini 심층(법률충돌/문서작성)
# 모듈화: T1을 나중에 LawmadiLM으로 교체 가능
# =============================================================

def _build_leader_summary_for_gemini() -> str:
    """리더 레지스트리에서 Gemini 분석용 요약 생성"""
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
사용자의 질문을 분석하여 JSON으로 응답하세요. 답변은 절대 하지 마세요.

## 60인 리더 목록
{leader_summary}

## 분류 기준
- complexity: "simple" (단일 법률, 조문 확인, 용어 설명) | "complex" (2개 이상 법률, 판례 필요) | "critical" (법률 간 충돌, 헌법 쟁점, 다중 이해관계)
- is_document: true (고소장/소장/답변서/내용증명/고소취하서/합의서/계약서 등 법률문서 작성 요청인 경우)
- tier: 1 (simple이고 문서작성 아님) | 2 (complex이고 문서작성 아님) | 3 (critical이거나 문서작성 요청)
- leader_id: 가장 적합한 리더 1명의 ID (예: "L08"). 반드시 위 목록에서 선택.
- leader_name: 해당 리더 이름 (반드시 위 목록의 실제 이름 사용)
- leader_specialty: 전문 분야
- summary: 질문 핵심 요약 (1문장)
- is_legal: true (법률 질문) | false (비법률 질문)

## 중요 지침 — 자연어 질문 이해
1. 사용자는 법률 용어를 모릅니다. 일상 표현에서 법적 상황을 파악하세요.
2. 감정적 호소, 상황 설명, 구어체 표현도 법률 질문입니다.
3. "어떻게 해야 하나요?", "도와주세요" 같은 표현은 법적 도움 요청입니다.
4. 애매한 경우 is_legal=true로 분류하세요. (Lawmadi는 법률 시스템)

## ⚠️ 핵심 분류 원칙 — 행위의 본질 기준
리더를 배정할 때 **배경(직장/학교/가정)이 아닌, 핵심 불법행위의 법적 성격**으로 판단하세요.

**온라인/SNS 명예훼손·허위사실 유포 → 광고·언론(L52) 미소** (인터넷·SNS·게시글·댓글·블로그·유튜브 등 온라인 매체)
**오프라인 대면 모욕·폭언·비방 → 형사법(L22) 무결** (직접 대면, 전화, 오프라인 상황)
**부당해고·임금체불·직장 내 괴롭힘 → 노동법(L30)** (근로관계에서 발생하는 문제, 단 괴롭힘으로 산재 인정 → L43)
**폭행·사기·절도·횡령·음주운전 도주·도주치상 → 형사법(L22)** (발생 장소와 무관, 형사 처벌·양형이 핵심인 경우. 돈을 빌려줬는데 처음부터 갚을 생각이 없었던 경우 = 사기)
**동업·공동사업·소규모 창업·카페/가게/음식점 → 스타트업(L15) 별하** (소규모 사업체 설립·동업계약·투자비율)
**직장 괴롭힘으로 인한 산업재해·과로사·업무상질병 → 산업재해(L43)** (산재 인정·보상이 핵심인 경우)
**이혼·양육권·가정폭력 → 가사법(L41)** (가족 관계 문제)
**저작권 침해·무단 사용 → 저작권(L42)** (창작물 관련)
**의료사고·의료과실 → 의료법(L05)** (의료 행위 관련)
**명의신탁·부동산 명의·부동산 거래 → 부동산법(L02) 보늬** (명의신탁, 부동산 명의 문제)
**경매·압류·가압류·강제집행 → 민사집행(L10) 결휘** (재산 집행 관련)

예시:
- "직장 동료가 SNS에 허위사실 유포" → **광고·언론(L52)** (온라인 명예훼손은 미디어법 관할)
- "아버지 명의로 아파트를 구입, 명의만 빌려드린 것" → **부동산법(L02)** (명의신탁은 부동산법)
- "직장에서 해고당했다" → **노동법(L30)** (근로관계 종료)
- "직장 상사가 때렸다" → **형사법(L22)** (폭행, 장소가 직장이라도 형사 문제)
- "직장에서 월급을 안 준다" → **노동법(L30)** (임금 체불)
- "돈 빌려줬는데 갚을 생각이 없었다" → **형사법(L22)** (차용 사기, 채권추심이 아닌 형사 사기)
- "블로그 사진을 업체가 광고에 무단 사용" → **저작권(L42)** ('광고'가 포함되어도 핵심은 저작권 침해)
- "친구와 카페 동업, 법인 설립" → **스타트업(L15)** (소규모 동업·창업은 스타트업)

## 분류 예시 (구어체 / 자연어 포함)
질문: "친구한테 맞았어요"
→ {{"tier":1,"complexity":"simple","is_document":false,"leader_id":"L22","leader_name":"무결","leader_specialty":"형사법","summary":"폭행 피해","is_legal":true}}

질문: "집주인이 보증금을 안 돌려줘요"
→ {{"tier":1,"complexity":"simple","is_document":false,"leader_id":"L08","leader_name":"온유","leader_specialty":"임대차","summary":"보증금 반환 거부","is_legal":true}}

질문: "회사에서 갑자기 잘렸어요"
→ {{"tier":1,"complexity":"simple","is_document":false,"leader_id":"L30","leader_name":"담우","leader_specialty":"노동법","summary":"부당해고","is_legal":true}}

질문: "남편이 바람을 피웠어요"
→ {{"tier":2,"complexity":"complex","is_document":false,"leader_id":"L41","leader_name":"산들","leader_specialty":"이혼·가족","summary":"배우자 외도 이혼","is_legal":true}}

질문: "부모님이 돌아가셨는데 빚이 있어요"
→ {{"tier":2,"complexity":"complex","is_document":false,"leader_id":"L57","leader_name":"세움","leader_specialty":"상속·신탁","summary":"상속 채무","is_legal":true}}

질문: "인터넷에서 물건 샀는데 사기 같아요"
→ {{"tier":1,"complexity":"simple","is_document":false,"leader_id":"L22","leader_name":"무결","leader_specialty":"형사법","summary":"인터넷 사기 피해","is_legal":true}}

질문: "지인에게 돈을 빌려줬는데 처음부터 갚을 생각이 없었던 것 같아요"
→ {{"tier":2,"complexity":"complex","is_document":false,"leader_id":"L22","leader_name":"무결","leader_specialty":"형사법","summary":"차용 사기 의심","is_legal":true}}

질문: "월급을 3달째 못 받고 있어요"
→ {{"tier":1,"complexity":"simple","is_document":false,"leader_id":"L30","leader_name":"담우","leader_specialty":"노동법","summary":"임금 체불","is_legal":true}}

질문: "교통사고 났는데 어떻게 해요"
→ {{"tier":1,"complexity":"simple","is_document":false,"leader_id":"L07","leader_name":"하늬","leader_specialty":"교통사고","summary":"교통사고 처리","is_legal":true}}

질문: "통장이 압류됐어요"
→ {{"tier":1,"complexity":"simple","is_document":false,"leader_id":"L10","leader_name":"결휘","leader_specialty":"민사집행","summary":"통장 압류","is_legal":true}}

질문: "전 직장 동료가 SNS에 허위사실을 올려서 퇴사했어요"
→ {{"tier":1,"complexity":"simple","is_document":false,"leader_id":"L52","leader_name":"미소","leader_specialty":"광고·언론","summary":"SNS 명예훼손·허위사실 유포","is_legal":true}}

질문: "아버지 명의로 아파트를 구입했는데 명의만 빌려드린 거예요"
→ {{"tier":2,"complexity":"complex","is_document":false,"leader_id":"L02","leader_name":"보늬","leader_specialty":"부동산법","summary":"부동산 명의신탁","is_legal":true}}

질문: "블로그 사진을 업체가 무단으로 광고에 사용했어요"
→ {{"tier":1,"complexity":"simple","is_document":false,"leader_id":"L42","leader_name":"하람","leader_specialty":"저작권","summary":"사진 저작권 침해","is_legal":true}}

질문: "병원 수술 실수로 합병증이 생겼어요"
→ {{"tier":2,"complexity":"complex","is_document":false,"leader_id":"L05","leader_name":"연우","leader_specialty":"의료법","summary":"의료과실 손해배상","is_legal":true}}

질문: "동업으로 카페를 하려는데 계약서 주의사항이요"
→ {{"tier":2,"complexity":"complex","is_document":false,"leader_id":"L15","leader_name":"별하","leader_specialty":"스타트업","summary":"동업 카페 창업 계약","is_legal":true}}

질문: "개인회생이랑 파산 중 뭐가 유리한가요"
→ {{"tier":2,"complexity":"complex","is_document":false,"leader_id":"L11","leader_name":"오름","leader_specialty":"채권추심","summary":"개인회생·파산 비교","is_legal":true}}

질문: "오늘 날씨 어때요?"
→ {{"tier":0,"complexity":"simple","is_document":false,"leader_id":"L60","leader_name":"마디","leader_specialty":"시스템 총괄","summary":"비법률 질문","is_legal":false}}

질문: "점심 뭐 먹을까요?"
→ {{"tier":0,"complexity":"simple","is_document":false,"leader_id":"L60","leader_name":"마디","leader_specialty":"시스템 총괄","summary":"비법률 질문","is_legal":false}}

질문: "영화 추천해줘"
→ {{"tier":0,"complexity":"simple","is_document":false,"leader_id":"L60","leader_name":"마디","leader_specialty":"시스템 총괄","summary":"비법률 질문","is_legal":false}}

질문: "코딩 배우고 싶어요"
→ {{"tier":0,"complexity":"simple","is_document":false,"leader_id":"L60","leader_name":"마디","leader_specialty":"시스템 총괄","summary":"비법률 질문","is_legal":false}}

## 비법률 판단 기준
- 법률, 법적 분쟁, 권리침해, 계약, 피해, 사건과 무관한 일상 질문은 is_legal=false
- 날씨, 음식, 여행, 영화, 게임, 취미, 인사, IT, 학업 등은 모두 비법률

반드시 위 목록에서 leader_id, leader_name을 선택하고 아래 JSON 형식만 출력하세요:
{{"tier": 1, "complexity": "simple", "is_document": false, "leader_id": "L08", "leader_name": "리더이름", "leader_specialty": "전문분야", "summary": "요약", "is_legal": true}}"""


_GEMINI_CLASSIFY_TIMEOUT = 10  # seconds


async def _gemini_analyze_query(query: str) -> Optional[Dict[str, Any]]:
    """Gemini로 질문 분석/분류/리더 배정 (답변 X).
    동기 Gemini SDK 호출을 run_in_executor로 감싸고 10초 타임아웃 적용.
    타임아웃 시 None 반환 → 기존 키워드 fallback 경로 자동 작동.
    """
    genai_client = _RUNTIME.get("genai_client")
    if not genai_client:
        logger.warning("Gemini 클라이언트 없음 -> 키워드 기반 fallback")
        return None

    leader_summary = _build_leader_summary_for_gemini()

    def _sync_call():
        """429 시 자동 모델 전환 포함"""
        for _attempt in range(3):
            model_name = get_model()
            try:
                resp = genai_client.models.generate_content(
                    model=model_name,
                    contents=f"질문: {query}",
                    config={
                        "system_instruction": TIER_ANALYSIS_PROMPT.format(leader_summary=leader_summary),
                        "max_output_tokens": 800,
                        "temperature": 0.1,
                    },
                )
                return resp.text.strip() if resp.text else ""
            except Exception as e:
                if is_quota_error(e) and _attempt < 2:
                    on_quota_error()
                    continue
                raise

    try:
        loop = asyncio.get_running_loop()
        text = await asyncio.wait_for(
            loop.run_in_executor(None, _sync_call),
            timeout=_GEMINI_CLASSIFY_TIMEOUT,
        )
        # JSON 추출 (중첩 JSON 및 코드블록 지원)
        result = _safe_extract_json(text)
        if result:
            logger.info(f"[Tier Router] Gemini 분석: tier={result.get('tier')}, "
                       f"leader={result.get('leader_name')}({result.get('leader_id')}), "
                       f"complexity={result.get('complexity')}, is_document={result.get('is_document')}")
            return result
        logger.warning(f"Gemini 분석 JSON 파싱 실패: {text[:200]}")
        return None
    except asyncio.TimeoutError:
        logger.warning(f"Gemini 분류 타임아웃 ({_GEMINI_CLASSIFY_TIMEOUT}s) -> 키워드 fallback")
        return None
    except Exception as e:
        logger.warning(f"Gemini 분석 실패: {e}")
        return None


def _fallback_tier_classification(query: str) -> Dict[str, Any]:
    """Gemini 실패 시 키워드 기반 fallback 분류"""
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

    # 비법률 판정: NLU 패턴 매칭이면 무조건 법률, 아니면 비법률 키워드로 판정
    nlu_match = _nlu_detect_intent(query)
    if nlu_match:
        is_legal = True
    else:
        non_legal_keywords = [
            # 일상생활
            "날씨", "기온", "비 올", "눈 올", "미세먼지",
            "요리", "레시피", "맛집", "점심", "저녁", "아침", "뭐 먹", "메뉴",
            "카페", "커피", "음식",
            # 엔터테인먼트
            "영화 추천", "영화", "드라마", "넷플릭스", "유튜브",
            "음악 추천", "노래", "가수", "아이돌", "콘서트",
            "게임", "스포츠", "축구", "야구", "농구",
            # 여행/취미
            "여행지", "여행", "관광", "호텔", "항공", "비행기",
            "취미", "운동 방법", "다이어트", "헬스", "요가", "등산",
            # 인사/잡담
            "안녕하세요", "반갑습니다", "안녕", "하이", "헬로",
            "자기소개", "너 누구", "넌 뭐", "이름이 뭐",
            "고마워", "감사합니다", "수고",
            # IT/기술
            "코딩", "프로그래밍", "파이썬", "자바", "엑셀",
            "컴퓨터", "스마트폰", "아이폰", "갤럭시",
            # 교육/학업
            "수학", "영어", "시험", "공부", "대학",
            # 쇼핑/생활
            "쇼핑", "할인", "세일", "배송",
            "택배", "반품", "교환",
        ]
        is_legal = not any(kw in query for kw in non_legal_keywords)

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
