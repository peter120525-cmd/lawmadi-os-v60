"""
Lawmadi OS v60 -- 3-Stage Hybrid Legal Pipeline.
LawmadiLM(강화 프롬프트, 3000토큰) + RAG + DRF 전수 검증, Stage 4 제거.

Pipeline:
  Stage 0: Gemini 질문 분류 (병렬 실행)
  Stage 1: RAG 조문 검색 (ChromaDB + law_cache, Stage 0과 병렬)
  Stage 2: LawmadiLM 강화 답변 (5단계 프레임워크, RAG 컨텍스트 기반)
  Stage 3: DRF 실시간 전수 검증 (조문번호까지 검증)
  → Fail-Closed → 응답

사용법:
    from core.pipeline import set_runtime, set_law_cache, run_legal_pipeline
    set_runtime(RUNTIME)
    set_law_cache(LAW_CACHE, build_cache_context, match_ssot_sources, build_ssot_context)
"""
import json
import os
import re
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx
from google.genai import types as genai_types
from core.constants import (
    GEMINI_MODEL,
    LAWMADILM_API_URL,
    LAWMADILM_RAG_URL,
    FAIL_CLOSED_RESPONSE,
)
from utils.helpers import _remove_think_blocks, _safe_extract_gemini_text
from prompts.system_instructions import build_lawmadilm_prompt, build_system_instruction

logger = logging.getLogger("LawmadiOS.Pipeline")

# 최소 법률 응답 길이 (이 미만이면 재생성 시도)
MIN_LEGAL_RESPONSE_GENERAL = 2000   # 일반 답변 최소 2000자
MIN_LEGAL_RESPONSE_EXPERT = 4000    # 전문가 답변 최소 4000자

# ---------------------------------------------------------------------------
# Module-level state (set via setters from main.py)
# ---------------------------------------------------------------------------
_RUNTIME: Dict[str, Any] = {}
_LAW_CACHE: Dict[str, Any] = {}
_LEADER_PROFILES: Dict[str, Any] = {}
_build_cache_context_fn = None
_match_ssot_sources_fn = None
_build_ssot_context_fn = None


def _load_leader_profiles() -> Dict[str, Any]:
    """leader-profiles.json 로드 (리더 철학·접근방식·정체성)"""
    global _LEADER_PROFILES
    if _LEADER_PROFILES:
        return _LEADER_PROFILES
    try:
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "frontend", "public", "leader-profiles.json",
        )
        with open(path, "r", encoding="utf-8") as f:
            _LEADER_PROFILES = json.load(f)
        logger.info(f"✅ 리더 프로필 로드 완료: {len(_LEADER_PROFILES)}명")
    except Exception as e:
        logger.warning(f"🟡 리더 프로필 로드 실패: {e}")
        _LEADER_PROFILES = {}
    return _LEADER_PROFILES


