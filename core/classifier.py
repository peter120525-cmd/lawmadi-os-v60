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
from utils.helpers import _safe_extract_json, _safe_extract_gemini_text

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
    # L22: 형사법 — 폭행·협박·사기·절도·성범죄·음주운전 등
    "L22": [
        r"(?:누군가|친구|사람|남자|여자|상대|옆\s*사람|동네|이웃).*(?:때리|때려|때렸|때린|맞|맞은|폭행|위협|협박|치|구타|밀치|밀친)",
        r"(?:때리|때려|때렸|때린|맞|폭행|위협|협박|구타).*(?:었|았|당했|어요|습니다|는데|인데)",
        r"(?:스토킹|따라다니|미행|쫓아).*(?:당하|받|해요|하는데|어요|인데)",
        r"(?:훔치|훔친|훔쳤|훔쳐|도둑|도난).*(?:당|갔|어요|는데|했|잡)",
        r"(?:사기|속이|속인|속았|갈취|뜯기|뜯긴|피싱|보이스피싱).*(?:당했|봤|어요|쳤|인데|는데)",
        r"(?:몰카|불법\s*촬영|성추행|성폭행|성희롱).*(?:당|피해|했|어요|는데)",
        r"(?:빌려준|빌려줬)\s*(?:돈|금액).*(?:안\s*갚|안\s*줘|연락|먹튀|떼먹)",
        r"(?:빌려줬|빌려준).*(?:갚을\s*생각|갚을\s*의사|안\s*갚|먹튀|떼먹|사기)",
        # "돈 빌려줬는데 안 갚아" — 역순도 매칭 (돈이 앞에 오는 경우)
        r"(?:돈|금액).*(?:빌려줬|빌려준).*(?:안\s*갚|안\s*줘|먹튀|떼먹|갚을\s*생각|갚을\s*의사|안\s*돌려|없었)",
        r"(?:고소|고발|형사).*(?:하고|할까|싶|방법|해야|어떻게)",
        r"(?:명예\s*훼손|모욕|비방|욕설|악플).*(?:당하|받|어요|는데|했|어떻게)",
        r"(?:감금|납치|강도|방화).*(?:당|했|피해|어요|어떻게)",
        # 음주운전·도주·양형 — 단독 패턴
        r"(?:음주\s*운전|음주\s*측정|음주\s*단속|음주운전).*(?:적발|걸렸|했|어떻게|처벌|벌금|면허)",
        r"(?:도주\s*치상|도주치상|뺑소니).*(?:했|어떻게|처벌|해야)",
        r"(?:자수|양형|집행유예|선처).*(?:하면|할까|어떻게|방법|해야|받을)",
        # 자립 패턴: 단어 자체가 충분히 특이 — 끝말 불필요
        r"(?:훔친|훔쳤|훔쳐간|도난당|도둑맞|속인|속았|사기친|밀친|밀쳤)",
    ],
    # L08: 임대차 — 보증금·전세·월세·집주인·세입자
    "L08": [
        r"(?:보증금|전세금|월세).*(?:안\s*돌려|못\s*받|안\s*줘|떼|돌려받|어떻게)",
        r"(?:집주인|임대인|건물주).*(?:안\s*줘|연락|수리\s*안|돌려\s*안|안\s*해|어떻게)",
        r"(?:전세|월세|보증금|임대차).*(?:문제|분쟁|피해|걱정|어떻게|해야)",
        r"(?:이사\s*(?:나가|하라|가라)|퇴거|내보내|나가라|비워).*(?:강요|어떻게|해야|는데)",
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
        r"(?:양육권|양육비|아이(?!템)|자녀|애).*(?:데려|뺏|안\s*줘|보내|어떻게|해야)",
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
    # L07: 교통사고 (음주운전 형사처벌은 L22 관할)
    "L07": [
        r"(?:차|자동차|오토바이|자전거|킥보드).*(?:사고|부딪|충돌|박|받|치었|넘어)",
        r"(?:교통\s*사고|접촉\s*사고)",
        r"(?:보험\s*처리|과실\s*비율).*(?:어떻게|안\s*해|분쟁|해야)",
        r"(?:교통사고|차\s*사고).*(?:보험금|보험\s*처리|합의금|어떻게)",
    ],
    # L05: 의료법
    "L05": [
        r"(?:병원|의사|수술|진료|시술|의료진).*(?:실수|잘못|사고|피해|부작용|후유증|합병증|과실)",
        r"(?:의료\s*사고|의료\s*과오|오진|수술\s*실패|의료\s*과실)",
        r"(?:성형|시술|약|치료).*(?:부작용|잘못|실패|하자)",
        r"(?:합병증|재수술|후유증).*(?:생기|발생|생겨|어떻게|책임|배상|청구)",
        r"(?:병원|의사|의료진).*(?:불가항력|책임|과실|손해|배상)",
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
        r"(?:계약|약정).*(?:손해배상|손해\s*배상|배상|소송)",
        r"(?:금전|채권|채무|대여금).*(?:돌려|받|갚|청구|변제|소멸|어떻게)",
        r"(?:내용증명|지급명령|소장|민사소송).*(?:보내|신청|제기|방법|어떻게)",
        r"(?:가압류|가처분).*(?:신청|방법|해야|어떻게)",
    ],
    # L06: 손해배상
    "L06": [
        r"(?:피해|손해|다쳤|망가|파손).*(?:보상|배상|물어|책임|얼마|어떻게)",
        r"(?:배상|보상|합의금).*(?:요구|청구|방법|얼마|어떻게|받을)",
        r"(?:위자료|정신적\s*피해|정신적\s*손해).*(?:청구|받을|얼마|어떻게)",
        r"(?:불법\s*행위|불법행위).*(?:손해|배상|책임|어떻게)",
        r"(?:손해|피해).*(?:청구|보상).*(?:어떻게|방법|절차|해야)",
    ],
    # L10: 민사집행 — 압류·경매·강제집행
    "L10": [
        r"(?:압류|가압류|차압).*(?:당했|됐|어떻게|해제|이의|해야)",
        r"(?:통장|계좌|월급).*(?:압류|동결|묶|못\s*써|어떻게)",
        r"(?:민사\s*집행|강제\s*집행|강제집행).*(?:방법|절차|어떻게|해야|신청)",
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
        # 분양권·재건축입주권·부동산 파생 쿼리
        r"(?:분양권|분양\s*권).*(?:전매|매매|양도|문제|어떻게|해야)",
        r"(?:재건축|재개발).*(?:입주권|입주\s*권|분양|매매|투자|어떻게)",
        r"(?:부동산|아파트|토지).*(?:계약\s*사기|이중\s*계약|하자|매매\s*사기)",
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
        r"(?:학교\s*폭력|학폭|왕따|따돌림).*(?:당했|피해|어떻게|신고|가해|처벌|처분)",
        r"(?:미성년자|청소년|아이(?!템)).*(?:범죄|사건|피해|가해|어떻게|폭행|맞|때리|때렸)",
        r"(?:학교|학교에서|교실|학생).*(?:맞았|때렸|때리|폭행|괴롭|왕따|따돌)",
        r"(?:학폭|학교\s*폭력).*(?:가해자|피해자|형사|처벌|신고|위원회|어떻게)",
        # 자립 패턴: 학폭 관련 강한 신호
        r"(?:학폭\s*위원회|학교폭력\s*위원회|학폭\s*가해|학폭\s*피해)",
    ],
    # L43: 산업재해
    "L43": [
        r"(?:산재|산업\s*재해|일하다\s*다침|작업\s*중\s*사고)",
        r"(?:공장|현장|작업장).*(?:사고|다침|부상|화상|어떻게)",
        # 직장 괴롭힘/과로 → 산재 인정 맥락
        r"(?:직장|회사|업무|근무).*(?:괴롭힘|괴롭|스트레스|과로).*(?:산재|산업\s*재해|우울증|질병|쓰러|사망)",
        r"(?:괴롭힘|과로|스트레스).*(?:산재\s*신청|산재\s*인정|업무상\s*질병|산재\s*보상)",
    ],
    # L25: 군형법
    "L25": [
        r"(?:군대|군인|병역|입대|전역|복무).*(?:폭행|폭력|사고|괴롭|가혹|문제|부당|어떻게|거부|면제|연기)",
        r"(?:군\s*내\s*폭력|군\s*내\s*사고|가혹\s*행위|군대\s*폭행|군인\s*폭행)",
    ],
    # L31: 행정법
    "L31": [
        r"(?:과태료|행정\s*처분|영업\s*정지|인허가).*(?:이의|불복|억울|부당|취소|소송|해야|어떻게)",
        r"(?:행정\s*소송|행정소송|행정\s*심판|행정심판).*(?:절차|방법|제기|청구|어떻게|해야)",
        r"(?:행정\s*처분|행정처분).*(?:불복|취소\s*소송|이의\s*신청|항고|어떻게|해야)",
    ],
    # L42: 저작권 — 사진·글·영상 무단 사용
    "L42": [
        r"(?:사진|그림|글|영상|동영상|음악|노래|작품|콘텐츠).*(?:허락\s*없이|무단|도용|복제|베끼|훔쳐|가져다|갖다|쓰고|사용)",
        r"(?:블로그|유튜브|인스타|SNS).*(?:사진|글|영상|콘텐츠).*(?:무단|허락\s*없이|도용|가져|사용)",
        r"(?:워터마크|저작권|저작물|표절|원작).*(?:지우|삭제|침해|위반|도용|베끼|어떻게)",
    ],
    # L04: 재개발·재건축 — 정비사업·조합·입주권
    "L04": [
        r"(?:재개발|재건축|정비\s*사업|정비\s*구역).*(?:조합|분담금|이주|보상|어떻게|해야|문제|분쟁)",
        r"(?:조합원|입주권|관리처분).*(?:분양|매매|문제|어떻게|해야|분쟁)",
        r"(?:재개발|재건축).*(?:구역|빌라|아파트|입주|매수|투자|감정|평가)",
    ],
    # L14: 회사법·M&A — 이사배임·주주대표소송·합병
    "L14": [
        r"(?:이사\s*배임|이사\s*횡령|대표이사\s*배임|대표이사\s*횡령|이사\s*충실의무|이사\s*경업금지|이사\s*해임|이사\s*선임)",
        r"(?:주주|소수주주).*(?:대표소송|대표\s*소송|권리|총회|의결|배당|어떻게)",
        r"(?:합병|분할|인수|M&A).*(?:절차|반대|매수청구|가액|어떻게|해야)",
        r"(?:법인|회사).*(?:설립|해산|청산|이사회|정관|어떻게|해야)",
    ],
    # L16: 보험 — 보험금 거절·보험사기·약관
    "L16": [
        r"(?:보험금|보험\s*금).*(?:거절|거부|안\s*줘|못\s*받|지급\s*거절|삭감|부지급|감액)",
        r"(?:보험사|보험\s*회사).*(?:거절|거부|안\s*해|지급\s*안|어떻게|분쟁)",
        r"(?:보험\s*사기|보험\s*청구).*(?:의심|조사|어떻게|해야|방법)",
        r"(?:약관|면책|보험\s*계약).*(?:불공정|부당|어떻게|해석|분쟁)",
        r"(?:보험금|보험).*(?:거절당|거부당|안\s*나와|안\s*내줘|분쟁|약관)",
    ],
    # L26: 지식재산권 — 특허침해·상표도용·영업비밀
    "L26": [
        r"(?:특허|실용신안).*(?:침해|등록|출원|거절|어떻게|해야|분쟁|소송)",
        r"(?:상표|브랜드|상호).*(?:도용|침해|등록|유사|어떻게|분쟁|소송)",
        r"(?:영업\s*비밀|기술\s*유출|핵심\s*기술).*(?:유출|침해|보호|어떻게|해야)",
        r"(?:디자인\s*권|디자인\s*특허).*(?:침해|등록|어떻게|분쟁)",
    ],
    # L15: 스타트업·창업 — 동업·법인설립·소규모 사업
    "L15": [
        r"(?:동업|공동\s*운영|공동\s*창업|같이\s*하|함께\s*하).*(?:계약|계약서|법인|설립|주의|어떻게|해야)",
        r"(?:카페|가게|음식점|식당|매장|가맹).*(?:창업|열|차리|하려|설립|운영|개업|어떻게)",
        r"(?:투자\s*비율|지분|출자).*(?:나누|정하|어떻게|계약|해야)",
    ],
    # L03: 건설법 — 건축허가·하자보수·공사대금·건설분쟁
    "L03": [
        r"(?:건축\s*허가|건축허가|착공\s*신고|착공신고).*(?:절차|방법|거부|반려|어떻게|해야)",
        r"(?:건물|아파트|주택|빌딩).*(?:하자|누수|균열|부실\s*시공|하자\s*보수).*(?:책임|청구|어떻게|해야|문제)",
        r"(?:공사\s*대금|공사대금|기성금|준공금).*(?:안\s*줘|못\s*받|체불|미지급|청구|어떻게)",
        r"(?:시공\s*업체|건설\s*회사|시공사|건설사).*(?:부실|하자|도망|파산|어떻게|문제|분쟁)",
        r"(?:건설|건축|시공).*(?:분쟁|소송|중재|클레임|어떻게|해야)",
    ],
    # L09: 국가계약 — 입찰·낙찰·조달·국가계약분쟁
    "L09": [
        r"(?:입찰|낙찰|유찰).*(?:자격|조건|취소|이의|부정|담합|문제|분쟁|어떻게|해야)",
        r"(?:조달|조달청|나라장터).*(?:등록|입찰|계약|절차|문제|어떻게|해야)",
        r"(?:국가\s*계약|관급\s*공사|정부\s*조달).*(?:분쟁|이의|해제|문제|어떻게|해야|절차)",
        r"(?:공사\s*계약|용역\s*계약|물품\s*계약).*(?:국가|정부|관급|조달).*(?:문제|분쟁|어떻게)",
    ],
    # L12: 등기·경매 — 경매참여·배당·등기절차
    "L12": [
        r"(?:경매|공매).*(?:참여|입찰|낙찰|유찰|배당|명도|절차|어떻게|해야)",
        r"(?:등기|등기부).*(?:열람|변경|말소|이전|경정|절차|방법|어떻게|해야)",
        r"(?:배당|배당금).*(?:이의|요구|순위|계산|받을|어떻게|해야)",
        r"(?:낙찰|낙찰자).*(?:명도|인도|대금|잔금|어떻게|해야|절차)",
    ],
    # L13: 상사법 — 상거래·어음수표·상사분쟁
    "L13": [
        r"(?:어음|수표|약속\s*어음).*(?:부도|부정|위조|배서|추심|지급|거절|어떻게|해야)",
        r"(?:상거래|상사|상법).*(?:분쟁|문제|소송|어떻게|해야|절차)",
        r"(?:상인|상행위|상사\s*채권).*(?:시효|소멸|권리|청구|어떻게|해야)",
    ],
    # L17: 국제거래 — 국제계약·준거법·국제중재
    "L17": [
        r"(?:국제\s*계약|국제계약|국제\s*거래|국제거래|해외\s*거래).*(?:분쟁|준거법|중재|소송|어떻게|해야)",
        r"(?:준거법|국제\s*중재|ICC|UNCITRAL).*(?:선택|적용|절차|어떻게|해야)",
        r"(?:해외|외국|수출|수입).*(?:계약|거래|대금|클레임|분쟁).*(?:어떻게|해야|방법|절차)",
    ],
    # L18: 에너지·자원 — 에너지사업·발전소·자원개발
    "L18": [
        r"(?:발전소|태양광|풍력|원전|원자력).*(?:인허가|건설|운영|분쟁|사고|어떻게|해야)",
        r"(?:에너지\s*사업|에너지사업|전력\s*사업).*(?:인허가|규제|분쟁|어떻게|해야|절차)",
        r"(?:자원\s*개발|광업|광물|채굴).*(?:허가|규제|분쟁|어떻게|해야|절차)",
        r"(?:신재생\s*에너지|신재생에너지|ESS|전기\s*사업).*(?:인허가|보조금|분쟁|어떻게|해야)",
    ],
    # L19: 해상·항공 — 선박사고·해상운송·항공분쟁
    "L19": [
        r"(?:선박|배).*(?:사고|충돌|침몰|좌초|보험|어떻게|해야|분쟁)",
        r"(?:해상\s*운송|해상운송|해운|용선).*(?:계약|분쟁|클레임|손해|어떻게|해야)",
        r"(?:항공|비행기|항공사).*(?:지연|취소|사고|배상|분쟁|어떻게|해야)",
        r"(?:화물|컨테이너).*(?:해상|선박|운송).*(?:손해|분실|분쟁|어떻게)",
    ],
    # L21: IT·보안 — 해킹·사이버범죄·정보보호
    "L21": [
        r"(?:해킹|해커|랜섬웨어|디도스|DDoS).*(?:당했|피해|공격|신고|어떻게|해야|대응)",
        r"(?:사이버\s*범죄|사이버범죄|인터넷\s*범죄).*(?:신고|피해|처벌|어떻게|해야)",
        r"(?:정보\s*보호|정보보호|보안\s*사고).*(?:의무|위반|규제|어떻게|해야|절차)",
        r"(?:서버|시스템|네트워크).*(?:침입|침해|해킹|보안|어떻게|해야)",
    ],
    # L23: 엔터테인먼트 — 연예계약·전속계약·매니지먼트
    "L23": [
        r"(?:전속\s*계약|전속계약|연예\s*계약).*(?:해지|위반|부당|분쟁|어떻게|해야)",
        r"(?:매니지먼트|소속사|기획사|엔터).*(?:계약|분쟁|갈등|해지|부당|어떻게|해야)",
        r"(?:연예인|아이돌|배우|가수).*(?:계약|전속|위약금|분쟁|어떻게|해야)",
        r"(?:초상권|퍼블리시티권|출연료).*(?:침해|미지급|분쟁|어떻게|해야|청구)",
    ],
    # L24: 조세불복 — 세무조사·과세처분·조세심판
    "L24": [
        r"(?:세무\s*조사|세무조사).*(?:대응|방법|통지|거부|어떻게|해야|준비)",
        r"(?:과세\s*처분|과세처분|부과\s*처분).*(?:이의|불복|취소|어떻게|해야|절차)",
        r"(?:조세\s*심판|조세심판|국세\s*심판).*(?:청구|절차|방법|어떻게|해야)",
        r"(?:경정\s*청구|경정청구|수정\s*신고).*(?:방법|절차|기한|어떻게|해야)",
    ],
    # L27: 환경법 — 환경오염·소음·환경영향평가
    "L27": [
        r"(?:환경\s*오염|환경오염|수질\s*오염|토양\s*오염|대기\s*오염).*(?:피해|배상|신고|어떻게|해야)",
        r"(?:소음|층간\s*소음|공사\s*소음|진동|악취).*(?:피해|신고|기준|어떻게|해야|분쟁)",
        r"(?:환경\s*영향\s*평가|환경영향평가).*(?:절차|부실|이의|어떻게|해야|문제)",
        r"(?:폐기물|쓰레기|폐수).*(?:불법|투기|처리|신고|어떻게|해야|문제)",
    ],
    # L28: 무역·관세 — 수입통관·관세·FTA원산지
    "L28": [
        r"(?:수입\s*통관|수입통관|수출입\s*통관|수출입통관|통관\s*절차|통관).*(?:지연|거부|문제|분쟁|어떻게|해야|방법)",
        r"(?:관세|관세율|관세\s*환급).*(?:부과|이의|환급|문제|분쟁|어떻게|해야|절차|감면)",
        r"(?:FTA|원산지\s*증명|원산지증명).*(?:발급|적용|혜택|어떻게|해야|절차)",
        r"(?:수입|수출|수출입).*(?:규제|금지|허가|신고|통관).*(?:문제|분쟁|어떻게|해야|절차|방법)",
    ],
    # L29: 게임·콘텐츠 — 게임규제·환전·콘텐츠분쟁
    "L29": [
        r"(?:게임\s*아이템|게임아이템|아이템\s*거래).*(?:사기|환불|분쟁|어떻게|해야)",
        r"(?:게임|아이템).*(?:환불|사기|피해).*(?:어떻게|해야|방법|문제)",
        r"(?:게임\s*규제|게임규제|게임\s*등급).*(?:심의|분류|이의|어떻게|해야)",
        r"(?:게임\s*머니|게임머니|게임\s*환전).*(?:불법|규제|문제|어떻게|해야)",
        r"(?:콘텐츠|디지털\s*콘텐츠).*(?:분쟁|환불|이용|해지|계약|어떻게|해야)",
    ],
    # L32: 공정거래 — 독점·카르텔·불공정거래·가맹
    "L32": [
        r"(?:독점|시장\s*지배|시장지배).*(?:남용|규제|신고|어떻게|해야|문제)",
        r"(?:카르텔|담합|입찰\s*담합).*(?:신고|제재|과징금|위반|처벌|문제|어떻게|해야|의심)",
        r"(?:불공정\s*거래|불공정거래|갑질).*(?:신고|피해|규제|어떻게|해야|대응)",
        r"(?:가맹|프랜차이즈|가맹\s*사업).*(?:분쟁|부당|해지|위약|어떻게|해야|피해)",
    ],
    # L35: 헌법 — 기본권침해·위헌심판·헌법소원
    "L35": [
        r"(?:기본권|기본\s*권리).*(?:침해|제한|보장|어떻게|해야|구제)",
        r"(?:위헌\s*심판|위헌심판|위헌\s*법률).*(?:청구|절차|방법|어떻게|해야)",
        r"(?:헌법\s*소원|헌법소원).*(?:청구|절차|요건|방법|어떻게|해야)",
        r"(?:집회|시위|표현의\s*자유).*(?:제한|금지|침해|허가|어떻게|해야|신고)",
    ],
    # L39: 정보통신 — 통신분쟁·방송규제·전파
    "L39": [
        r"(?:통신\s*분쟁|통신분쟁|통신\s*요금|통신비).*(?:이의|조정|과다|분쟁|문제|어떻게|해야)",
        r"(?:방송\s*규제|방송규제|방송\s*심의|방송).*(?:규제|위반|제재|이의|분쟁|어떻게|해야)",
        r"(?:전파|주파수).*(?:허가|간섭|위반|규제|어떻게|해야)",
        r"(?:인터넷\s*서비스|ISP|통신사).*(?:해지|위약금|장애|분쟁|어떻게|해야)",
        r"(?:인터넷|통신|ISP|통신사).*(?:해지|위약금).*(?:어떻게|해야|분쟁|문제)",
    ],
    # L40: 인권 — 차별·인권침해·혐오표현
    "L40": [
        r"(?:차별|인종\s*차별|성차별|장애\s*차별|나이\s*차별|고용\s*차별).*(?:당했|피해|신고|구제|어떻게|해야)",
        r"(?:인권\s*침해|인권침해).*(?:당했|피해|신고|구제|어떻게|해야|진정)",
        r"(?:혐오\s*표현|혐오표현|혐오\s*발언).*(?:신고|처벌|규제|어떻게|해야|피해)",
        r"(?:국가인권위|인권위).*(?:진정|신고|절차|방법|어떻게|해야)",
    ],
    # L44: 사회복지 — 기초생활·복지급여·긴급지원
    "L44": [
        r"(?:기초\s*생활|기초생활|기초\s*수급).*(?:수급|신청|탈락|자격|어떻게|해야|조건)",
        r"(?:복지\s*급여|복지급여|생계\s*급여).*(?:신청|삭감|중단|이의|어떻게|해야)",
        r"(?:긴급\s*지원|긴급지원|긴급\s*복지).*(?:신청|자격|방법|어떻게|해야|절차)",
        r"(?:사회\s*복지|사회복지|복지\s*서비스).*(?:이용|신청|거부|자격|어떻게|해야)",
    ],
    # L45: 교육·청소년 — 학원분쟁·교육차별·교권
    "L45": [
        r"(?:학원|학원비|학원\s*계약).*(?:환불|해지|분쟁|어떻게|해야|위약금)",
        r"(?:교육\s*차별|교육차별|입학\s*차별).*(?:당했|피해|신고|어떻게|해야|구제)",
        r"(?:교권|교권\s*침해|교사\s*폭행).*(?:피해|보호|신고|어떻게|해야|문제)",
        r"(?:학교|교육청).*(?:징계|처분|퇴학|정학|이의|부당|어떻게|해야)",
    ],
    # L46: 보험·연금 — 국민연금·건강보험·퇴직연금
    "L46": [
        r"(?:국민\s*연금|국민연금).*(?:수령|신청|미납|체납|반환|감액|분쟁|어떻게|해야|문제)",
        r"(?:건강\s*보험|건강보험|건보).*(?:피부양자|자격|보험료|체납|이의|분쟁|어떻게|해야|문제)",
        r"(?:퇴직\s*연금|퇴직연금|IRP|DB|DC).*(?:수령|해지|중도\s*인출|분쟁|어떻게|해야|문제)",
        r"(?:연금|기금).*(?:수급|자격|감액|지급|정지|분쟁|어떻게|해야|신청|문제)",
    ],
    # L50: 다문화·이주 — 비자·체류·귀화·난민
    "L50": [
        r"(?:비자|사증|체류\s*자격).*(?:신청|연장|변경|거부|취소|어떻게|해야|절차)",
        r"(?:귀화|국적\s*취득|국적취득).*(?:신청|자격|조건|절차|어떻게|해야)",
        r"(?:난민|난민\s*신청|난민신청).*(?:인정|거부|절차|방법|어떻게|해야)",
        r"(?:외국인|이주\s*노동자|이주노동자).*(?:체류|비자|권리|차별|어떻게|해야|문제)",
        r"(?:결혼\s*이민|결혼이민|다문화\s*가정).*(?:체류|자격|이혼|분쟁|어떻게|해야)",
    ],
    # L33: 우주·항공 — 드론·위성·우주개발
    "L33": [
        r"(?:드론|무인\s*항공기|무인기).*(?:규제|허가|신고|비행|금지|어떻게|해야|사고)",
        r"(?:위성|인공\s*위성).*(?:발사|등록|주파수|허가|어떻게|해야|문제)",
        r"(?:우주|항공\s*우주).*(?:개발|사업|손해|배상|책임|규제|어떻게|해야)",
        r"(?:항공|비행).*(?:사고|손해|규제|허가|면허|어떻게|해야|안전)",
    ],
    # L36: 문화재·문화유산 — 보호·현상변경·매장문화재
    "L36": [
        r"(?:문화재|문화\s*유산).*(?:보호|지정|해제|현상\s*변경|훼손|어떻게|해야|신고)",
        r"(?:매장\s*문화재|매장문화재).*(?:발견|발굴|신고|절차|어떻게|해야)",
        r"(?:천연\s*기념물|천연기념물|보물|국보).*(?:지정|해제|손상|보호|어떻게|해야)",
        r"(?:무형\s*문화재|무형문화재).*(?:전승|보유자|지정|인정|어떻게|해야)",
    ],
    # L47: 규제샌드박스·신산업 — 실증특례·규제자유특구
    "L47": [
        r"(?:규제\s*샌드박스|규제샌드박스|실증\s*특례).*(?:신청|승인|적용|기간|어떻게|해야)",
        r"(?:규제\s*자유\s*특구|규제자유특구|특구).*(?:지정|신청|사업|어떻게|해야|혜택)",
        r"(?:신\s*산업|신산업|신기술).*(?:규제|인허가|허용|어떻게|해야|특례)",
        r"(?:산업\s*융합|산업융합).*(?:촉진|규제|특례|신청|어떻게|해야)",
    ],
    # L48: 예술·문화예술 — 예술인복지·공연·전시
    "L48": [
        r"(?:예술인|예술\s*활동|예술인\s*복지).*(?:등록|증명|지원|보험|계약|어떻게|해야)",
        r"(?:공연|전시|축제).*(?:계약|취소|보상|책임|손해|어떻게|해야|분쟁)",
        r"(?:문화\s*예술|문화예술).*(?:지원|보조금|사업|신청|어떻게|해야)",
        r"(?:표준\s*계약서|표준계약서).*(?:예술|작가|어떻게|해야|작성|위반)",
    ],
    # L49: 식품·의약품 안전 — 식품위생·약사·건강기능식품
    "L49": [
        r"(?:식품|음식|식당).*(?:위생|안전|허가|신고|위반|과태료|어떻게|해야|영업)",
        r"(?:의약품|약품|약).*(?:허가|승인|부작용|리콜|불법|어떻게|해야|판매)",
        r"(?:건강\s*기능\s*식품|건강기능식품|건기식).*(?:허가|광고|표시|규제|어떻게|해야)",
        r"(?:HACCP|해썹).*(?:인증|의무|위반|신청|어떻게|해야)",
    ],
    # L51: 종교·신앙 — 종교단체·종교자유·종교재산
    "L51": [
        r"(?:종교\s*단체|종교단체|교회|절|사찰|성당).*(?:분쟁|재산|운영|세금|면세|어떻게|해야)",
        r"(?:종교|신앙).*(?:자유|차별|침해|강요|어떻게|해야|탈퇴)",
        r"(?:헌금|시주|기부).*(?:반환|횡령|문제|분쟁|어떻게|해야)",
        r"(?:목사|승려|신부|종교\s*지도자).*(?:비위|횡령|성범죄|어떻게|해야|문제)",
    ],
    # L53: 농림·축산 — 농지·축산업·농업보조금
    "L53": [
        r"(?:농지|농업|농사).*(?:취득|전용|매매|임대|위반|어떻게|해야|허가)",
        r"(?:축산|축사|가축).*(?:허가|신고|폐수|악취|이전|어떻게|해야|분쟁)",
        r"(?:농업\s*보조금|농업보조금|직불금|직접\s*지불).*(?:신청|반환|부정|수급|어떻게|해야)",
        r"(?:농약|비료|종자).*(?:피해|규제|등록|허가|어떻게|해야|문제)",
    ],
    # L54: 해양·수산 — 어업권·해양환경·선박
    "L54": [
        r"(?:어업|어업권|수산업).*(?:면허|허가|침해|분쟁|보상|어떻게|해야|신고)",
        r"(?:해양|바다).*(?:오염|환경|사고|투기|어떻게|해야|규제|피해)",
        r"(?:선박|어선).*(?:사고|안전|등록|검사|보험|어떻게|해야|문제)",
        r"(?:수산물|양식).*(?:안전|유통|허가|규제|어떻게|해야|피해)",
    ],
    # L55: 과학기술·연구개발 — 국가R&D·기술이전·연구윤리
    "L55": [
        r"(?:연구\s*개발|연구개발|R&D|국가\s*과제).*(?:성과|귀속|기술료|부정|어떻게|해야|관리)",
        r"(?:기술\s*이전|기술이전|기술\s*사업화).*(?:계약|로열티|분쟁|절차|어떻게|해야)",
        r"(?:연구\s*윤리|연구윤리|논문\s*표절).*(?:위반|조사|제재|절차|어떻게|해야)",
        r"(?:직무\s*발명|직무발명).*(?:보상|귀속|출원|분쟁|어떻게|해야|특허)",
    ],
    # L56: 장애인 권리 — 차별금지·편의제공·고용
    "L56": [
        r"(?:장애인|장애).*(?:차별|편의\s*제공|접근성|고용|어떻게|해야|권리|시설)",
        r"(?:장애\s*등급|장애등급|장애\s*정도|장애정도).*(?:판정|심사|이의|재심|어떻게|해야)",
        r"(?:활동\s*지원|활동지원|활동\s*보조).*(?:신청|자격|시간|어떻게|해야|서비스)",
        r"(?:장애인\s*주차|장애인주차|보조\s*기기).*(?:지원|신청|규제|어떻게|해야)",
    ],
    # L58: 스포츠법 — 선수계약·도핑·체육시설
    "L58": [
        r"(?:선수|운동선수).*(?:계약|이적|연봉|폭력|인권|어떻게|해야|분쟁)",
        r"(?:도핑|금지\s*약물).*(?:적발|제재|이의|절차|어떻게|해야)",
        r"(?:체육\s*시설|체육시설|헬스장|수영장).*(?:사고|안전|환불|계약|어떻게|해야)",
        r"(?:스포츠|체육).*(?:중재|분쟁|폭력|비리|어떻게|해야|징계)",
    ],
    # L59: AI·데이터 — 인공지능규제·데이터법·알고리즘
    "L59": [
        r"(?:인공\s*지능|인공지능|AI).*(?:규제|윤리|책임|피해|차별|어떻게|해야|법)",
        r"(?:알고리즘|자동\s*결정|자동화\s*결정).*(?:차별|이의|설명|투명|어떻게|해야)",
        r"(?:데이터|빅\s*데이터).*(?:활용|결합|규제|보호|권리|어떻게|해야|동의)",
        r"(?:자율\s*주행|자율주행).*(?:사고|책임|보험|규제|어떻게|해야|법)",
    ],
    # L60: 법률총괄(CCO) — 복합쟁점·도메인연계
    "L60": [
        r"(?:여러|복합|다수).*(?:법률|법적|법).*(?:문제|쟁점|분쟁|분야|영역|사건)",
        r"(?:여러|복합|다수).*(?:법률\s*문제|법적\s*쟁점|분쟁).*(?:어떻게|해야|상담|연계)",
        r"(?:어떤\s*법률|무슨\s*법|어디).*(?:상담|문의|신고|어떻게|해야|맞는)",
    ],
}