# 리더별 핵심 법률 (DRF 검증 통과율 향상 - RAG 컨텍스트 주입용)
_LEADER_LAW_BOOST = {
    "L01": (
        "• 민법 제162조 제1항: 채권은 10년간 행사하지 아니하면 소멸시효가 완성한다.\n"
        "• 민법 제163조: 다음 각호의 채권은 3년간 행사하지 아니하면 소멸시효가 완성한다. 1. 이자, 부양료, 급료, 사용료 기타 1년 이내의 기간으로 정한 금전 또는 물건의 지급을 목적으로 한 채권.\n"
        "• 민법 제390조: 채무자가 채무의 내용에 좇은 이행을 하지 아니한 때에는 채권자는 손해배상을 청구할 수 있다.\n"
        "• 민법 제580조 제1항: 매매의 목적물에 하자가 있는 때에는 매수인은 계약의 해제 또는 손해배상을 청구할 수 있다.\n"
        "• 민법 제741조: 법률상 원인 없이 타인의 재산 또는 노무로 인하여 이익을 얻고 이로 인하여 타인에게 손해를 가한 자는 그 이익을 반환하여야 한다.\n"
        "• 민법 제750조: 고의 또는 과실로 인한 위법행위로 타인에게 손해를 가한 자는 그 손해를 배상할 책임이 있다.\n"
        "• 민법 제766조 제1항: 불법행위로 인한 손해배상의 청구권은 피해자나 그 법정대리인이 그 손해 및 가해자를 안 날로부터 3년간 이를 행사하지 아니하면 시효로 인하여 소멸한다.\n"
        "• 민사소송법 제462조: 금전, 그 밖에 대체물이나 유가증권의 일정한 수량의 지급을 목적으로 하는 청구에 대하여 채권자는 지급명령을 신청할 수 있다.\n"
        "• 민사집행법 제276조 제1항: 가압류는 금전채권이나 금전으로 환산할 수 있는 채권에 대하여 할 수 있다.\n"
        "• 민사집행법 제277조: 가압류는 다툼이 있는 권리관계에 대한 현재의 위험을 방지하기 위하여 필요한 경우에 한하여 할 수 있다."
    ),
    "L02": (
        "• 부동산등기법 제3조: 등기는 당사자의 신청 또는 관공서의 촉탁에 따라 한다.\n"
        "• 부동산등기법 제23조 제1항: 등기는 법률에 다른 규정이 없는 경우에는 당사자의 신청 또는 관공서의 촉탁이 없으면 하지 못한다.\n"
        "• 민법 제186조: 부동산에 관한 법률행위로 인한 물권의 득실변경은 등기하여야 그 효력이 생긴다.\n"
        "• 민법 제187조: 상속, 공용징수, 판결, 경매 기타 법률의 규정에 의한 부동산에 관한 물권의 취득은 등기를 요하지 아니한다.\n"
        "• 공인중개사법 제25조 제1항: 개업공인중개사는 중개대상물의 확인·설명에 관하여 성실·정확하게 중개의뢰인에게 설명하고, 토지대장 등본 등 설명의 근거자료를 제시하여야 한다.\n"
        "• 공인중개사법 제30조 제1항: 개업공인중개사는 중개행위를 함에 있어서 고의 또는 과실로 거래당사자에게 재산상의 손해를 발생하게 한 때에는 그 손해를 배상할 책임이 있다.\n"
        "• 부동산 거래신고 등에 관한 법률 제3조 제1항: 거래당사자는 부동산 등의 매매계약을 체결한 경우 그 실제 거래가격 등을 거래계약의 체결일부터 30일 이내에 신고하여야 한다.\n"
        "• 민법 제563조: 매매는 당사자 일방이 재산권을 상대방에게 이전할 것을 약정하고 상대방이 그 대금을 지급할 것을 약정함으로써 그 효력이 생긴다.\n"
        "• 민법 제568조 제1항: 매도인은 매수인에 대하여 매매의 목적이 된 권리를 이전하여야 하며, 부동산에 있어서는 등기를 이전하여야 한다.\n"
        "• 민법 제356조: 저당권자는 저당물의 경매대가에서 다른 채권자보다 자기채권의 우선변제를 받을 권리가 있다."
    ),
    "L04": (
        "• 도시 및 주거환경정비법 제2조 제2호: 정비사업이란 도시기능을 회복하기 위하여 정비구역에서 정비기반시설을 정비하거나 주택 등 건축물을 개량 또는 건설하는 사업을 말한다.\n"
        "• 도시 및 주거환경정비법 제39조 제1항: 재개발사업의 조합원은 토지등소유자로 한다.\n"
        "• 도시 및 주거환경정비법 제39조 제2항: 재건축사업의 조합원은 재건축사업에 동의한 자로 한다.\n"
        "• 도시 및 주거환경정비법 제72조 제1항: 사업시행자는 분양설계, 분양대상자별 종전의 토지 또는 건축물의 명세 등을 포함한 관리처분계획을 수립하여 시장·군수등의 인가를 받아야 한다.\n"
        "• 도시 및 주거환경정비법 제74조 제1항: 관리처분계획에 따라 분양대상자에게 분양하여야 한다.\n"
        "• 도시 및 주거환경정비법 제86조 제1항: 재개발사업 또는 재건축사업의 분양을 받은 자가 분양받은 권리를 전매하는 경우 투기과열지구에서는 전매가 제한된다.\n"
        "• 주택법 제64조 제1항: 사업주체가 건설·공급하는 주택의 입주자로 선정된 지위(분양권)는 투기과열지구에서 전매가 제한된다."
    ),
    "L07": (
        "• 도로교통법 제44조 제1항: 누구든지 술에 취한 상태에서 자동차 등을 운전하여서는 아니 된다.\n"
        "• 도로교통법 제148조의2 제3항 제1호: 혈중알코올농도 0.08% 이상인 상태에서 운전한 사람은 1년 이상 2년 이하의 징역이나 500만원 이상 1천만원 이하의 벌금에 처한다.\n"
        "• 도로교통법 제148조의2 제3항 제2호: 혈중알코올농도 0.03% 이상 0.08% 미만인 상태에서 운전한 사람은 1년 이하의 징역이나 500만원 이하의 벌금에 처한다.\n"
        "• 도로교통법 제54조 제1항: 차의 운전 등 교통으로 인하여 사람을 사상하거나 물건을 손괴한 경우 즉시 정차하여 필요한 조치를 하여야 한다.\n"
        "• 특정범죄 가중처벌 등에 관한 법률 제5조의3 제1항: 도로교통법 제2조에 규정된 자동차의 교통으로 인하여 형법 제268조의 죄를 범한 해당 차량의 운전자가 피해자를 구호하는 등의 조치를 하지 아니하고 도주한 경우에는 1년 이상의 유기징역에 처한다.\n"
        "• 특정범죄 가중처벌 등에 관한 법률 제5조의3 제2항: 피해자를 사망에 이르게 하고 도주한 경우에는 무기 또는 5년 이상의 징역에 처한다.\n"
        "• 특정범죄 가중처벌 등에 관한 법률 제5조의11: 음주 또는 약물의 영향으로 정상적인 운전이 곤란한 상태에서 자동차를 운전하여 사람을 사상한 경우 가중처벌한다.\n"
        "• 형법 제52조 제1항: 죄를 범한 후 수사책임이 있는 관서에 자수한 때에는 그 형을 감경 또는 면제할 수 있다."
    ),
    "L08": (
        "• 주택임대차보호법 제3조 제1항: 임대차는 그 등기가 없는 경우에도 임차인이 주택의 인도와 주민등록을 마친 때에는 그 다음 날부터 제삼자에 대하여 효력이 생긴다.\n"
        "• 주택임대차보호법 제3조의2 제1항: 제3조 제1항의 대항요건과 임대차계약증서상의 확정일자를 갖춘 임차인은 민사집행법에 따른 경매 또는 국세징수법에 따른 공매 시 임차주택의 환가대금에서 후순위권리자나 그 밖의 채권자보다 우선하여 보증금을 변제받을 권리가 있다.\n"
        "• 주택임대차보호법 제3조의3 제1항: 임차권등기명령은 임대차가 종료된 후 보증금이 반환되지 아니한 경우 임차인은 임차주택의 소재지를 관할하는 지방법원에 임차권등기명령을 신청할 수 있다.\n"
        "• 주택임대차보호법 제6조의3 제1항: 임차인은 임대인에게 계약갱신을 요구할 수 있다. 다만, 임대인은 다음 각 호의 어느 하나에 해당하는 경우에는 거절할 수 있다.\n"
        "• 주택임대차보호법 제8조 제1항: 임차인은 보증금 중 일정액을 다른 담보물권자보다 우선하여 변제받을 권리가 있다.\n"
        "• 민법 제640조: 건물 기타 공작물의 임대차에는 임차인의 차임연체액이 2기의 차임액에 달하는 때에는 임대인은 계약을 해지할 수 있다.\n"
        "• 상가건물 임대차보호법 제10조 제1항: 임대인은 임차인이 임대차기간이 만료되기 6개월 전부터 1개월 전까지 사이에 계약갱신을 요구할 경우 정당한 사유 없이 거절하지 못한다.\n"
        "• 상가건물 임대차보호법 제10조의3 제1항: 권리금이란 임대차 목적물인 상가건물에서 영업을 하는 자 또는 영업을 하려는 자가 영업시설·비품, 거래처, 신용, 영업상의 노하우, 상가건물의 위치에 따른 영업상의 이점 등 유형·무형의 재산적 가치의 양도 또는 이용대가로서 임대인, 임차인에게 보증금과 차임 이외에 지급하는 금전 등의 대가를 말한다.\n"
        "• 상가건물 임대차보호법 제10조의4 제1항: 임대인은 임대차기간이 끝나기 6개월 전부터 임대차 종료 시까지 임차인이 주선한 신규임차인이 되려는 자로부터 권리금을 지급받는 것을 방해하여서는 아니 된다.\n"
        "• 상가건물 임대차보호법 제10조의4 제3항: 임대인이 제1항을 위반하여 임차인에게 손해를 발생하게 한 때에는 그 손해를 배상할 책임이 있다."
    ),
    "L14": (
        "• 상법 제382조의3: 이사는 법령과 정관의 규정에 따라 회사를 위하여 그 직무를 충실하게 수행하여야 한다.\n"
        "• 상법 제397조 제1항: 이사는 이사회의 승인이 없으면 자기 또는 제삼자의 계산으로 회사의 영업부류에 속한 거래를 하지 못하며, 같은 종류의 영업을 목적으로 하는 다른 회사의 무한책임사원이나 이사가 되지 못한다.\n"
        "• 상법 제397조의2 제1항: 이사는 이사회의 승인 없이 현재 또는 장래에 회사의 이익이 될 수 있는 사업기회를 자기 또는 제삼자의 이익을 위하여 이용하여서는 아니 된다.\n"
        "• 상법 제399조 제1항: 이사가 법령 또는 정관에 위반한 행위를 하거나 그 임무를 게을리한 경우에는 그 이사는 회사에 대하여 연대하여 손해를 배상할 책임이 있다.\n"
        "• 상법 제403조 제1항: 발행주식의 총수의 100분의 1 이상에 해당하는 주식을 가진 주주는 회사에 대하여 이사의 책임을 추궁할 소의 제기를 청구할 수 있다.\n"
        "• 상법 제403조 제3항: 회사가 청구를 받은 날부터 30일 내에 소를 제기하지 아니한 때에는 주주는 즉시 회사를 위하여 소를 제기할 수 있다.\n"
        "• 상법 제522조의3 제1항: 합병에 반대하는 주주는 주주총회 전에 회사에 대하여 서면으로 합병에 반대하는 의사를 통지한 경우에는 자기가 소유하고 있는 주식의 매수를 청구할 수 있다.\n"
        "• 상법 제176조의5 제1항: 상장회사의 합병에 반대하는 주주의 주식매수가격은 이사회 결의일 이전의 시장가격을 기초로 산정한다."
    ),
    "L30": (
        "• 근로기준법 제23조 제1항: 사용자는 근로자에게 정당한 이유 없이 해고, 휴직, 정직, 전직, 감봉, 그 밖의 징벌을 하지 못한다.\n"
        "• 근로기준법 제24조 제1항: 사용자가 경영상 이유에 의하여 근로자를 해고하려면 긴박한 경영상의 필요가 있어야 한다.\n"
        "• 근로기준법 제24조 제2항: 사용자는 해고를 피하기 위한 노력을 다하여야 하며, 합리적이고 공정한 해고의 기준을 정하고, 이에 따라 그 대상자를 선정하여야 한다.\n"
        "• 근로기준법 제26조: 사용자는 근로자를 해고하려면 적어도 30일 전에 예고를 하여야 하고, 30일 전에 예고를 하지 아니하였을 때에는 30일분 이상의 통상임금을 지급하여야 한다.\n"
        "• 근로기준법 제28조 제1항: 사용자가 근로자에게 부당해고등을 하면 근로자는 노동위원회에 구제를 신청할 수 있다.\n"
        "• 근로기준법 제34조 제1항: 사용자는 계속근로기간 1년에 대하여 30일분 이상의 평균임금을 퇴직금으로 퇴직하는 근로자에게 지급하여야 한다.\n"
        "• 근로기준법 제36조: 사용자는 근로자가 사망 또는 퇴직한 경우에는 그 지급 사유가 발생한 때부터 14일 이내에 임금, 보상금, 그 밖에 일체의 금품을 지급하여야 한다.\n"
        "• 근로기준법 제37조 제1항: 임금채권은 사용자의 총재산에 대하여 질권 또는 저당권에 의하여 담보된 채권 외에는 조세·공과금 및 다른 채권에 우선하여 변제되어야 한다.\n"
        "• 근로기준법 제43조의2: 사용자는 임금 등의 지급을 지체한 경우 그 다음 날부터 지급하는 날까지의 지연 일수에 대하여 연 100분의 20 이내의 범위에서 대통령령으로 정하는 이율에 따른 지연이자를 지급하여야 한다."
    ),
    "L41": (
        "• 민법 제834조: 부부는 협의에 의하여 이혼할 수 있다.\n"
        "• 민법 제836조의2 제1항: 협의상 이혼을 하려는 자는 가정법원이 제공하는 이혼에 관한 안내를 받아야 하고, 가정법원은 필요한 경우 당사자에게 상담에 관하여 전문적인 지식과 경험을 갖춘 전문상담인의 상담을 받을 것을 권고할 수 있다.\n"
        "• 민법 제839조의2 제1항: 협의상 이혼한 자의 일방은 다른 일방에 대하여 재산분할을 청구할 수 있다.\n"
        "• 민법 제839조의2 제2항: 재산분할에 관하여 협의가 되지 아니하거나 협의할 수 없는 때에는 가정법원은 당사자의 청구에 의하여 당사자 쌍방의 협력으로 이룩한 재산의 액수 기타 사정을 참작하여 분할의 액수와 방법을 정한다.\n"
        "• 민법 제840조: 부부의 일방은 다음 각호의 사유가 있는 경우에는 가정법원에 이혼을 청구할 수 있다. 1. 배우자에 부정한 행위가 있었을 때.\n"
        "• 민법 제843조: 이혼에 관하여는 제806조의 규정을 준용한다. (위자료 청구)\n"
        "• 민법 제837조 제1항: 당사자는 그 자의 양육에 관한 사항을 협의에 의하여 정한다.\n"
        "• 민법 제837조의2 제1항: 자를 직접 양육하지 아니하는 부모의 일방과 자는 상호 면접교섭할 수 있는 권리를 가진다.\n"
        "• 민법 제909조 제4항: 부모의 이혼의 경우에는 부모의 협의로 친권자를 정하여야 하고, 협의할 수 없거나 협의가 이루어지지 아니하는 경우에는 가정법원은 직권으로 또는 당사자의 청구에 따라 친권자를 정한다.\n"
        "• 가사소송법 제2조 제1항: 가정법원은 다류 가사비송사건 및 마류 가사소송사건에 관하여 직권으로 사실조사 및 필요한 증거조사를 할 수 있다."
    ),
    "L43": (
        "• 산업안전보건법 제38조 제1항: 사업주는 근로자가 추락할 위험이 있는 장소, 토사 등이 붕괴할 우려가 있는 장소 등에 안전난간, 울타리, 안전방망 등 안전조치를 하여야 한다.\n"
        "• 산업안전보건법 제39조 제1항: 사업주는 근로자의 건강장해를 예방하기 위하여 보건조치를 하여야 한다.\n"
        "• 산업안전보건법 제167조 제1항: 제38조 또는 제39조를 위반하여 근로자를 사망에 이르게 한 자는 7년 이하의 징역 또는 1억원 이하의 벌금에 처한다.\n"
        "• 산업재해보상보험법 제5조 제1호: 업무상의 재해란 업무상의 사유에 따른 근로자의 부상·질병·장해 또는 사망을 말한다.\n"
        "• 산업재해보상보험법 제37조 제1항: 근로자가 업무상 사유에 의한 부상·질병·장해 또는 사망은 업무상의 재해로 본다. 업무와 재해 사이에 상당인과관계가 있어야 한다.\n"
        "• 산업재해보상보험법 제37조 제1항 제2호: 업무상 질병에 해당하는 경우 업무상 재해로 인정한다. 업무수행 과정에서 물리적 인자, 화학물질, 분진, 병원체, 신체에 부담을 주는 업무 등으로 발생한 질병이 해당된다.\n"
        "• 산업재해보상보험법 제40조 제1항: 요양급여는 근로자가 업무상의 사유로 부상을 당하거나 질병에 걸린 경우에 그 근로자에게 지급한다.\n"
        "• 중대재해 처벌 등에 관한 법률 제2조 제2호: 중대산업재해란 산업재해 중 사망자가 1명 이상 발생하거나, 동일한 사고로 6개월 이상 치료가 필요한 부상자가 2명 이상 발생하거나, 동일한 유해요인으로 급성중독 등 직업성 질병자가 1년 이내에 3명 이상 발생한 경우를 말한다.\n"
        "• 중대재해 처벌 등에 관한 법률 제6조 제1항: 사업주 또는 경영책임자등이 안전 및 보건 확보의무를 위반하여 중대산업재해가 발생한 경우 1년 이상의 징역 또는 10억원 이하의 벌금에 처한다.\n"
        "• 근로기준법 제76조의2: 사용자 또는 근로자는 직장 내 괴롭힘이 발생하였거나 발생할 우려가 있는 경우 사업주에게 신고할 수 있다.\n"
        "• 근로기준법 제76조의3 제1항: 사업주는 직장 내 괴롭힘 신고를 접수하거나 직장 내 괴롭힘이 발생한 사실을 인지한 경우에는 지체 없이 그 사실 확인을 위한 조사를 실시하여야 한다."
    ),
    "L34": (
        "• 개인정보 보호법 제15조 제1항: 개인정보처리자는 다음 각 호의 어느 하나에 해당하는 경우에는 개인정보를 수집할 수 있으며 그 수집 목적의 범위에서 이용할 수 있다. 1. 정보주체의 동의를 받은 경우.\n"
        "• 개인정보 보호법 제17조 제1항: 개인정보처리자는 다음 각 호의 어느 하나에 해당되는 경우에는 정보주체의 개인정보를 제3자에게 제공할 수 있다.\n"
        "• 개인정보 보호법 제23조 제1항: 개인정보처리자는 사상·신념, 노동조합·정당의 가입·탈퇴, 정치적 견해, 건강, 성생활 등에 관한 정보, 그 밖에 정보주체의 사생활을 현저히 침해할 우려가 있는 개인정보를 처리하여서는 아니 된다.\n"
        "• 개인정보 보호법 제23조의2 제1항: 개인정보처리자가 생체인식정보를 처리하려면 정보주체에게 생체인식정보의 처리 목적, 항목 등을 알리고 별도의 동의를 받아야 한다.\n"
        "• 개인정보 보호법 제25조 제1항: 누구든지 불특정 다수가 이용하는 목욕실, 화장실, 발한실, 탈의실 등 개인의 사생활을 현저히 침해할 우려가 있는 장소의 내부를 볼 수 있도록 영상정보처리기기를 설치·운영하여서는 아니 된다.\n"
        "• 개인정보 보호법 제34조 제1항: 개인정보처리자는 개인정보가 유출되었음을 알게 되었을 때에는 지체 없이 해당 정보주체에게 유출된 개인정보의 항목, 유출된 시점과 그 경위 등을 알려야 한다.\n"
        "• 개인정보 보호법 제34조의2: 개인정보처리자는 1천명 이상의 정보주체에 관한 개인정보가 유출된 경우에는 정보주체에 대한 통지 및 조치결과를 지체 없이 개인정보보호위원회에 신고하여야 한다.\n"
        "• 개인정보 보호법 제39조의15: 정보통신서비스 제공자등의 개인정보 처리에 관한 특례를 정한다.\n"
        "• 개인정보 보호법 제64조의2 제1항: 개인정보보호위원회는 개인정보처리자가 처리하는 주민등록번호가 분실·도난·유출·위조·변조 또는 훼손된 경우에는 5억원 이하의 과징금을 부과·징수할 수 있다.\n"
        "• 개인정보 보호법 제28조의7: 개인정보처리자는 개인정보의 국외 이전을 하려면 정보주체에게 보호위원회가 고시하는 사항을 알리고 동의를 받아야 한다."
    ),
    "L52": (
        "• 형법 제307조 제1항: 공연히 사실을 적시하여 사람의 명예를 훼손한 자는 2년 이하의 징역이나 금고 또는 500만원 이하의 벌금에 처한다.\n"
        "• 형법 제307조 제2항: 공연히 허위의 사실을 적시하여 사람의 명예를 훼손한 자는 5년 이하의 징역, 10년 이하의 자격정지 또는 1천만원 이하의 벌금에 처한다.\n"
        "• 형법 제309조 제1항: 사람을 비방할 목적으로 신문, 잡지 또는 라디오 기타 출판물에 의하여 제307조 제1항의 죄를 범한 자는 3년 이하의 징역이나 금고 또는 700만원 이하의 벌금에 처한다.\n"
        "• 형법 제309조 제2항: 제1항의 방법으로 제307조 제2항의 죄를 범한 자는 7년 이하의 징역, 10년 이하의 자격정지 또는 1천500만원 이하의 벌금에 처한다.\n"
        "• 형법 제311조: 공연히 사람을 모욕한 자는 1년 이하의 징역이나 금고 또는 200만원 이하의 벌금에 처한다.\n"
        "• 형법 제312조 제1항: 제308조와 제311조의 죄는 고소가 있어야 공소를 제기할 수 있다.\n"
        "• 형법 제312조 제2항: 제307조와 제309조의 죄는 피해자의 명시한 의사에 반하여 공소를 제기할 수 없다.\n"
        "• 정보통신망 이용촉진 및 정보보호 등에 관한 법률 제70조 제1항: 사람을 비방할 목적으로 정보통신망을 통하여 공공연하게 사실을 드러내어 다른 사람의 명예를 훼손한 자는 3년 이하의 징역 또는 3천만원 이하의 벌금에 처한다.\n"
        "• 정보통신망 이용촉진 및 정보보호 등에 관한 법률 제70조 제2항: 사람을 비방할 목적으로 정보통신망을 통하여 공공연하게 거짓의 사실을 드러내어 다른 사람의 명예를 훼손한 자는 7년 이하의 징역, 10년 이하의 자격정지 또는 5천만원 이하의 벌금에 처한다.\n"
        "• 민법 제750조: 고의 또는 과실로 인한 위법행위로 타인에게 손해를 가한 자는 그 손해를 배상할 책임이 있다.\n"
        "• 민법 제751조 제1항: 타인의 신체, 자유 또는 명예를 해하거나 기타 정신상고통을 가한 자는 재산 이외의 손해에 대하여도 배상할 책임이 있다.\n"
        "• 형사소송법 제230조 제1항: 친고죄에 대하여는 범인을 알게 된 날로부터 6개월을 경과하면 고소하지 못한다."
    ),
    "L57": (
        "• 민법 제1000조 제1항: 상속에 있어서는 다음 순위로 상속인이 된다. 1. 피상속인의 직계비속 2. 피상속인의 직계존속 3. 피상속인의 형제자매 4. 피상속인의 4촌 이내의 방계혈족.\n"
        "• 민법 제1003조 제1항: 피상속인의 배우자는 제1000조 제1항 제1호와 제2호의 규정에 의한 상속인이 있는 경우에는 그 상속인과 동순위로 공동상속인이 된다.\n"
        "• 민법 제1003조 제2항: 배우자는 그 고유의 상속분에 5할을 가산한다.\n"
        "• 민법 제1008조: 공동상속인 중에 피상속인으로부터 재산의 증여 또는 유증을 받은 자가 있는 경우에 그 수증재산이 자기의 상속분에 달하지 못한 때에는 그 부족한 부분의 한도에서 상속분이 있다.\n"
        "• 민법 제1008조의2 제1항: 공동상속인 중에 상당한 기간 동거·간호 그 밖의 방법으로 피상속인을 특별히 부양하거나 피상속인의 재산의 유지 또는 증가에 특별히 기여한 자가 있을 때에는 상속개시 당시의 피상속인의 재산가액에서 공동상속인의 협의로 정한 기여분을 공제한 것을 상속재산으로 보고 그 기여자의 상속분에 기여분을 가산한다.\n"
        "• 민법 제1019조 제1항: 상속인은 상속개시있음을 안 날로부터 3월 내에 단순승인이나 한정승인 또는 포기를 할 수 있다.\n"
        "• 민법 제1042조: 상속의 포기는 상속개시된 때에 소급하여 그 효력이 있다.\n"
        "• 민법 제1112조: 상속인의 유류분은 다음 각호에 의한다. 1. 피상속인의 직계비속은 그 법정상속분의 2분의 1 2. 피상속인의 배우자는 그 법정상속분의 2분의 1 3. 피상속인의 직계존속은 그 법정상속분의 3분의 1 4. 피상속인의 형제자매는 그 법정상속분의 3분의 1.\n"
        "• 민법 제1113조 제1항: 유류분은 피상속인의 상속개시시에 있어서의 재산의 가액에 증여재산의 가액을 가산하고 채무의 전액을 공제하여 이를 산정한다.\n"
        "• 민법 제1115조 제1항: 유류분권리자가 피상속인의 증여 및 유증으로 인하여 그 유류분에 부족이 생긴 때에는 부족한 한도에서 그 재산의 반환을 청구할 수 있다.\n"
        "• 민법 제1026조: 다음 각호의 사유가 있는 경우에는 상속인이 단순승인을 한 것으로 본다. 1. 상속인이 상속재산에 대한 처분행위를 한 때 2. 제1019조 제1항의 기간 내에 한정승인 또는 포기를 하지 아니한 때."
    ),
}