# Pre-compile NLU patterns for performance
_NLU_COMPILED: Dict[str, List[re.Pattern]] = {
    lid: [re.compile(p) for p in patterns]
    for lid, patterns in _NLU_INTENT_PATTERNS.items()
}

# =============================================================
# [NLU] English intent patterns — same structure as Korean
# =============================================================

_NLU_INTENT_PATTERNS_EN: Dict[str, List[str]] = {
    "L22": [
        r"(?:someone|friend|person|man|woman|neighbor|stranger).*(?:hit|beat|punch|assault|threaten|attack|stalk|harass)",
        r"(?:hit|beat|punch|assault|threaten|attack|stalk).*(?:me|him|her|victim|police|report|charge)",
        r"(?:assault|attack|mug|rob).*(?:by|ed\b|victim|street|night|stranger)",
        r"(?:was|been|got)\s+(?:assaulted|attacked|mugged|robbed|beaten|stabbed|threatened)",
        r"(?:stalk|follow|harass|spy).*(?:me|victim|report|how|what)",
        r"(?:\bex\b|ex-boyfriend|ex-girlfriend|ex-husband|ex-wife).*(?:follow|stalk|harass|threaten|call|message|show\s*up|show\s*up|uninvited|won't\s*leave)",
        r"(?:stole|stolen|theft|robbery|burglary|pickpocket).*(?:report|police|how|what|charge)",
        r"(?:broke\s*into|break-in|broken\s*into|burglar|intruder).*(?:house|home|apartment|car|office|store|stole|stolen)",
        r"(?:fraud|scam|phishing|swindle|deceive|cheat).*(?:victim|money|report|how|police)",
        r"(?:hidden\s*camera|spy\s*cam|sexual\s*assault|sexual\s*harassment|molestation|groping|groped)",
        r"(?:lent|loaned)\s*(?:money|cash).*(?:won't\s*pay|wont\s*pay|not\s*pay|refuse|disappear|ghosted|scam)",
        r"(?:prosecute|press\s*charges|criminal\s*complaint|file\s*charges).*(?:how|method|should|want)",
        r"(?:defamation|insult|slander|libel).*(?:victim|sued|how|what)",
        r"(?:drunk\s*driv|DUI|DWI).*(?:caught|arrested|penalty|fine|license)",
        r"(?:blackmail|extort|threaten).*(?:photo|video|private|secret|money|demand|victim|how)",
        r"(?:voice\s*phishing|phishing|vishing).*(?:victim|lost|money|savings|scam|how|report)",
        r"(?:pick\s*(?:my\s*)?pocket|pickpocket|shoplifting).*(?:subway|bus|street|report|how|victim|caught)",
        r"(?:stole|stolen|took).*(?:credit\s*card|wallet|phone|bag|purse|laptop|money|cash)",
        r"(?:roommate|colleague|friend|acquaintance).*(?:stole|stolen|took|theft|fraud|embezzl)",
    ],
    "L08": [
        r"(?:deposit|jeonse|rent|security\s*deposit).*(?:refund|return|not\s*return|won't\s*return|refuse|get\s*back|how|back)",
        r"(?:get|recover|claim).*(?:deposit|security\s*deposit).*(?:back|refund|return|how)?",
        r"(?:landlord|owner|lessor).*(?:refuse|return|repair|evict|not\s*pay|how|contact|kick|force|trying)",
        r"(?:lease|rental|tenancy|jeonse|wolse|rent).*(?:problem|dispute|issue|how|what|expire|renew|break|end|terminat)",
        r"(?:evict|move\s*out|vacate|kick\s*out|kick\s*me\s*out).*(?:force|how|should|refuse|illegal|before)",
        r"(?:contract\s*expir|renew|extend).*(?:lease|rental|refuse|how|what)",
        r"(?:repair|leak|mold|defect).*(?:landlord|owner|refuse|responsib|how|demand|rented|tenant|apartment|flat)",
        r"(?:mold|leak|crack|defect).*(?:rented|rental|my\s*apartment|my\s*flat|tenant)",
        r"(?:break|end|terminat).*(?:lease|rental\s*(?:contract|agreement)).*(?:early|before|how|penalty)",
        r"(?:tenant|renter).*(?:refuse|leave|vacate|move\s*out|expired|won't)",
    ],
    "L30": [
        r"(?:fired|terminated|laid\s*off|dismissed|let\s*go|resign|forced\s*to\s*quit).*(?:unfair|wrongful|how|what|rights|sue|pregnan|discriminat)",
        r"(?:fired|terminated|dismissed|laid\s*off|forced\s*resignation)",
        r"(?:fired|terminated|dismissed).*(?:for|because).*(?:pregnan|sick|union|whistleblow)",
        r"(?:salary|wage|pay|overtime|bonus|back\s*pay).*(?:unpaid|not\s*paid|overdue|owed|how|withh[eo]ld)",
        r"(?:owe|owed|owes).*(?:pay|salary|wage|month|back\s*pay)",
        r"(?:employer|company|boss).*(?:not\s*paid|hasn?.t\s*paid|hasn?.t\s*pay|owes?|withh[eo]ld|unpaid|refuses?\s*to\s*pay)",
        r"(?:work|company|employer).*(?:holiday|weekend|overtime).*(?:no\s*(?:extra|additional)\s*pay|without\s*(?:extra|additional|overtime)\s*pay|unpaid|legal|illegal|how)",
        r"(?:overtime|extra\s*hours|holiday\s*work|weekend\s*work).*(?:pay|unpaid|compensation|how)",
        r"(?:workplace|office|boss|employer|manager|supervisor).*(?:bully|bullies|harass|abuse|hostile|discriminat|how)",
        r"(?:manager|boss|supervisor|coworker).*(?:bully|bullies|harass|abuse|hostile).*(?:me|every|day|office|work)",
        r"(?:severance|retirement\s*pay).*(?:unpaid|not\s*paid|calculat|how|demand|owed)",
        r"(?:wrongful\s*dismissal|unfair\s*termination|constructive\s*dismissal).*(?:how|rights|sue|remedy|claim)",
        r"(?:(?:wrongful|unfair)(?:ly)?\s*(?:fired|terminated|dismissed)).*(?:how|rights|sue|can\s*I)",
        r"(?:employment\s*contract|labor\s*contract|written\s*contract).*(?:missing|no\s*contract|verbal|how|issue|not\s*provide|did\s*not)",
        r"(?:employer|company).*(?:not\s*provide|did\s*not\s*provide|no\s*written).*(?:contract|employment)",
        r"(?:forced\s*to\s*resign|forced\s*resignation).*(?:report|whistleblow|safety|how|rights|unfair)",
        r"(?:resign|quit).*(?:forced|pressur|coerce).*(?:report|whistleblow|safety|how)",
    ],
    "L41": [
        r"(?:husband|wife|spouse|partner|boyfriend|girlfriend).*(?:hit|beat|assault|violence|affair|cheat|infidelity|abuse|hide|hiding)",
        r"(?:divorce|separate|split\s*up|break\s*up).*(?:want|how|procedure|process|condition|file|apply|rights)",
        r"(?:file|apply|want).*(?:divorce|separation|split\s*up)",
        r"(?:custody|child\s*support|visitation|parental\s*rights|children).*(?:how|rights|claim|demand|refuse|fight|modify|get|want)",
        r"(?:get|want|fight\s*for|claim).*(?:custody|child\s*support|visitation|parental\s*rights)",
        r"(?:property\s*division|alimony|settlement|division\s*of\s*assets|marital\s*property).*(?:how|amount|claim|demand|calculate|entitle|divide|split)",
        r"(?:divide|split).*(?:marital\s*property|property|assets).*(?:divorce|how)",
        r"(?:domestic\s*violence|DV|family\s*violence|abusive).*(?:how|report|protect|restrain|shelter|help|order)",
        r"(?:foreign|international|overseas)\s*(?:spouse|marriage|divorce).*(?:how|rights|procedure|custody|jurisdiction)",
    ],
    "L57": [
        r"(?:parent|father|mother|grandparent|sibling|spouse).*(?:passed\s*away|died|death|deceased|inherit|estate|property|left)",
        r"(?:inherit|estate|will|bequest|legacy).*(?:divide|share|renounce|waive|debt|how|tax|rights|portion|claim)",
        r"(?:debt|liability).*(?:inherit|pass\s*on).*(?:how|renounce|waive|reject|limit)",
        r"(?:inheritance\s*tax|estate\s*tax).*(?:how|calculate|pay|reduce|exempt|file)",
    ],
    "L38": [
        r"(?:refund|return|exchange).*(?:refuse|denied|can't|won't|how|demand|policy)",
        r"(?:defective|faulty|broken|damaged).*(?:product|item|goods|appliance).*(?:how|exchange|refund|claim)",
        r"(?:product|item|goods|order|package).*(?:broken|damaged|defective|faulty|wrong|missing|arrived)",
        r"(?:cancel|terminate|withdraw).*(?:subscription|membership|gym|service).*(?:refuse|penalty|how|charge|fee|can't|won't)",
        r"(?:subscription|membership|gym).*(?:cancel|terminate|refund|penalty|charge|how|can't|won't)",
        r"(?:purchase|payment|order|bought|ordered).*(?:cancel|fraud|scam|defective|refund|how|broken|damaged|arrived)",
        r"(?:used\s*car|second\s*hand|pre-owned).*(?:defect|lemon|flood|damage|fraud|misrepresent|refund|how)",
        r"(?:warranty|guarantee).*(?:refuse|expired|void|how|claim|repair)",
        r"(?:online\s*store|seller|shop|retailer).*(?:refuse|refund|exchange|return|defective|how|won't)",
    ],
    "L07": [
        r"(?:car|vehicle|motorcycle|bicycle|scooter|bus|truck).*(?:accident|crash|collision|hit|struck|rear-end)",
        r"(?:traffic\s*accident|car\s*accident|auto\s*accident|fender\s*bender)",
        r"(?:rear-end|rear\s*end|t-bon|sideswip|hit-and-run|fender\s*bender)",
        r"(?:hit|struck|crash|collid).*(?:my\s*(?:car|vehicle|parked)|parked\s*car)",
        r"(?:driver|accident).*(?:fault|deny|negligence|liability|hit-and-run|fled|ran\s*away|drove\s*away)",
        r"(?:insurance\s*claim|fault\s*ratio|liability|negligence).*(?:how|dispute|calculate|process)",
        r"(?:traffic|car|auto)\s*(?:accident|crash).*(?:insurance|claim|settlement|compensation|how)",
        r"(?:drunk\s*driver|drunk\s*driving|DUI|DWI).*(?:hit|crash|accident|collid|struck|motorcycle|car|vehicle)",
    ],
    "L05": [
        r"(?:hospital|doctor|surgeon|surgery|treatment|procedure|physician).*(?:mistake|error|negligence|malpractice|harm|side\s*effect|complication|wrong|botch)",
        r"(?:operat|surgery|surgeon).*(?:wrong|mistake|error|botch|fail|side|left|forgot)",
        r"(?:medical\s*malpractice|medical\s*negligence|misdiagnosis|surgical\s*error|medical\s*accident)",
        r"(?:cosmetic|plastic\s*surgery|procedure|medication).*(?:botch|fail|side\s*effect|wrong|defect)",
        r"(?:complication|secondary\s*surgery|after-effect).*(?:occur|happen|develop|how|liable|compensat)",
    ],
    "L11": [
        r"(?:debt|loan|interest|creditor).*(?:can't\s*pay|cannot\s*pay|overwhelm|restructur|bankrupt|how|harass|call|collect)",
        r"(?:debt\s*collector|collection\s*agency|collector).*(?:call|harass|threaten|constant|how|stop|illegal|night|3am|every)",
        r"(?:collect|collector|collection|calls|demand).*(?:constant|harass|every\s*day|how|stop|illegal)",
        r"(?:personal\s*(?:recovery|rehabilitation)|individual\s*bankruptcy|debt\s*restructuring|credit\s*recovery)",
        r"(?:discharge|bankrupt|insolvency).*(?:decision|petition|apply|file|qualify|debt|how)",
        r"(?:owe|owed|owes)\s*(?:money|debt).*(?:creditor|multiple|several|many|can't\s*pay|cannot\s*pay|how)",
        r"(?:multiple|several|many)\s*(?:debt|loan|creditor).*(?:can't\s*pay|cannot\s*pay|overwhelm|how|bankrupt)",
    ],
    "L01": [
        r"(?:contract|agreement).*(?:breach|violat|cancel|terminat|void|dispute|how|sue|claim|not\s*fulfil|not\s*honor|broken)",
        r"(?:sue|lawsuit|file|claim).*(?:breach|violat).*(?:contract|agreement)",
        r"(?:signed|entered).*(?:contract|agreement).*(?:not\s*fulfil|breach|violat|refuse|broken|how)",
        r"(?:contract|agreement).*(?:damages|compensation|lawsuit|litigation|sue)",
        r"(?:money|loan|debt|lent|borrowed|owed).*(?:return|recover|repay|collect|sue|claim|how|statute)",
        r"(?:demand\s*letter|payment\s*order|lawsuit|civil\s*suit|small\s*claims).*(?:send|file|how|procedure)",
        r"(?:provisional\s*seizure|preliminary\s*injunction|garnish).*(?:apply|file|how|procedure)",
    ],
    "L06": [
        r"(?:damage|harm|injur|broken|destroy).*(?:compensat|liable|pay|how|sue|amount)",
        r"(?:compensat|damages|settlement).*(?:demand|claim|how|amount|calculate|emotional|distress)",
        r"(?:get|claim|receive|seek).*(?:compensat|damages|settlement)",
        r"(?:emotional\s*distress|mental\s*suffering|pain\s*and\s*suffering).*(?:claim|sue|how|amount)",
        r"(?:sue|claim|seek).*(?:emotional\s*distress|mental\s*suffering|pain\s*and\s*suffering|damages).*(?:neighbor|noise|nuisance|how)?",
        r"(?:sue|claim).*(?:neighbor|landlord|company|person).*(?:emotional\s*distress|damages|compensat|liable)",
        r"(?:tort|negligence|wrongful\s*act).*(?:damage|liable|compensat|how|sue)",
    ],
    "L10": [
        r"(?:seiz|garnish|attach|levy).*(?:account|salary|property|how|release|challenge)",
        r"(?:bank\s*account|salary|wage).*(?:frozen|seized|garnished|attached|blocked|how)",
        r"(?:civil\s*enforcement|compulsory\s*execution|forced\s*execution).*(?:how|procedure|apply|file)",
    ],
    "L34": [
        r"(?:personal\s*(?:data|information)|my\s*(?:data|information)).*(?:leak|breach|stolen|misuse|how|protect|collect|without\s*consent)",
        r"(?:CCTV|surveillance|wiretap|spy).*(?:illegal|privacy|invasion|how|report|install|camera|point|record)",
        r"(?:install|set\s*up|place).*(?:CCTV|camera|surveillance).*(?:house|home|property|room|privacy)",
        r"(?:collect|gather|store|use).*(?:personal\s*(?:data|information)).*(?:without\s*(?:consent|permission)|illegal|how|report)",
        r"(?:data\s*(?:leak|breach|stolen)).*(?:company|personal|customer|how|report)",
    ],
    "L02": [
        r"(?:registration|title|ownership).*(?:transfer|change|issue|how|dispute|property)",
        r"(?:apartment|condo|land|building|property).*(?:fraud|defect|dispute|purchase|buy|sell|how|lied|misrepresent|condition)",
        r"(?:seller|sold|bought|purchase).*(?:apartment|condo|land|building|property|house|real\s*estate).*(?:lied|defect|fraud|condition|misrepresent|how|dispute)",
        r"(?:seller|sold|bought|purchase).*(?:lied|defect|fraud|misrepresent|condition).*(?:apartment|condo|land|building|property|house)",
        r"(?:real\s*estate|property|land|apartment).*(?:transaction|contract|purchase|sale|how|dispute|title|cancel|fraud)",
        r"(?:cancel|void|rescind).*(?:real\s*estate|property|land).*(?:contract|deal|transaction|fraud|how)",
    ],
    "L20": [
        r"(?:tax|income\s*tax|capital\s*gains|gift\s*tax|inheritance\s*tax|property\s*tax).*(?:how\s*much|file|pay|how|owe|delinquent|overdue|return|report)",
        r"(?:how\s*much|calculate|owe).*(?:tax|capital\s*gains\s*tax|income\s*tax|gift\s*tax|inheritance\s*tax)",
        r"(?:gift\s*tax|inheritance\s*tax).*(?:parents?|give|receive|money|how|pay|need)",
        r"(?:pay|need\s*to\s*pay|do\s*I\s*(?:need|have)\s*to\s*pay).*(?:gift\s*tax|inheritance\s*tax|capital\s*gains\s*tax|income\s*tax)",
        r"(?:file|submit).*(?:tax\s*return|income\s*tax|tax\s*report)",
    ],
    "L52": [
        r"(?:internet|social\s*media|online|post|comment|youtube|blog|SNS).*(?:defamation|slander|insult|delete|harm|false|fake|review|reputation|impersonat)",
        r"(?:false\s*information|fake\s*news|rumor).*(?:spread|post|report|sue|how)",
        r"(?:spread|post|writ).*(?:false|fake|rumor|lie|defam).*(?:online|social\s*media|internet|SNS|blog|youtube)",
        r"(?:malicious|fake|false|defamatory)\s*(?:review|comment|post|article).*(?:online|business|reputation|how|delete|report)",
        r"(?:fake\s*(?:account|profile)|impersonat).*(?:social\s*media|online|internet|report|how)",
    ],
    "L37": [
        r"(?:school\s*(?:violence|bully)|bullying|hazing|ostraciz).*(?:victim|report|how|punish|committee|what)",
        r"(?:minor|juvenile|teenager|youth|child).*(?:crime|incident|victim|perpetrat|how|assault|beat|bully|bullied|harass)",
        r"(?:school|class|student|classmate).*(?:beat|hit|assault|bully|harass|ostraciz|how)",
        r"(?:son|daughter|child|kid).*(?:bully|bullied|harass|beat|hit|assault|ostraciz).*(?:school|class|student|classmate|how)?",
        r"(?:bully|bullied|harass|beat).*(?:at\s*school|by\s*(?:classmate|student|peer))",
    ],
    "L43": [
        r"(?:workplace\s*(?:accident|injury)|industrial\s*accident|work\s*(?:accident|injury)|on-the-job\s*injury)",
        r"(?:injur|hurt|accident).*(?:at\s*work|workplace|factory|construction\s*site|on\s*the\s*job)",
        r"(?:workers?\s*comp|industrial\s*accident|occupational\s*(?:injury|disease|accident))",
        r"(?:factory|site|workshop|workplace).*(?:accident|injur|burn|fall|how|compensat)",
        r"(?:workplace|office|job).*(?:bully|harass|stress|overwork).*(?:workers?\s*comp|industrial\s*accident|depression|illness|death)",
        r"(?:burn|fell|fall|crush|electr).*(?:while\s*working|at\s*(?:work|factory|site|plant)|on\s*the\s*job|during\s*work)",
        r"(?:worker|employee|colleague).*(?:fell|fall|died|killed|injur|burn|crush).*(?:work|factory|site|scaffold|construction|machine)",
        r"(?:died|death|killed).*(?:overwork|karoshi|work|factory|construction|on\s*the\s*job)",
    ],
    "L25": [
        r"(?:military|army|soldier|service|enlist|discharge|duty).*(?:assault|violence|accident|bully|hazing|issue|unfair|how|draft|exempt|defer)",
        r"(?:military\s*violence|military\s*accident|hazing|military\s*assault)",
    ],
    "L31": [
        r"(?:fine|penalty|administrative\s*(?:action|sanction)|license\s*(?:suspension|revocation)|permit).*(?:appeal|challenge|unfair|dispute|cancel|how)",
        r"(?:government|state|authorit|municipal).*(?:seiz|expropri|condemn|confiscat|revok|cancel|fine|penalt).*(?:property|land|license|permit|compensation|how|unfair|without)",
        r"(?:seiz|expropri|condemn|confiscat).*(?:property|land|building).*(?:government|state|without\s*(?:proper|fair|adequate)?\s*compensation|unfair|how)",
        r"(?:administrative\s*(?:litigation|lawsuit|appeal|tribunal)).*(?:procedure|file|how|deadline)",
        r"(?:eminent\s*domain|expropriat|compulsory\s*acquisition).*(?:compensation|unfair|how|challenge|taking|appeal)",
        r"(?:challenge|appeal|fight|contest).*(?:eminent\s*domain|expropriat|government\s*(?:seiz|tak)|compulsory\s*acquisition)",
        r"(?:government|state|city|municipal).*(?:revok|cancel|suspend).*(?:license|permit|business).*(?:without|unfair|notice|how)?",
    ],
    "L42": [
        r"(?:photo|image|article|video|music|song|work|content|design|photograph).*(?:without\s*(?:permission|consent|credit)|unauthorized|stolen|copied|plagiariz|pirate)",
        r"(?:stole|stolen|took|used|copied|uploaded).*(?:photo|image|video|music|song|work|content|article|design|photograph).*(?:post|upload|online|website|without|YouTube)?",
        r"(?:copyright|intellectual\s*property|DMCA|plagiarism).*(?:infring|violat|stolen|report|how|claim)",
        r"(?:upload|post|use|copy).*(?:my\s*(?:photo|image|video|music|song|work|content|design|photograph)).*(?:without|YouTube|online|website|permission|consent)?",
        r"(?:someone|they|website|company).*(?:using|copied|stole|took|upload).*(?:my\s*(?:photo|image|video|music|song|work|design|photograph))",
    ],
    "L04": [
        r"(?:redevelopment|reconstruction|urban\s*renewal).*(?:association|contribution|relocation|compensat|how|dispute)",
        r"(?:association\s*member|occupancy\s*right).*(?:purchase|sell|dispute|how)",
    ],
    "L14": [
        r"(?:director|officer|CEO|board).*(?:breach|embezzl|fiduciary|dismiss|appoint|liab)",
        r"(?:shareholder|minority\s*shareholder).*(?:derivative\s*suit|rights|meeting|vote|dividend|how)",
        r"(?:file|bring|initiate).*(?:derivative\s*suit|shareholder\s*action|shareholder\s*lawsuit)",
        r"(?:merger|acquisition|M&A|split|takeover).*(?:procedure|oppose|appraisal|how)",
        r"(?:corporation|company).*(?:establish|dissolve|liquidat|board|articles|how)",
        r"(?:business\s*partner|co-founder|partner).*(?:embezzl|steal|misappropriat|fraud|fund|money)",
    ],
    "L16": [
        r"(?:insurance\s*(?:claim|payment|benefit|payout)).*(?:denied|refused|reject|reduced|how|dispute)",
        r"(?:insurer|insurance\s*company).*(?:denied|refused|reject|dispute|how|reduced|payout)",
        r"(?:insurance\s*(?:fraud|claim)).*(?:suspect|investigat|how)",
        r"(?:policy|coverage|exclusion|insurance\s*contract).*(?:unfair|dispute|how|interpret)",
        r"(?:insurance).*(?:denied|refused|reject|reduced|won't\s*pay|dispute|claim)",
        r"(?:insurance\s*company).*(?:denied|refused|reject|reduced).*(?:claim|my|accident|how)",
        r"(?:denied|refused|reject).*(?:insurance|(?:my|the)\s*claim).*(?:accident|how|what)?",
        r"(?:insurance\s*company|insurer).*(?:denied|refused|reject|reduced|won't\s*pay).*(?:my|the|car|accident|claim|how)",
    ],
    "L26": [
        r"(?:patent|utility\s*model).*(?:infring|register|file|reject|how|dispute|sue)",
        r"(?:trademark|brand|trade\s*name|logo).*(?:infring|stolen|register|similar|how|dispute|sue|copy|counterfeit)",
        r"(?:register|file|apply).*(?:patent|trademark|trade\s*name|utility\s*model)",
        r"(?:trade\s*secret|proprietary|confidential).*(?:leak|stolen|misappropriat|protect|how)",
        r"(?:use|copy|modif|imitat).*(?:patent|trademark|design|invention).*(?:infring|legal|how|permission|without)",
        r"(?:use|copy|modif|imitat).*(?:someone|other|their|else).*(?:patent|trademark|design|invention)",
        r"(?:competitor|someone|company).*(?:selling|using|copying).*(?:logo|trademark|brand|design).*(?:similar|same|copy|how)?",
        r"(?:using|selling|copy).*(?:my\s*(?:patent|trademark|logo|brand|design|invention)).*(?:without|infring|how)?",
    ],
    "L15": [
        r"(?:partnership|joint\s*venture|co-found|start\s*together).*(?:contract|agreement|company|register|how|caution)",
        r"(?:cafe|restaurant|shop|store|franchise|food\s*truck|bakery|bar).*(?:start|open|establish|run|operate|how|license|register)",
        r"(?:open|start|run|register).*(?:cafe|restaurant|shop|store|franchise|food\s*truck|bakery|bar|business).*(?:friend|partner|together|how|Seoul|Korea)?",
        r"(?:investment|equity|share|capital\s*contribution).*(?:split|divide|how|agreement|contract)",
        r"(?:start\s*a?\s*business|start-?up|entrepreneur|found\s*a?\s*company).*(?:how|register|procedure|foreign|visa|requirement)",
        r"(?:register|set\s*up|establish).*(?:small\s*business|sole\s*proprietor|company|LLC|corporation).*(?:Korea|Seoul|how|procedure)?",
    ],
    "L03": [
        r"(?:building\s*permit|construction\s*permit).*(?:procedure|denied|how|apply)",
        r"(?:building|apartment|house).*(?:defect|leak|crack|poor\s*construction).*(?:liable|claim|how|repair)",
        r"(?:construction\s*(?:payment|cost)|progress\s*payment).*(?:unpaid|owed|overdue|how|claim)",
        r"(?:contractor|builder|construction\s*company).*(?:defect|abandon|bankrupt|how|dispute)",
    ],
    "L09": [
        r"(?:bid|tender|procurement).*(?:qualif|cancel|protest|collusion|rigg|how|dispute)",
        r"(?:government\s*contract|public\s*procurement).*(?:dispute|challenge|cancel|how|procedure)",
    ],
    "L12": [
        r"(?:auction|foreclosure|public\s*sale).*(?:bid|participate|distribute|vacate|procedure|how)",
        r"(?:participate|bid|join).*(?:auction|foreclosure|public\s*sale)",
        r"(?:registry|title\s*deed|registration).*(?:inspect|change|cancel|transfer|how|procedure)",
    ],
    "L13": [
        r"(?:promissory\s*note|check|bill\s*of\s*exchange).*(?:dishonor|forge|endorse|collect|how)",
        r"(?:commercial|trade|mercantile).*(?:dispute|litigation|how|procedure)",
    ],
    "L17": [
        r"(?:international\s*(?:contract|transaction|trade)|cross-border|overseas\s*(?:deal|transaction)).*(?:dispute|governing\s*law|arbitration|how)",
        r"(?:international|cross-border|overseas|foreign).*(?:trade|contract|transaction).*(?:dispute|arbitration|law|how)",
        r"(?:joint\s*venture|partnership|contract|business).*(?:foreign\s*company|overseas\s*company|international|cross-border)",
        r"(?:set\s*up|establish|form).*(?:joint\s*venture|partnership).*(?:foreign|international|overseas|cross-border)",
        r"(?:governing\s*law|international\s*arbitration|ICC|UNCITRAL).*(?:choose|apply|procedure|how)",
    ],
    "L18": [
        r"(?:power\s*plant|solar|wind|nuclear).*(?:permit|license|construct|operate|dispute|accident|how)",
        r"(?:energy\s*(?:business|project)|renewable\s*energy|electricity\s*business).*(?:permit|regulat|dispute|subsidy|how)",
    ],
    "L19": [
        r"(?:ship|vessel|cargo\s*ship|tanker|freighter).*(?:accident|collision|sink|ground|insurance|dispute|how)",
        r"(?:collision|accident|sink|ground).*(?:at\s*sea|ship|vessel|maritime|ocean|port)",
        r"(?:maritime\s*(?:transport|shipping)|charter).*(?:contract|dispute|claim|damage|how)",
        r"(?:flight|airline|aviation).*(?:delay|cancel|accident|compensat|dispute|how)",
    ],
    "L21": [
        r"(?:hack|hacker|ransomware|DDoS|cyber\s*attack).*(?:victim|damage|attack|report|how|respond)",
        r"(?:hacked|breached|compromised).*(?:data|account|system|company|server|customer|stolen)",
        r"(?:cyber\s*crime|internet\s*crime).*(?:report|victim|penalty|how)",
        r"(?:data\s*(?:breach|security)|information\s*security|security\s*incident).*(?:obligation|violation|regulat|how)",
    ],
    "L23": [
        r"(?:exclusive\s*contract|talent\s*(?:contract|agreement)|management\s*(?:contract|agreement)).*(?:terminat|breach|unfair|dispute|how)",
        r"(?:management|agency|entertainment).*(?:contract|dispute|conflict|terminat|unfair|how)",
        r"(?:celebrity|idol|actor|singer|artist).*(?:contract|exclusive|penalty|dispute|how)",
    ],
    "L24": [
        r"(?:tax\s*(?:audit|investigation|examination)).*(?:respond|prepare|notice|how)",
        r"(?:tax\s*(?:assessment|levy|imposition|penalty)).*(?:appeal|challenge|cancel|how|unfair|dispute)",
        r"(?:challenge|appeal|dispute).*(?:tax\s*(?:penalty|assessment|levy|fine|imposition))",
        r"(?:tax\s*(?:tribunal|appeal|review)).*(?:file|procedure|how|deadline)",
    ],
    "L27": [
        r"(?:pollution|contamination|air\s*quality|water\s*quality|soil).*(?:damage|compensat|report|how)",
        r"(?:pollut|contaminat|dump|discharg).*(?:water|air|soil|river|lake|sea|environment|supply|ground)",
        r"(?:factory|plant|company).*(?:pollut|contaminat|discharg|dump|emission|waste)",
        r"(?:noise|vibration|odor|smell).*(?:damage|complaint|standard|how|dispute|neighbor|excessive|every|night|constant)",
        r"(?:neighbor|neighbour|upstairs|downstairs).*(?:noise|loud|bang|stomp|music|party|every\s*night|constant)",
        r"(?:waste|garbage|sewage|hazardous).*(?:illegal|dump|disposal|report|how)",
    ],
    "L28": [
        r"(?:import|export|customs\s*clearance|customs).*(?:delay|refuse|problem|dispute|how|procedure|help|clearance)",
        r"(?:customs\s*clearance|clear\s*customs).*(?:import|export|goods|product|how|help|procedure)",
        r"(?:tariff|customs\s*duty|duty\s*rate).*(?:assess|appeal|refund|how|exemption)",
        r"(?:FTA|certificate\s*of\s*origin|rules\s*of\s*origin).*(?:issue|apply|benefit|how)",
    ],
    "L29": [
        r"(?:game\s*item|in-game|virtual\s*item).*(?:scam|fraud|refund|dispute|how)",
        r"(?:game|gaming).*(?:refund|scam|fraud|regulat).*(?:how|report|claim)",
        r"(?:scam|fraud|cheat).*(?:game|gaming|game\s*item|in-game|virtual)",
        r"(?:digital\s*content|online\s*content).*(?:dispute|refund|cancel|contract|how)",
    ],
    "L32": [
        r"(?:monopoly|market\s*dominan).*(?:abuse|regulat|report|how)",
        r"(?:cartel|collusion|bid\s*rigging|price\s*fixing)",
        r"(?:unfair\s*(?:trade|business)|anti-competitive).*(?:report|victim|regulat|how)",
        r"(?:franchise|franchis).*(?:dispute|unfair|terminat|penalty|how|victim)",
    ],
    "L35": [
        r"(?:fundamental\s*rights|basic\s*rights|constitutional\s*rights).*(?:violat|restrict|protect|how|remedy)",
        r"(?:unconstitutional|constitutional\s*(?:review|challenge|petition|complaint))",
        r"(?:file|submit).*(?:constitutional\s*(?:complaint|petition|challenge|review))",
        r"(?:protest|demonstration|rally|freedom\s*of\s*(?:speech|expression|assembly)).*(?:restrict|ban|violat|permit|how)",
    ],
    "L39": [
        r"(?:telecom|phone|internet\s*service|ISP|carrier).*(?:dispute|cancel|penalty|overcharg|how)",
        r"(?:broadcast|TV).*(?:regulat|violation|sanction|appeal|dispute|how)",
    ],
    "L40": [
        r"(?:discriminat|racial|gender|disability|age|employment).*(?:discriminat|victim|report|remedy|how)",
        r"(?:human\s*rights?\s*violation).*(?:victim|report|remedy|how|complaint)",
        r"(?:report|file|complain).*(?:human\s*rights?\s*violation|discrimination|inequality)",
        r"(?:hate\s*speech|hate\s*expression).*(?:report|penalty|regulat|how|victim)",
    ],
    "L44": [
        r"(?:basic\s*living|welfare\s*benefit|livelihood\s*benefit).*(?:apply|denied|qualif|how|eligib)",
        r"(?:apply|receive|get|qualif).*(?:basic\s*living|welfare\s*benefit|livelihood|public\s*assistance)",
        r"(?:eligib|qualif).*(?:basic\s*living|welfare\s*benefit|livelihood|public\s*assistance)",
        r"(?:emergency\s*(?:aid|assistance|relief|welfare)).*(?:apply|qualif|how|procedure)",
        r"(?:social\s*(?:welfare|security|service)).*(?:apply|denied|eligib|how)",
        r"(?:nursing\s*home|nursing\s*care|care\s*facility|elderly\s*care|senior\s*center).*(?:neglect|abuse|mistreat|how|report|complaint)",
        r"(?:report|complain).*(?:abuse|neglect|mistreat).*(?:nursing|care\s*facility|elderly|senior)",
        r"(?:single\s*(?:mother|parent|father)).*(?:benefit|welfare|assistance|support|eligib|qualif|how)",
    ],
    "L45": [
        r"(?:academy|cram\s*school|tuition|tutoring).*(?:refund|cancel|dispute|how|penalty)",
        r"(?:education|school|admission).*(?:discriminat|victim|report|how|remedy)",
        r"(?:school|board\s*of\s*education).*(?:disciplin|expel|suspend|appeal|unfair|how)",
        r"(?:student|pupil).*(?:expel|suspend|disciplin|punish|unfair).*(?:school|how|appeal)?",
        r"(?:expel|suspend|disciplin).*(?:student|pupil|school|unfair|appeal|how)",
    ],
    "L46": [
        r"(?:national\s*pension|pension).*(?:receive|apply|unpaid|overdue|how|reduce|amount|early)",
        r"(?:receive|collect|withdraw|get).*(?:national\s*pension|pension|retirement\s*fund).*(?:early|how)?",
        r"(?:health\s*insurance|national\s*health).*(?:dependent|eligib|premium|overdue|how|dispute|too\s*high|reduce|expensive)",
        r"(?:health\s*insurance\s*premium).*(?:high|expensive|reduce|dispute|how|too)",
        r"(?:retirement\s*(?:pension|fund)|IRP).*(?:receive|withdraw|early|dispute|how)",
    ],
    "L50": [
        r"(?:visa|residence\s*(?:permit|status)|work\s*permit).*(?:apply|extend|change|denied|cancel|revoke|how|procedure|transfer|switch)",
        r"(?:change|switch|convert|transfer).*(?:visa|visa\s*status|residence\s*status|work\s*permit)",
        r"(?:naturaliz|citizenship|nationality).*(?:apply|qualif|condition|procedure|how)",
        r"(?:refugee|asylum).*(?:apply|recognized|denied|procedure|how|claim|status)",
        r"(?:apply|file|request).*(?:refugee|asylum).*(?:status|how|procedure|Korea)?",
        r"(?:foreign(?:er)?|immigrant|migrant\s*worker).*(?:visa|residence|rights|discriminat|how|issue)",
        r"(?:marriage\s*(?:immigration|visa|immigrant)|multicultural\s*family).*(?:residence|status|divorce|dispute|how)",
        r"(?:E-2|F-2|F-4|F-5|F-6|D-10|H-1|H-2).*(?:visa|status|extend|change|transfer|how)",
    ],
    "L33": [
        r"(?:drone|UAV|unmanned).*(?:regulat|permit|register|flight|restrict|how|accident|crash|damage|injur|collid|fly|operat)",
        r"(?:fly|operat|use).*(?:drone|UAV|unmanned).*(?:permit|license|regulat|how|commercial|restrict)?",
        r"(?:satellite|spacecraft).*(?:launch|register|frequency|permit|how)",
        r"(?:space|aerospace).*(?:develop|business|damage|liability|regulat|how)",
    ],
    "L36": [
        r"(?:cultural\s*(?:heritage|property|asset)).*(?:protect|designat|alter|damage|how|report|demolit|destroy|preserv)",
        r"(?:protect|preserv|save).*(?:cultural\s*(?:heritage|property|asset|site)|historic|monument)",
        r"(?:buried\s*cultural\s*(?:property|asset)).*(?:discover|excavat|report|how|procedure)",
    ],
    "L47": [
        r"(?:regulatory\s*sandbox|pilot\s*program|special\s*(?:zone|exemption)).*(?:apply|approv|how|procedure|get|exemption)",
        r"(?:regulatory\s*sandbox)",
        r"(?:new\s*(?:industry|technology)|innovat|fintech).*(?:regulat|permit|exemption|how|special|sandbox)",
    ],
    "L48": [
        r"(?:artist|art\s*worker|arts?\s*welfare).*(?:register|certif|support|insurance|contract|how|not\s*paid|unpaid|payment|benefit|welfare)",
        r"(?:register|certif|apply).*(?:as\s*(?:an?\s*)?artist|art\s*worker|arts?\s*welfare).*(?:benefit|welfare|how|support)?",
        r"(?:performance|exhibition|festival).*(?:contract|cancel|compensat|liable|how|dispute|paid|payment|unpaid|organiz|not\s*paid)",
        r"(?:artist|performer|musician).*(?:not\s*paid|unpaid|owed|payment).*(?:performance|festival|exhibition|concert|event)?",
        r"(?:festival|concert|event)\s*(?:organiz|promot).*(?:not\s*paid|unpaid|owed|refuse|payment|artist|performer)",
    ],
    "L49": [
        r"(?:food|restaurant|dining).*(?:hygiene|safety|permit|violation|fine|how|license)",
        r"(?:drug|medicine|pharmaceutical).*(?:approv|side\s*effect|recall|illegal|how|sale)",
    ],
    "L51": [
        r"(?:religious\s*(?:organization|institution)|church|temple|mosque).*(?:dispute|property|tax|exempt|how)",
        r"(?:religion|faith|belief).*(?:freedom|discriminat|violat|force|how)",
    ],
    "L53": [
        r"(?:farmland|agricultural|farming).*(?:acquir|convert|sale|lease|violation|how|permit)",
        r"(?:livestock|cattle|farm\s*animal).*(?:permit|report|waste|odor|relocation|how|dispute)",
    ],
    "L54": [
        r"(?:fishing|fishery).*(?:license|permit|infring|dispute|compensat|how|rights|violat|vessel)",
        r"(?:fishing\s*(?:vessel|boat|ship|rights))",
        r"(?:ocean|marine|sea).*(?:pollution|environment|accident|dump|how|regulat)",
    ],
    "L55": [
        r"(?:R&D|research|national\s*project).*(?:result|ownership|royalty|fraud|how|manage)",
        r"(?:technology\s*transfer|commercializ).*(?:contract|royalty|dispute|how|procedure)",
        r"(?:research\s*(?:ethics|misconduct)|plagiarism).*(?:violation|investigat|sanction|how)",
    ],
    "L56": [
        r"(?:disab(?:led|ility)).*(?:discriminat|accommodat|accessib|employment|how|rights|facilit)",
        r"(?:wheelchair|ramp|accessible|blind|deaf|handicap).*(?:missing|no\s|lack|discriminat|how|rights|access|require)",
        r"(?:disability\s*(?:rating|assessment|grade)).*(?:review|appeal|reassess|how)",
        r"(?:appeal|challenge|review).*(?:disability\s*(?:rating|assessment|grade))",
    ],
    "L58": [
        r"(?:athlete|player|sports\s*(?:person|professional)).*(?:contract|transfer|salary|violence|how|dispute|doping|caught)",
        r"(?:doping|banned\s*substance|prohibited\s*substance).*(?:caught|sanction|appeal|how|test|positive)",
        r"(?:caught|tested\s*positive|accused).*(?:doping|banned\s*substance|prohibited\s*substance)",
        r"(?:gym|sports\s*facility|pool|fitness\s*center|fitness).*(?:accident|safety|refund|contract|how|injur|faulty|equipment|fell|slip)",
        r"(?:injur|hurt|accident).*(?:gym|sports\s*facility|pool|fitness|training|exercise)",
    ],
    "L59": [
        r"(?:artificial\s*intelligence|AI|machine\s*learning).*(?:regulat|ethic|liable|harm|discriminat|how|law)",
        r"(?:algorithm|automated\s*decision).*(?:discriminat|appeal|explain|transparen|how)",
        r"(?:data|big\s*data).*(?:use|combine|regulat|protect|rights|how|consent)",
        r"(?:autonomous\s*(?:vehicle|driving)|self-driving).*(?:accident|liable|insurance|regulat|how)",
        r"(?:self-driving|autonomous|unmanned|driverless)\s*(?:car|vehicle|bus|truck)",
    ],
    "L60": [
        r"(?:multiple|complex|several).*(?:legal|law).*(?:issue|problem|dispute|area|matter)",
        r"(?:which\s*law|what\s*law|where).*(?:consult|ask|report|how|apply|go)",
    ],
}