def _get_leader_law_boost(leader_id: str) -> str:
    """리더별 핵심 법률 텍스트 반환 (RAG 컨텍스트 보강용)"""
    return _LEADER_LAW_BOOST.get(leader_id, "")


def _build_leader_persona(leader_id: str) -> str:
    """리더 프로필에서 핵심 인격·철학 텍스트 생성"""
    profiles = _load_leader_profiles()
    p = profiles.get(leader_id)
    if not p:
        return ""
    parts = []
    if p.get("hero"):
        parts.append(f"신조: {p['hero']}")
    identity = p.get("identity", {})
    if identity.get("what"):
        parts.append(f"역할: {identity['what']}")
    if identity.get("why"):
        parts.append(f"사명: {identity['why']}")
    solve = p.get("whatWeSolve", {})
    if solve.get("approach"):
        parts.append(f"접근방식: {solve['approach']}")
    if p.get("philosophy"):
        parts.append(f"철학: {p['philosophy']}")
    if not parts:
        return ""
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Setters
# ---------------------------------------------------------------------------

def set_runtime(runtime: Dict[str, Any]) -> None:
    """main.py의 RUNTIME 딕셔너리를 파이프라인 모듈에 주입."""
    global _RUNTIME
    _RUNTIME = runtime


def set_law_cache(
    law_cache: Dict[str, Any],
    build_cache_context_fn=None,
    match_ssot_sources_fn=None,
    build_ssot_context_fn=None,
) -> None:
    """main.py의 LAW_CACHE 딕셔너리와 관련 함수들을 주입."""
    global _LAW_CACHE, _build_cache_context_fn, _match_ssot_sources_fn, _build_ssot_context_fn
    _LAW_CACHE = law_cache
    _build_cache_context_fn = build_cache_context_fn
    _match_ssot_sources_fn = match_ssot_sources_fn
    _build_ssot_context_fn = build_ssot_context_fn


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# =============================================================
# 데이터 구조체
# =============================================================