_NLU_COMPILED_EN: Dict[str, List[re.Pattern]] = {
    lid: [re.compile(p, re.IGNORECASE) for p in patterns]
    for lid, patterns in _NLU_INTENT_PATTERNS_EN.items()
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
    "L04": 1,   # 재개발 (재건축/정비사업 문맥 — L02/L03보다 우선)
    "L05": 1,   # 의료법 (의료 맥락 손해배상은 L06보다 우선)
    "L07": 2,   # 교통사고
    "L14": 2,   # 회사법 (이사/주주 문맥 — L01보다 우선)
    "L16": 2,   # 보험 (보험금/약관 문맥 — L06보다 우선)
    "L26": 2,   # 지식재산권 (특허/상표 문맥)
    "L38": 2,   # 소비자법
    "L43": 1,   # 산업재해 (산재 문맥 — L30보다 우선, 직장 괴롭힘+산재 → L43)
    "L37": 1,   # 학교폭력 (학교/미성년자/학폭 문맥 — L22보다 우선)
    "L42": 1,   # 저작권 (블로그/사진 문맥 — L52 광고·언론보다 우선)
    "L15": 2,   # 스타트업/창업 (동업/카페 문맥 — L14 회사법보다 우선)
    "L03": 2,   # 건설법 (건축/공사 문맥 — L01 민사보다 우선)
    "L09": 2,   # 국가계약 (입찰/조달 문맥)
    "L12": 2,   # 등기·경매 (경매/등기 문맥 — L10 민사집행과 구분)
    "L13": 2,   # 상사법 (어음/수표/상거래 문맥)
    "L17": 2,   # 국제거래 (국제계약/중재 문맥)
    "L18": 2,   # 에너지·자원 (발전소/에너지 문맥)
    "L19": 2,   # 해상·항공 (선박/항공 문맥)
    "L21": 2,   # IT·보안 (해킹/사이버 문맥)
    "L23": 2,   # 엔터테인먼트 (전속계약/매니지먼트 문맥)
    "L24": 2,   # 조세불복 (세무조사/과세처분 문맥 — L20 세금보다 우선)
    "L27": 2,   # 환경법 (환경오염/소음 문맥)
    "L28": 2,   # 무역·관세 (통관/관세 문맥)
    "L29": 2,   # 게임·콘텐츠 (게임규제/아이템 문맥)
    "L32": 2,   # 공정거래 (독점/담합/가맹 문맥)
    "L35": 2,   # 헌법 (기본권/위헌/헌법소원 문맥)
    "L39": 2,   # 정보통신 (통신분쟁/방송규제 문맥)
    "L40": 2,   # 인권 (차별/인권침해 문맥)
    "L44": 3,   # 사회복지 (기초생활/복지 — 넓은 도메인)
    "L45": 2,   # 교육·청소년 (학원분쟁/교권 문맥 — L37 학폭과 구분)
    "L46": 2,   # 보험·연금 (국민연금/건강보험 문맥 — L16 보험과 구분)
    "L50": 2,   # 다문화·이주 (비자/체류/귀화 문맥)
    "L33": 2,   # 우주·항공 (드론/위성/우주 문맥)
    "L36": 2,   # 문화재 (문화유산/매장문화재 문맥)
    "L47": 2,   # 규제샌드박스 (신산업/실증특례 문맥)
    "L48": 2,   # 예술·문화예술 (예술인/공연/전시 문맥)
    "L49": 2,   # 식품·의약품 (식품위생/약사 문맥)
    "L51": 2,   # 종교 (종교단체/신앙자유 문맥)
    "L53": 2,   # 농림·축산 (농지/축산업 문맥)
    "L54": 2,   # 해양·수산 (어업권/해양환경 문맥)
    "L55": 2,   # 과학기술 (R&D/기술이전 문맥)
    "L56": 2,   # 장애인 권리 (차별금지/편의제공 문맥)
    "L58": 2,   # 스포츠법 (선수계약/도핑 문맥)
    "L59": 2,   # AI·데이터 (인공지능/알고리즘 문맥)
    "L10": 2,   # 민사집행 (압류/경매 문맥 — L01 민사보다 우선)
    "L11": 2,   # 채권추심/개인회생 (빚/회생 문맥 — L01 민사보다 우선)
    "L20": 3,   # 세금 (일반 세금 — L24 조세불복보다 후순위)
    "L25": 2,   # 군형법 (군대/병역 문맥 — L22 형사보다 우선)
    "L31": 2,   # 행정법 (행정처분/행정소송 문맥)
    "L34": 2,   # 개인정보 (정보유출/CCTV 문맥)
    "L60": 4,   # 법률총괄 (복합쟁점 — 가장 낮은 우선순위)
    "L01": 3,   # 민사법 (기본값과 동일 — 계약 문맥이 핵심)
    "L06": 3,   # 손해배상 (기본값과 동일 — 피해/보상 문맥이 핵심)
    "L22": 5,   # 형사법 (포괄적 — 최하위 우선순위)
    # 기본값: 3
}


def _nlu_detect_intent(query: str, lang: str = "") -> Optional[str]:
    """자연어 패턴 기반 법적 의도 감지 → 리더 ID 반환 (L01~L60).

    키워드 매칭과 달리, (상황+행위) 조합 정규식을 사용하여
    "친구한테 맞았어요" → L22, "보증금을 안 돌려줘요" → L08 등
    구어체 질문을 정확하게 분류합니다.

    lang="en"이면 영문 패턴(_NLU_COMPILED_EN)을 사용합니다.

    여러 도메인이 매칭되면 (1) 매칭 패턴 수, (2) 우선순위로 결정.
    예: "남편이 때린 적 있어요" → L41(가사, 1매칭, 우선1) > L22(형사, 1매칭, 우선5)
    """
    compiled = _NLU_COMPILED_EN if lang == "en" else _NLU_COMPILED
    matches: List[tuple] = []  # (leader_id, match_count)

    for leader_id, compiled_patterns in compiled.items():
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

_DOMAIN_MAP_EN = {
    "L01_CIVIL": (["civil", "contract", "breach", "obligation", "claim", "lawsuit", "tort", "damages", "statute of limitations", "demand letter", "payment order", "small claims"], "L01"),
    "L02_PROPERTY": (["real estate", "property", "land", "building", "apartment", "title", "registration", "deed"], "L02"),
    "L03_CONSTRUCTION": (["construction", "building permit", "defect", "contractor", "architect"], "L03"),
    "L04_REDEVEL": (["redevelopment", "reconstruction", "urban renewal", "association"], "L04"),
    "L05_MEDICAL": (["medical", "malpractice", "hospital", "doctor", "surgery", "misdiagnosis", "negligence"], "L05"),
    "L06_DAMAGES": (["damages", "compensation", "liability", "negligence", "tort", "settlement"], "L06"),
    "L07_TRAFFIC": (["traffic accident", "car accident", "vehicle", "collision", "insurance claim", "fault"], "L07"),
    "L08_LEASE": (["lease", "tenant", "landlord", "deposit", "rent", "jeonse", "wolse", "eviction", "rental", "security deposit"], "L08"),
    "L09_GOVCONTRACT": (["government contract", "procurement", "bid", "tender"], "L09"),
    "L10_EXECUTION": (["enforcement", "seizure", "garnishment", "attachment", "foreclosure"], "L10"),
    "L11_COLLECTION": (["debt collection", "collection", "creditor", "bankruptcy", "insolvency", "debt restructuring", "credit recovery"], "L11"),
    "L12_AUCTION": (["auction", "foreclosure", "registry", "registration"], "L12"),
    "L13_COMMERCIAL": (["commercial law", "promissory note", "check", "merchant"], "L13"),
    "L14_CORP_MA": (["corporate", "M&A", "merger", "acquisition", "shareholder", "board", "director", "fiduciary"], "L14"),
    "L15_STARTUP": (["startup", "venture", "partnership", "entrepreneur", "business registration", "franchise", "small business"], "L15"),
    "L16_INSURANCE": (["insurance", "insurance claim", "policy", "coverage", "insurer"], "L16"),
    "L17_INTL_TRADE": (["international trade", "export", "import", "arbitration", "international contract"], "L17"),
    "L18_ENERGY": (["energy", "power plant", "solar", "wind", "renewable"], "L18"),
    "L19_MARINE_AIR": (["maritime", "aviation", "ship", "vessel", "airline", "cargo"], "L19"),
    "L20_TAX_FIN": (["tax", "income tax", "capital gains", "VAT", "tax return", "filing", "deduction"], "L20"),
    "L21_IT_SEC": (["IT", "cybersecurity", "hacking", "data breach", "cyber crime"], "L21"),
    "L22_CRIMINAL": (["criminal", "prosecution", "assault", "fraud", "theft", "embezzlement", "arrest", "police", "charge", "DUI", "stalking", "harassment", "defamation"], "L22"),
    "L23_ENTERTAIN": (["entertainment", "celebrity", "talent", "management", "exclusive contract"], "L23"),
    "L24_TAX_APPEAL": (["tax appeal", "tax audit", "tax assessment", "tax tribunal"], "L24"),
    "L25_MILITARY": (["military", "army", "soldier", "conscription", "service", "draft", "discharge"], "L25"),
    "L26_IP": (["intellectual property", "patent", "trademark", "trade secret", "copyright"], "L26"),
    "L27_ENVIRON": (["environment", "pollution", "noise", "waste", "contamination", "emission"], "L27"),
    "L28_CUSTOMS": (["customs", "tariff", "import", "export", "FTA", "clearance"], "L28"),
    "L29_GAME": (["game", "gaming", "digital content", "virtual item"], "L29"),
    "L30_LABOR": (["labor", "employment", "fired", "dismissed", "wage", "salary", "overtime", "severance", "workplace", "harassment", "unfair dismissal", "termination"], "L30"),
    "L31_ADMIN": (["administrative", "permit", "license", "fine", "penalty", "appeal", "tribunal"], "L31"),
    "L32_FAIRTRADE": (["fair trade", "antitrust", "monopoly", "cartel", "collusion", "franchise"], "L32"),
    "L33_SPACE": (["drone", "UAV", "satellite", "aerospace", "space"], "L33"),
    "L34_PRIVACY": (["privacy", "personal data", "data protection", "GDPR", "CCTV", "surveillance"], "L34"),
    "L35_CONSTITUTION": (["constitution", "constitutional", "fundamental rights", "unconstitutional", "judicial review"], "L35"),
    "L36_CULTURE": (["cultural heritage", "cultural property", "monument", "artifact"], "L36"),
    "L37_JUVENILE": (["juvenile", "school violence", "bullying", "minor", "youth"], "L37"),
    "L38_CONSUMER": (["consumer", "refund", "return", "defective", "warranty", "product liability", "lemon"], "L38"),
    "L39_TELECOM": (["telecom", "telecommunications", "broadcast", "carrier", "ISP"], "L39"),
    "L40_HUMAN_RIGHTS": (["human rights", "discrimination", "equality", "hate speech"], "L40"),
    "L41_DIVORCE": (["divorce", "family", "custody", "child support", "alimony", "property division", "domestic violence", "spouse", "marriage"], "L41"),
    "L42_COPYRIGHT": (["copyright", "plagiarism", "piracy", "DMCA", "unauthorized use", "fair use"], "L42"),
    "L43_INDUSTRIAL": (["industrial accident", "workers compensation", "workplace injury", "occupational", "safety"], "L43"),
    "L44_WELFARE": (["welfare", "social security", "basic living", "public assistance"], "L44"),
    "L45_EDUCATION": (["education", "school", "tuition", "academy", "student"], "L45"),
    "L46_PENSION": (["pension", "national pension", "health insurance", "retirement fund"], "L46"),
    "L47_VENTURE": (["regulatory sandbox", "new industry", "special zone"], "L47"),
    "L48_ARTS": (["arts", "artist", "performance", "exhibition", "cultural arts"], "L48"),
    "L49_FOOD": (["food", "food safety", "pharmaceutical", "drug", "hygiene", "HACCP"], "L49"),
    "L50_MULTICUL": (["immigration", "visa", "foreigner", "residence permit", "refugee", "naturalization", "multicultural"], "L50"),
    "L51_RELIGION": (["religion", "church", "temple", "faith", "religious"], "L51"),
    "L52_MEDIA": (["media", "press", "online defamation", "SNS", "social media", "fake news", "hate comment"], "L52"),
    "L53_AGRI": (["agriculture", "farmland", "livestock", "farming", "crop"], "L53"),
    "L54_FISHERY": (["fishery", "fishing", "marine", "ocean", "aquaculture"], "L54"),
    "L55_SCIENCE": (["R&D", "research", "technology transfer", "research ethics"], "L55"),
    "L56_DISABILITY": (["disability", "disabled", "accessibility", "accommodation", "disability rights"], "L56"),
    "L57_INHERITANCE": (["inheritance", "estate", "will", "probate", "heir", "bequest", "trust", "estate tax", "inheritance tax"], "L57"),
    "L58_SPORTS": (["sports", "athlete", "doping", "sports facility", "player contract"], "L58"),
    "L59_AI_ETHICS": (["AI", "artificial intelligence", "algorithm", "data", "autonomous", "machine learning"], "L59"),
}