@dataclass
class RAGContext:
    """Stage 1 결과: RAG 조문 검색 결과"""
    articles: List[Dict] = field(default_factory=list)       # RAG API 결과
    matched_laws: List[Dict] = field(default_factory=list)   # law_cache 매칭 결과
    context_text: str = ""                                    # 프롬프트 주입용 포맷팅 텍스트
    cache_context: str = ""                                   # 기존 build_cache_context 결과


@dataclass
class VerificationResult:
    """Stage 3 결과: DRF 전수 검증 결과"""
    verified_refs: List[Dict] = field(default_factory=list)
    unverified_refs: List[Dict] = field(default_factory=list)
    all_passed: bool = True
    total_refs: int = 0
    drf_failed: bool = False  # DRF 자체 오류 발생 여부



# =============================================================
# Stage 1: RAG 조문 검색
# =============================================================

async def _stage1_rag_search(query: str, top_k: int = 10) -> RAGContext:
    """Stage 1: RAG 서비스 + law_cache 키워드 매칭으로 관련 조문 검색"""
    ctx = RAGContext()

    # 1a. LawmadiLM RAG API 호출 (설정된 경우)
    rag_url = LAWMADILM_RAG_URL
    if rag_url:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{rag_url}/search",
                    params={"query": query, "top_k": top_k},
                )
                resp.raise_for_status()
                results = resp.json().get("results", [])
                ctx.articles = results
                logger.info(f"[Stage 1] RAG API: {len(results)}건 조문 검색 완료")
        except Exception as e:
            logger.warning(f"[Stage 1] RAG API 실패 (law_cache 폴백): {e}")

    # 1b. law_cache 키워드 매칭 (로컬, 즉시)
    if _match_ssot_sources_fn:
        try:
            cache_matches = _match_ssot_sources_fn(query, top_k=8)
            ctx.matched_laws = cache_matches or []
        except Exception as e:
            logger.warning(f"[Stage 1] law_cache 매칭 실패: {e}")

    # 1c. SSOT 컨텍스트 텍스트 생성 (조문 원문 포함)
    if _build_ssot_context_fn:
        try:
            ctx.context_text = _build_ssot_context_fn(query)
        except Exception:
            ctx.context_text = ""

    # 1d. 기존 build_cache_context (요약 버전)
    if _build_cache_context_fn:
        try:
            ctx.cache_context = _build_cache_context_fn(query)
        except Exception:
            ctx.cache_context = ""

    # RAG API 결과를 텍스트로 포맷팅하여 context_text에 추가
    if ctx.articles:
        rag_text_lines = ["\n[RAG 검색 결과 조문]"]
        for art in ctx.articles[:10]:
            law_name = art.get("law_name", art.get("법령명", ""))
            article_no = art.get("article_no", art.get("조문번호", ""))
            article_title = art.get("article_title", art.get("조문제목", ""))
            text = art.get("text", art.get("조문내용", ""))
            score = art.get("score", 0)
            if law_name and text:
                header = f"■ {law_name}"
                if article_no:
                    header += f" 제{article_no}조"
                if article_title:
                    header += f" ({article_title})"
                if score:
                    header += f" [관련도: {score:.2f}]"
                rag_text_lines.append(header)
                rag_text_lines.append(f"  {text[:500]}")
        ctx.context_text = "\n".join(rag_text_lines) + "\n" + ctx.context_text

    total = len(ctx.articles) + len(ctx.matched_laws)
    logger.info(f"[Stage 1] RAG 완료: RAG API {len(ctx.articles)}건 + law_cache {len(ctx.matched_laws)}건 = {total}건")
    return ctx