def select_swarm_leader(query: str, leaders: Dict, lang: str = "") -> Dict:
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
    nlu_leader_id = _nlu_detect_intent(query, lang=lang)
    if nlu_leader_id:
        nlu_leader = registry.get(nlu_leader_id)
        if nlu_leader:
            logger.info(f"[L2 NLU] {nlu_leader_id} 리더 자동 배정 (패턴 매칭)")
            return nlu_leader

    # 3) 도메인 키워드 매칭 (전체 60 Leader 매핑)
    if lang == "en":
        domain_map = _DOMAIN_MAP_EN
    else:
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
                return _safe_extract_gemini_text(resp)
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
        # JSON 추출 (중첩 JSON, 코드블록, 잘린 JSON 복구 지원)
        result = _safe_extract_json(text)
        if result and result.get("tier") and result.get("leader_id"):
            recovered = "(복구)" if "}" not in text[text.find("{"):] else ""
            logger.info(f"[Tier Router] Gemini 분석{recovered}: tier={result.get('tier')}, "
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
            "쇼핑", "할인", "세일",
        ]
        is_legal = not any(kw in query for kw in non_legal_keywords)

    return {
        "tier": tier,
        "complexity": complexity,
        "is_document": is_document,
        "leader_id": leader.get("_id", "L60"),
        "leader_name": leader_name,
        "leader_specialty": leader_specialty,
        "summary": query[:50],
        "is_legal": is_legal,
    }