# =============================================================
# Stage 2: LawmadiLM 주력 답변 생성
# =============================================================

async def _call_lawmadilm(
    query: str,
    analysis: Dict,
    rag_context: RAGContext,
    drf_verification: Optional[VerificationResult] = None,
    lang: str = "",
    mode: str = "general",
) -> str:
    """Stage 2: LawmadiLM 핵심 법률 초안 (5-6초 내 완료, 150토큰)"""
    leader_name = analysis.get("leader_name", "마디")
    leader_specialty = analysis.get("leader_specialty", "통합")
    leader_id = analysis.get("leader_id", "")

    # RAG 컨텍스트 텍스트 준비
    rag_text = ""
    if rag_context.context_text:
        rag_text = rag_context.context_text[:4000]
    elif rag_context.cache_context:
        rag_text = rag_context.cache_context[:2000]

    # 리더 인격·철학 텍스트
    persona_text = _build_leader_persona(leader_id)

    # 5단계 프레임워크 강화 프롬프트 생성
    system_prompt = build_lawmadilm_prompt(
        leader_name=leader_name,
        leader_specialty=leader_specialty,
        rag_context=rag_text,
        drf_verification=drf_verification,
        lang=lang,
        mode=mode,
        leader_persona=persona_text,
    )

    max_tokens = 100 if mode == "expert" else 60  # 5초 내 완성 목표 (네트워크 지연 포함)

    payload = {
        "messages": [{"role": "user", "content": query}],
        "system_prompt": system_prompt,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(f"{LAWMADILM_API_URL}/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()

    content = data.get("answer", "")
    elapsed = data.get("usage", {}).get("elapsed_seconds", 0)
    tokens = data.get("usage", {}).get("completion_tokens", 0)
    logger.info(f"[Stage 2] LawmadiLM 강화 답변 완료 ({elapsed}s, {tokens} tokens, {len(content)}자)")
    return content


def _postprocess_lawmadilm(draft: str, query: str) -> Optional[str]:
    """LawmadiLM 답변 후처리: 품질 미달 시 None -> Gemini 전담"""
    if not draft or len(draft.strip()) < 30:
        return None

    # <think> 태그 제거
    draft = _remove_think_blocks(draft)

    # 반복 50% 이상 감지
    sentences = [s.strip() for s in re.split(r'[.\u3002\n]', draft) if s.strip()]
    if sentences:
        unique = set(sentences)
        if len(unique) / len(sentences) < 0.5:
            logger.warning(f"[Stage 2 PP] 반복 감지 ({len(unique)}/{len(sentences)}) -> None")
            return None

    return draft.strip()


# =============================================================
# Stage 3: DRF 실시간 전수 검증
# =============================================================

def _extract_articles_from_drf(raw_response) -> List[Dict]:
    """DRF lawService.do 응답에서 조문 목록을 추출

    lawService.do 응답 구조: {"법령": {"조문": {"조문단위": [...]}}}
    각 조문단위: {"조문번호": "3", "조문내용": "제3조(대항력) ...", ...}
    """
    if not raw_response:
        return []

    articles = []
    try:
        if isinstance(raw_response, dict):
            # lawService.do 응답: {"법령": {"조문": {"조문단위": [...]}}}
            law_root = raw_response.get("법령", raw_response)
            if isinstance(law_root, dict):
                jo_section = law_root.get("조문", {})
                if isinstance(jo_section, dict):
                    jo_list = jo_section.get("조문단위", [])
                    if isinstance(jo_list, dict):
                        jo_list = [jo_list]
                    if isinstance(jo_list, list):
                        articles.extend(jo_list)

            # Fallback: LawSearch 응답 구조 (하위 호환)
            if not articles:
                law_data = raw_response.get("LawSearch", {})
                if isinstance(law_data, dict):
                    law_list = law_data.get("law", [])
                    if isinstance(law_list, dict):
                        law_list = [law_list]
                    if isinstance(law_list, list):
                        for law in law_list:
                            jo_list = law.get("조문", [])
                            if isinstance(jo_list, dict):
                                jo_list = [jo_list]
                            for jo in jo_list:
                                if isinstance(jo, dict):
                                    articles.append(jo)

            # 직접 리스트 형식
            if not articles:
                for key in ["law", "조문", "조문목록"]:
                    items = raw_response.get(key, [])
                    if isinstance(items, list):
                        articles.extend(items)
                    elif isinstance(items, dict):
                        articles.append(items)

        elif isinstance(raw_response, list):
            articles = raw_response

    except Exception as e:
        logger.debug(f"[DRF Parse] 조문 추출 실패: {e}")

    return articles


def _get_article_text(articles: List[Dict], article_num: int) -> Optional[str]:
    """조문 목록에서 특정 조문번호의 텍스트를 반환"""
    for art in articles:
        try:
            num = art.get("조문번호", "")
            if isinstance(num, str):
                num = int(num.strip()) if num.strip().isdigit() else None
            if num == article_num:
                content = art.get("조문내용", "") or art.get("조문", "") or art.get("content", "")
                title = art.get("조문제목", "") or art.get("제목", "")
                if content:
                    return f"제{article_num}조({title}) {content}" if title else f"제{article_num}조 {content}"
        except (ValueError, TypeError):
            continue
    return None


async def _drf_verify_law_refs(text: str) -> VerificationResult:
    """Stage 3: 응답에서 인용된 모든 법률 참조를 DRF API로 전수 검증 (조문번호까지 확인).
    비동기 메서드 사용 가능 시 httpx로 직접 호출, 없으면 동기 fallback.
    """
    result = VerificationResult()

    # 법률 참조 추출: "OO법 제X조" 또는 "OO법 제X조 제Y항"
    refs = re.findall(
        r'([가-힣]+(?:법|시행령|시행규칙|규정|조례))\s*제(\d+)조(?:\s*제(\d+)항)?',
        text
    )
    if not refs:
        result.all_passed = True
        return result

    svc = _RUNTIME.get("search_service")
    if not svc:
        logger.warning("[Stage 3] SearchService 없음 -> 검증 스킵")
        result.all_passed = True
        return result

    seen = set()
    # 법령별로 lawService.do 호출 캐시 (조문 상세 포함)
    law_articles_cache: Dict[str, Any] = {}

    for law_name, article_num_str, paragraph_str in refs:
        article_num = int(article_num_str)
        key = f"{law_name} 제{article_num}조"
        if key in seen:
            continue
        seen.add(key)

        try:
            # lawService.do로 조문 상세 조회 (법령별 1회만 호출)
            if law_name not in law_articles_cache:
                if hasattr(svc, "get_law_articles_async"):
                    raw = await svc.get_law_articles_async(law_name)
                else:
                    raw = svc.get_law_articles(law_name)
                law_articles_cache[law_name] = raw
            else:
                raw = law_articles_cache[law_name]

            law_exists = bool(raw)
            article_exists = False
            article_text = None
            articles = []

            if raw:
                articles = _extract_articles_from_drf(raw)
                if articles:
                    article_exists = any(
                        _match_article_num(a, article_num) for a in articles
                    )
                    article_text = _get_article_text(articles, article_num)

            ref_entry = {
                "ref": key,
                "law_name": law_name,
                "article_num": article_num,
                "law_exists": law_exists,
                "article_exists": article_exists,
                "article_text": article_text,
                "verified": law_exists and article_exists,
            }

            if ref_entry["verified"]:
                result.verified_refs.append(ref_entry)
                logger.info(f"[Stage 3] ✅ {key}: 검증 통과")
            else:
                reason = "법령 미존재" if not law_exists else f"제{article_num}조 미존재"
                ref_entry["reason"] = reason
                result.unverified_refs.append(ref_entry)
                logger.warning(f"[Stage 3] ❌ {key}: {reason} (law_exists={law_exists}, articles={len(articles) if raw and articles else 0})")

        except Exception as e:
            logger.warning(f"[Stage 3] {key} 검증 실패: {e}")
            result.unverified_refs.append({
                "ref": key,
                "law_name": law_name,
                "article_num": article_num,
                "law_exists": False,
                "article_exists": False,
                "article_text": None,
                "verified": False,
                "reason": f"검증 오류: {type(e).__name__}",
            })

    # ── 판례 검증: "대법원 YYYY다NNNNN" 등 판례번호 추출 + DRF 검증 ──
    prec_refs = re.findall(
        r'((?:대법원|대법|헌법재판소|헌재|서울고등법원|서울고법|서울중앙지방법원)\s*'
        r'(\d{4})\s*[.]\s*(\d{1,2})\s*[.]\s*\d{1,2}\s*[.]?\s*선고\s*'
        r'(\d{2,4}[가-힣]+\d+)\s*(?:판결|결정))',
        text
    )
    # 더 간단한 패턴: "2020다12345", "2012헌바55", "2019헌마439" 등
    if not prec_refs:
        prec_refs_simple = re.findall(
            r'(\d{2,4}'
            r'(?:헌바|헌마|헌가|헌나|헌라|헌사|헌아|헌자|'  # 헌재결정례
            r'다|나|가|마|카|타|파|라|바|사|아|자|차|하|'    # 대법원 판례
            r'두|누|구|무|부|수|우|주|추|후|그|드|스|으)'
            r'(?:합)?\d{2,6})',
            text
        )
    else:
        prec_refs_simple = [p[3] for p in prec_refs]  # 사건번호만 추출

    if prec_refs_simple:
        drf_inst = _RUNTIME.get("drf")
        prec_seen = set()
        for case_no in prec_refs_simple:
            case_no = case_no.strip()
            if case_no in prec_seen or len(case_no) < 5:
                continue
            prec_seen.add(case_no)
            try:
                if drf_inst and hasattr(drf_inst, "search_precedents_async"):
                    raw_prec = await drf_inst.search_precedents_async(case_no)
                    prec_exists = bool(raw_prec)
                elif drf_inst and hasattr(drf_inst, "search_precedents"):
                    raw_prec = drf_inst.search_precedents(case_no)
                    prec_exists = bool(raw_prec)
                else:
                    prec_exists = False
                    logger.debug(f"[Stage 4] 판례 DRF 미사용 (drf 인스턴스 없음)")

                ref_entry = {
                    "ref": f"판례 {case_no}",
                    "type": "precedent",
                    "case_no": case_no,
                    "verified": prec_exists,
                }
                if prec_exists:
                    result.verified_refs.append(ref_entry)
                else:
                    ref_entry["reason"] = "판례 미존재"
                    result.unverified_refs.append(ref_entry)
            except Exception as e:
                logger.warning(f"[Stage 4] 판례 {case_no} 검증 실패: {e}")
                result.unverified_refs.append({
                    "ref": f"판례 {case_no}",
                    "type": "precedent",
                    "case_no": case_no,
                    "verified": False,
                    "reason": f"검증 오류: {type(e).__name__}",
                })

    result.total_refs = len(result.verified_refs) + len(result.unverified_refs)
    result.all_passed = len(result.unverified_refs) == 0

    law_count = sum(1 for r in result.verified_refs if r.get("type") != "precedent")
    prec_count = sum(1 for r in result.verified_refs if r.get("type") == "precedent")
    law_fail = sum(1 for r in result.unverified_refs if r.get("type") != "precedent")
    prec_fail = sum(1 for r in result.unverified_refs if r.get("type") == "precedent")

    logger.info(
        f"[Stage 4] DRF 전수 검증 완료: "
        f"총 {result.total_refs}건 (법률 {law_count+law_fail}건, 판례 {prec_count+prec_fail}건) | "
        f"통과 {len(result.verified_refs)}건, "
        f"실패 {len(result.unverified_refs)}건"
    )

    return result


def _match_article_num(article_dict: Dict, target_num: int) -> bool:
    """조문 딕셔너리에서 조문번호가 target_num과 일치하는지 확인"""
    try:
        num = article_dict.get("조문번호", "")
        if isinstance(num, (int, float)):
            return int(num) == target_num
        if isinstance(num, str):
            cleaned = num.strip().replace("조", "")
            if cleaned.isdigit():
                return int(cleaned) == target_num
    except (ValueError, TypeError):
        pass
    return False


# =============================================================
# FAIL_CLOSED 및 미검증 조문 제거
# =============================================================

def _remove_unverified_refs(text: str, drf_verification: VerificationResult) -> str:
    """미검증 조문 참조를 텍스트에서 제거하거나 경고 태깅"""
    for ref_info in drf_verification.unverified_refs:
        ref = ref_info.get("ref", "")
        if ref in text:
            reason = ref_info.get("reason", "미확인")
            text = text.replace(ref, f"{ref}(※ {reason})")
    return text


def _strip_unverified_sentences(text: str, drf_verification: VerificationResult) -> str:
    """미검증 조문이 포함된 문장을 텍스트에서 완전 삭제"""
    lines = text.split("\n")
    bad_refs = [r.get("ref", "") for r in drf_verification.unverified_refs if r.get("ref")]
    cleaned = []
    for line in lines:
        if any(ref in line for ref in bad_refs):
            logger.debug(f"[STRIP] 미검증 조문 포함 문장 삭제: {line[:60]}...")
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _apply_fail_closed(final_text: str, drf_verification: VerificationResult) -> str:
    """FAIL_CLOSED 로직: 0.1% 초과 미검증 시 응답 차단, DRF 자체 오류 시에도 차단"""

    # ── 안전장치 1: DRF 검증 시스템 자체 오류 → FAIL_CLOSED ──
    if drf_verification.drf_failed:
        logger.warning("[FAIL_CLOSED] DRF 검증 시스템 오류 → 응답 차단")
        return FAIL_CLOSED_RESPONSE

    # 법률 조문 참조가 없는 응답 → 통과 (일반 상담/설명)
    if drf_verification.total_refs == 0:
        return final_text

    unverified_count = len(drf_verification.unverified_refs)
    total_count = drf_verification.total_refs
    ratio = unverified_count / max(total_count, 1)

    # ── 안전장치 2: 미검증 비율 0.1% 초과 → 응답 차단 (fail-closed 0.1%) ──
    if ratio > 0.001:
        logger.warning(
            f"[FAIL_CLOSED] 미검증 {unverified_count}/{total_count} "
            f"({ratio*100:.1f}%) > 0.1% → 응답 차단"
        )
        return FAIL_CLOSED_RESPONSE

    # ── 안전장치 3: 미검증 → 해당 조문 완전 삭제 (태깅 아님) ──
    if unverified_count > 0:
        final_text = _strip_unverified_sentences(final_text, drf_verification)
        logger.info(
            f"[SAFE] 미검증 {unverified_count}건 조문 문장 삭제 "
            f"({ratio*100:.1f}%)"
        )

    return final_text


# =============================================================
# Gemini Fallback: LawmadiLM 실패 시 Gemini Flash로 답변 생성
# =============================================================

async def _gemini_fallback_compose(
    query: str,
    analysis: Dict,
    rag_context: RAGContext,
    tools: list,
    gemini_history: list,
    now_kst: str,
    ssot_available: bool,
    lang: str = "",
    mode: str = "general",
    lm_draft: str = "",
) -> str:
    """Gemini Flash 완성 답변 생성 (LM 초안 기반 또는 단독, 캐시 컨텍스트 최대 활용)"""
    gc = _RUNTIME.get("genai_client")
    if not gc:
        raise RuntimeError("Gemini 클라이언트 미초기화")

    model_name = GEMINI_MODEL
    leader_name = analysis.get("leader_name", "마디")
    leader_specialty = analysis.get("leader_specialty", "통합")

    # LM 초안 주입
    draft_section = ""
    if lm_draft:
        draft_section = (
            f"\n\n[LawmadiLM 법률 초안]\n{lm_draft}\n\n"
            f"위 초안의 법률 근거(조문, 판례)를 바탕으로 완성된 답변을 작성하세요.\n"
            f"초안의 법령명+조문번호를 반드시 포함하세요."
        )

    # RAG/캐시 컨텍스트 주입 (SSOT 캐시 최우선 참조)
    ctx_section = ""
    if rag_context.context_text:
        ctx_section = (
            "\n\n[SSOT 캐시 — 반드시 최우선 참조]\n"
            "아래 SSOT 캐시 데이터는 DRF API에서 사전 검증된 법률 정보입니다.\n"
            "답변 시 반드시 이 캐시의 법령명·조문번호·판례번호를 그대로 인용하세요.\n"
            "캐시에 없는 법령이나 판례를 임의 생성하지 마세요.\n"
            f"{rag_context.context_text[:100000]}"
        )
    elif rag_context.cache_context:
        ctx_section = (
            "\n\n[SSOT 캐시 — 반드시 최우선 참조]\n"
            "아래 캐시 데이터의 법령명·조문번호·판례번호를 그대로 인용하세요.\n"
            f"{rag_context.cache_context[:50000]}"
        )

    # 모드별 보강 지시
    if mode == "expert":
        enhance = (
            "\n\n[구조 지시] 사안의 쟁점 → 관련 법령 → 판례 검토 → 실무 대응 절차 → 쟁점별 검토 의견 → 결론 및 권고 → 법률 근거"
            "\n핵심 쟁점, 법률명, 판례번호는 **굵은 글씨**로 표시. 4,000~5,000자."
        )
        max_tokens = 5000
    else:
        enhance = (
            "\n\n[구조 지시] 결론부터 말씀드리면 → 왜 그런가요? → 지금 바로 하실 수 있는 일 → 그래도 해결이 안 되면 → 혼자 하기 어려우시면 → 지금 해야 할 행동 3가지 → 법률 근거"
            "\n한 문장은 50~60자 이내. 2,000~3,000자."
        )
        max_tokens = 3500

    lang_instruction = ""
    if lang == "en":
        lang_instruction = "\n\nIMPORTANT: Respond entirely in English. Translate Korean legal terms with the original Korean in parentheses."

    # 리더 인격·철학 주입
    leader_id = analysis.get("leader_id", "")
    persona_section = ""
    persona_text = _build_leader_persona(leader_id)
    if persona_text:
        persona_section = f"\n\n[리더 인격]\n{persona_text}"

    instruction = (
        f"{build_system_instruction(mode)}\n"
        f"현재 당신은 '{leader_name}' 리더입니다.\n"
        f"전문 분야: {leader_specialty}"
        f"{persona_section}\n"
        f"질문 요약: {analysis.get('summary', '')}"
        f"{draft_section}"
        f"{ctx_section}"
        f"{enhance}"
        f"{lang_instruction}"
    )

    gen_config = genai_types.GenerateContentConfig(
        tools=tools,
        system_instruction=instruction,
        max_output_tokens=max_tokens,
        automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=False),
    )

    chat = gc.chats.create(
        model=model_name,
        config=gen_config,
        history=gemini_history,
    )
    resp = chat.send_message(
        f"now_kst={now_kst}\nssot_available={ssot_available}\n사용자 질문: {query}"
    )
    text = _safe_extract_gemini_text(resp)
    logger.info(f"[Gemini Fallback] 답변 생성 완료 ({len(text)}자, mode={mode})")
    return text


# =============================================================
# Main Pipeline Orchestrator (3-Stage, LawmadiLM + Gemini Fallback)
# =============================================================

async def _run_legal_pipeline(
    query: str,
    analysis: Dict,
    tools: list,
    gemini_history: list,
    now_kst: str,
    ssot_available: bool,
    lang: str = "",
    mode: str = "general",
    rag_context: Optional[RAGContext] = None,
) -> str:
    """4-Stage Hybrid Legal Pipeline (LM 5초 초안 → Gemini 완성):
    Stage 1: RAG 조문 검색
    Stage 2: LawmadiLM 초안 (5초 타임아웃)
    Stage 3: Gemini Flash 완성 답변 (LM 초안 기반 또는 단독)
    Stage 4: DRF 실시간 전수 검증
    → Fail-Closed → 응답

    LawmadiLM 실패/타임아웃 시 Gemini가 단독 작성 (fallback).
    rag_context가 전달되면 Stage 1을 건너뛰어 S0+S1 병렬화를 지원.
    """
    final_text = ""
    drf_verification = VerificationResult()

    # -- Stage 1: RAG 조문 검색 (1회만 수행, 외부 전달 시 스킵) --
    if rag_context is None:
        logger.info("[Stage 1/4] RAG 조문 검색 시작")
        try:
            rag_context = await _stage1_rag_search(query)
        except Exception as e:
            logger.warning(f"[Stage 1] RAG 검색 실패 (빈 컨텍스트 진행): {e}")
            rag_context = RAGContext()
    else:
        logger.info("[Stage 1/4] RAG 컨텍스트 외부 전달 (S0+S1 병렬화)")

    # -- Stage 1.5: 리더별 핵심 법률 RAG 컨텍스트 보강 --
    leader_id = analysis.get("leader_id", "")
    _leader_law_boost = _get_leader_law_boost(leader_id)
    if _leader_law_boost:
        boost_text = (
            f"\n\n[리더 핵심 참조 법률 - 반드시 이 법률만 우선 인용하세요]\n"
            f"⚠️ 아래 목록에 없는 법률 조문은 인용하지 마세요. DRF 검증에서 실패할 수 있습니다.\n"
            f"{_leader_law_boost}"
        )
        if rag_context.context_text:
            rag_context.context_text = boost_text + "\n" + rag_context.context_text
        elif rag_context.cache_context:
            rag_context.cache_context = boost_text + "\n" + rag_context.cache_context
        else:
            rag_context.context_text = boost_text
        logger.info(f"[Stage 1.5] 리더 {leader_id} 핵심 법률 RAG 주입")

    # -- Stage 2: LawmadiLM 초안 (5초 타임아웃) --
    lm_draft = ""
    try:
        logger.info("[Stage 2/4] LawmadiLM 초안 생성 (5초)")
        raw_answer = await _call_lawmadilm(
            query, analysis, rag_context, lang=lang, mode=mode,
        )
        lm_draft = _postprocess_lawmadilm(raw_answer, query)
        if lm_draft:
            logger.info(f"[Stage 2] LM 초안 완료 ({len(lm_draft)}자)")
        else:
            logger.warning("[Stage 2] 후처리 -> None (품질 미달)")
            lm_draft = ""
    except Exception as e:
        logger.warning(f"[Stage 2] LawmadiLM 실패/타임아웃: {e} -> Gemini 단독")
        lm_draft = ""

    # -- Stage 3: Gemini Flash 완성 답변 (LM 초안 기반 또는 단독) --
    logger.info(f"[Stage 3/4] Gemini Flash 답변 (LM초안={'있음' if lm_draft else '없음'})")
    try:
        final_text = await _gemini_fallback_compose(
            query, analysis, rag_context, tools, gemini_history,
            now_kst, ssot_available, lang=lang, mode=mode,
            lm_draft=lm_draft,
        )
    except Exception as e:
        logger.error(f"[Stage 3] Gemini 답변 생성 실패: {e}")
        if lm_draft:
            final_text = lm_draft
        else:
            raise RuntimeError("LawmadiLM + Gemini 모두 답변 생성 실패")

    # 빈 응답 안전장치: Gemini가 빈 텍스트 반환 시 재시도 1회
    if not final_text or len(final_text.strip()) < 30:
        logger.warning(f"[Stage 3] Gemini 빈 응답 감지 ({len(final_text)}자) — 재시도")
        try:
            final_text = await _gemini_fallback_compose(
                query, analysis, rag_context, tools, gemini_history,
                now_kst, ssot_available, lang=lang, mode=mode,
                lm_draft=lm_draft,
            )
        except Exception as e:
            logger.error(f"[Stage 3 재시도] 실패: {e}")
        if not final_text or len(final_text.strip()) < 30:
            raise RuntimeError("Gemini 빈 응답 (재시도 포함)")

    # -- Stage 3.5: 최소 응답 길이 검증 (법률 응답) --
    is_legal = analysis.get("is_legal", True)
    min_len = MIN_LEGAL_RESPONSE_EXPERT if mode == "expert" else MIN_LEGAL_RESPONSE_GENERAL
    if is_legal and len(final_text.strip()) < min_len:
        logger.warning(
            f"[Stage 3.5] 법률 응답 길이 부족 ({len(final_text)}자 < {min_len}자, mode={mode}) — 재생성"
        )
        try:
            retry_text = await _gemini_fallback_compose(
                query, analysis, rag_context, tools, gemini_history,
                now_kst, ssot_available, lang=lang, mode=mode,
                lm_draft=lm_draft,
            )
            if retry_text and len(retry_text.strip()) >= min_len:
                final_text = retry_text
                logger.info(f"[Stage 3.5] 재생성 성공 ({len(final_text)}자)")
            else:
                logger.warning(f"[Stage 3.5] 재생성도 길이 부족 ({len(retry_text) if retry_text else 0}자)")
        except Exception as e:
            logger.warning(f"[Stage 3.5] 재생성 실패: {e}")

    # -- Stage 4: DRF 실시간 전수 검증 --
    logger.info("[Stage 4/4] DRF 전수 검증")
    try:
        drf_verification = await _drf_verify_law_refs(final_text)
    except Exception as e:
        logger.error(f"[Stage 4] DRF 검증 시스템 오류 → FAIL_CLOSED: {e}")
        drf_verification = VerificationResult(drf_failed=True)

    # FAIL_CLOSED 적용 (0.1% 초과 미검증 또는 DRF 오류 시 차단)
    fail_closed_result = _apply_fail_closed(final_text, drf_verification)

    # -- FAIL_CLOSED 재시도: 차단 시 1회 재생성 후 재검증 --
    if fail_closed_result == FAIL_CLOSED_RESPONSE:
        logger.warning("[FAIL_CLOSED 재시도] 1회 재생성 시도")
        # 미검증 법률 목록을 금지 목록으로 주입
        banned_laws = [r["ref"] for r in drf_verification.unverified_refs]
        if banned_laws:
            ban_text = ", ".join(banned_laws)
            ban_instruction = (
                f"\n\n⚠️ 아래 법률은 DRF 검증에서 미확인되었으므로 절대 인용하지 마세요: {ban_text}\n"
                f"반드시 [참고 법령 조문] 또는 [SSOT 캐시]에 있는 법률만 인용하세요."
            )
            # lm_draft에 금지 목록 추가
            if lm_draft:
                lm_draft = lm_draft + ban_instruction
            else:
                lm_draft = ban_instruction
        try:
            retry_text = await _gemini_fallback_compose(
                query, analysis, rag_context, tools, gemini_history,
                now_kst, ssot_available, lang=lang, mode=mode,
                lm_draft=lm_draft,
            )
            if retry_text and len(retry_text.strip()) >= 30:
                retry_drf = await _drf_verify_law_refs(retry_text)
                retry_result = _apply_fail_closed(retry_text, retry_drf)
                if retry_result != FAIL_CLOSED_RESPONSE:
                    logger.info("[FAIL_CLOSED 재시도] 재생성 + 재검증 통과")
                    return retry_result, retry_drf
                else:
                    # -- 최후 수단: 미검증 문장만 제거 후 남은 텍스트 반환 --
                    stripped = _strip_unverified_sentences(retry_text, retry_drf)
                    stripped = stripped.strip()
                    if len(stripped) >= 300:
                        disclaimer = (
                            "\n\n---\n"
                            "※ 이 답변의 일부 법률 조문은 실시간 검증에서 확인되지 않아 제거되었습니다. "
                            "정확한 조문은 [국가법령정보센터](https://law.go.kr)에서 확인해 주세요."
                        )
                        logger.info(
                            f"[FAIL_CLOSED 재시도] 미검증 문장 제거 후 반환 "
                            f"({len(stripped)}자, 제거 {len(retry_drf.unverified_refs)}건)"
                        )
                        return stripped + disclaimer, retry_drf
                    else:
                        logger.warning(
                            f"[FAIL_CLOSED 재시도] 미검증 제거 후 텍스트 부족 "
                            f"({len(stripped)}자 < 300자) → FAIL_CLOSED 유지"
                        )
            else:
                logger.warning("[FAIL_CLOSED 재시도] 재생성 실패 (빈 응답)")
        except Exception as e:
            logger.warning(f"[FAIL_CLOSED 재시도] 오류: {e}")

        return fail_closed_result, drf_verification

    return fail_closed_result, drf_verification


# =============================================================
# Streaming 지원 함수들 (routes/legal.py에서 호출)
# =============================================================

async def run_pipeline_stage1(query: str) -> RAGContext:
    """스트리밍용: Stage 1만 실행"""
    try:
        return await _stage1_rag_search(query)
    except Exception as e:
        logger.warning(f"[Stream Stage 1] RAG 실패: {e}")
        return RAGContext()


async def run_pipeline_stage2(
    query: str,
    analysis: Dict,
    rag_context: RAGContext,
    drf_verification: Optional[VerificationResult] = None,
    lang: str = "",
    mode: str = "general",
) -> str:
    """스트리밍용: Stage 2만 실행 (강화 프롬프트)"""
    try:
        raw = await _call_lawmadilm(
            query, analysis, rag_context,
            drf_verification=drf_verification,
            lang=lang,
            mode=mode,
        )
        return _postprocess_lawmadilm(raw, query) or ""
    except Exception as e:
        logger.warning(f"[Stream Stage 2] LawmadiLM 실패: {e}")
        return ""


async def run_pipeline_stage3(text: str) -> VerificationResult:
    """스트리밍용: Stage 3만 실행"""
    if not text:
        return VerificationResult()
    try:
        return await _drf_verify_law_refs(text)
    except Exception as e:
        logger.error(f"[Stream Stage 3] DRF 검증 시스템 오류 → FAIL_CLOSED: {e}")
        return VerificationResult(drf_failed=True)


# Public alias for external use
run_legal_pipeline = _run_legal_pipeline
# Option B: gemini-2.5-flash + law_cache direct injection (no CachedContent)
