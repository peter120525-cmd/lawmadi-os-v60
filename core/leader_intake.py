"""
리더 1:1 채팅 인테이크 시스템.

리더가 사용자 질문을 분석하여:
1. 분야 불일치 → 적절한 리더 추천
2. 정보 부족 → 전문분야별 추가 질문
3. 정보 충분 → 정리된 법률 질문 프롬프트 생성

사용법:
    from core.leader_intake import run_leader_triage
    result = await run_leader_triage(gc, query, history, leader_info, lang)
"""
import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from core.model_fallback import get_model

logger = logging.getLogger("LawmadiOS.LeaderIntake")

# ─── 전문분야별 필수 정보 (리더가 질문할 항목) ───
_DOMAIN_INTAKE = {
    "민사법": ["분쟁 유형(계약/채권/손해배상)", "상대방과의 관계", "분쟁 금액", "계약서 유무", "시기(발생일/기한)"],
    "부동산법": ["물건 종류(아파트/토지/상가)", "거래 유형(매매/임대/분양)", "계약 금액", "계약 시기", "등기 상태"],
    "건설법": ["공사 종류", "계약 금액", "하자/지연 내용", "계약서 유무", "당사자 관계(시공사/건축주)"],
    "재개발·재건축": ["사업 단계", "조합원 여부", "분담금/권리가액", "토지/건물 소유 관계"],
    "의료법": ["진료 내용", "피해 유형", "진료 시기", "병원 종류", "진료기록 보유 여부"],
    "손해배상": ["피해 유형(신체/재산/정신)", "가해자 관계", "피해 금액", "사고 시기", "증거 유무"],
    "교통사고": ["사고 유형(차대차/차대사람)", "과실 비율", "부상 정도", "보험 가입 여부", "사고 일시"],
    "임대차": ["물건 종류(주택/상가)", "보증금/월세 금액", "계약 기간", "문제 유형(미반환/해지/수리)", "전입신고 여부"],
    "채권추심": ["채권 종류", "채무 금액", "채무자 상태(연락/도주)", "담보 유무", "소멸시효 여부"],
    "등기·경매": ["물건 종류", "경매 단계", "권리분석 내용", "채권 금액", "배당 순위"],
    "상사법": ["거래 유형", "계약 상대방", "분쟁 내용", "계약 금액", "계약서 유무"],
    "회사법·M&A": ["회사 형태(주식/유한)", "주주 구성", "분쟁 내용(경영권/배당/합병)", "회사 규모"],
    "스타트업": ["사업 단계", "법인 형태", "투자 관련 여부", "주주간계약 유무", "분쟁 유형"],
    "보험": ["보험 종류(생명/손해/자동차)", "사고 내용", "보험금 금액", "청구 상태", "약관 쟁점"],
    "조세·금융": ["세금 종류", "금액", "과세 기간", "이의신청 여부", "사업자 유형"],
    "형사법": ["혐의/범죄 유형", "가해자/피해자 여부", "사건 경위", "수사 단계", "증거 상황"],
    "지식재산권": ["IP 종류(특허/상표/디자인/영업비밀)", "침해 유형", "등록 여부", "상대방 정보"],
    "노동법": ["근로 형태(정규/비정규/일용)", "분쟁 유형(해고/임금/산재)", "재직 기간", "회사 규모", "증거(근로계약서/급여명세)"],
    "행정법": ["처분 내용", "처분 기관", "처분 시기", "불복 여부", "이해관계"],
    "개인정보": ["유출/침해 유형", "개인정보 종류", "피해 규모", "처리자(기업/기관)", "동의 여부"],
    "이혼·가족": ["혼인 기간", "자녀 유무/나이", "분쟁 유형(이혼/양육/재산)", "재산 규모", "유책 사유"],
    "상속·신탁": ["피상속인 관계", "상속재산 종류/규모", "상속인 수", "유언장 유무", "분쟁 여부"],
    "소비자": ["제품/서비스 종류", "피해 내용", "구매 금액", "구매 시기", "판매자 정보"],
    "저작권": ["저작물 종류", "침해 유형(복제/배포/2차창작)", "저작권 등록 여부", "상대방 정보"],
    "산업재해": ["사고 유형", "부상 정도", "근무 기간", "산재 신청 여부", "회사 규모"],
    "다문화·이주": ["체류 자격", "비자 종류", "분쟁 유형(체류/근로/가족)", "체류 기간", "국적"],
    "환경법": ["오염 유형", "피해 내용", "원인 시설", "피해 규모", "신고 여부"],
    "국가계약": ["계약 유형(물품/용역/공사)", "발주기관", "계약 금액", "분쟁 내용(입찰/이행/대금)", "계약서 유무"],
    "민사집행": ["집행 유형(강제/가압류/가처분)", "채권 금액", "집행 대상(부동산/채권/동산)", "판결/공정증서 유무", "채무자 재산 파악"],
    "국제거래": ["거래 유형(수출/수입/투자)", "상대국", "계약 금액", "준거법/중재 조항", "분쟁 내용"],
    "에너지·자원": ["에너지 종류(전기/가스/신재생)", "사업 유형(발전/유통/개발)", "인허가 관련", "분쟁 내용", "관련 법규"],
    "해상·항공": ["운송 유형(해상/항공)", "화물/사고 내용", "보험 가입 여부", "관련 당사자", "분쟁 금액"],
    "IT·보안": ["서비스 유형(SW/플랫폼/보안)", "분쟁 내용(계약/침해/개인정보)", "피해 규모", "계약서 유무", "관련 당사자"],
    "엔터테인먼트": ["분야(음악/영화/방송/공연)", "계약 유형(전속/출연/매니지먼트)", "분쟁 내용", "계약 금액", "계약서 유무"],
    "조세불복": ["세금 종류", "부과 금액", "과세 기간", "불복 단계(이의/심판/소송)", "과세 근거"],
    "군형법": ["혐의 유형", "군인 신분(현역/예비역/군무원)", "사건 경위", "수사/재판 단계", "관련 증거"],
    "무역·관세": ["거래 유형(수출/수입)", "품목", "관세 분쟁 내용", "통관 단계", "금액"],
    "게임·콘텐츠": ["콘텐츠 유형(게임/웹툰/영상)", "분쟁 유형(저작권/계약/이용약관)", "플랫폼", "관련 금액", "계약서 유무"],
    "공정거래": ["위반 유형(담합/시장지배/불공정)", "관련 사업자", "피해 내용", "공정위 조사 여부", "관련 시장"],
    "우주항공": ["사업 유형(발사/위성/드론)", "인허가 관련", "분쟁 내용", "관련 법규", "당사자 관계"],
    "헌법": ["기본권 유형", "침해 주체(국가/기관)", "침해 내용", "구제 수단(헌법소원/위헌심판)", "관련 법률"],
    "문화·종교": ["분쟁 유형(재산/운영/명예)", "단체 종류", "관련 재산/금액", "구성원 관계", "관련 규약"],
    "소년법": ["대상자 나이", "비행/범죄 유형", "수사/재판 단계", "보호자 관계", "학교/시설 관련"],
    "정보통신": ["서비스 유형(통신/인터넷/방송)", "분쟁 내용(요금/해지/장애)", "사업자", "피해 규모", "신고 여부"],
    "인권": ["침해 유형(차별/폭력/노동)", "침해 주체", "피해 내용", "구제 절차(인권위/소송)", "증거 유무"],
    "사회복지": ["복지 유형(기초/장애/노인/아동)", "신청/수급 문제", "관할 기관", "분쟁 내용", "소득/재산 기준"],
    "교육·청소년": ["교육 기관(학교/학원/대학)", "분쟁 유형(징계/폭력/입학/학비)", "당사자 관계", "피해 내용", "관련 증거"],
    "벤처·신산업": ["사업 분야", "법인 형태", "투자/지원 관련", "규제/인허가 쟁점", "분쟁 유형"],
    "문화예술": ["분야(미술/음악/공연/출판)", "분쟁 유형(저작권/계약/기금)", "계약 관계", "관련 금액", "계약서 유무"],
    "식품·보건": ["식품/의약품 유형", "문제 유형(안전/허가/표시)", "피해 내용", "관련 기관", "인허가 상태"],
    "종교·전통": ["단체 유형(사찰/교회/종단)", "분쟁 내용(재산/운영/인사)", "관련 재산", "구성원 관계", "관련 규약"],
    "광고·언론": ["매체 유형(TV/인터넷/인쇄)", "분쟁 유형(허위광고/명예훼손/정정보도)", "피해 내용", "관련 당사자", "증거 유무"],
    "농림·축산": ["분야(농업/축산/임업)", "분쟁 유형(보상/피해/인허가)", "토지/시설 관련", "피해 규모", "관할 기관"],
    "해양·수산": ["분야(어업/양식/해운)", "분쟁 유형(어업권/보상/환경)", "관련 해역/시설", "피해 규모", "인허가 관련"],
    "과학기술": ["기술 분야", "분쟁 유형(특허/연구부정/기술유출)", "관련 기관/기업", "피해 규모", "계약서 유무"],
    "장애인·복지": ["장애 유형/등급", "분쟁 유형(차별/복지/접근성)", "관련 기관", "피해 내용", "구제 절차"],
    "스포츠·레저": ["종목/시설 유형", "분쟁 유형(계약/사고/도핑)", "관련 단체", "피해/금액", "계약서 유무"],
    "데이터·AI윤리": ["기술 유형(AI/빅데이터/알고리즘)", "분쟁 내용(편향/프라이버시/책임)", "관련 서비스", "피해 규모", "관련 법규"],
    "시스템 총괄": ["문의 유형", "관련 서비스", "문제 상세 설명"],
}

# 기본 필수 정보 (매핑 없는 분야용)
_DEFAULT_INTAKE = ["분쟁/문제 유형", "상대방 관계", "관련 금액", "시기", "증거/서류 유무"]


def _get_intake_fields(specialty: str) -> List[str]:
    """전문분야에 맞는 필수 정보 항목 반환."""
    for key, fields in _DOMAIN_INTAKE.items():
        if key in specialty or specialty in key:
            return fields
    return _DEFAULT_INTAKE


# ─── 리더 전문분야 → 분야 키워드 매핑 ───
_SPECIALTY_KEYWORDS = {
    "민사법": ["계약", "채권", "소송", "민사"],
    "부동산법": ["부동산", "토지", "건물", "아파트", "분양", "매매"],
    "건설법": ["건설", "공사", "하자", "시공"],
    "재개발·재건축": ["재개발", "재건축", "조합", "분담금"],
    "의료법": ["의료", "병원", "진료", "의사", "수술", "오진"],
    "손해배상": ["손해", "배상", "피해", "보상"],
    "교통사고": ["교통사고", "자동차", "사고", "과실", "합의금"],
    "임대차": ["임대", "전세", "월세", "보증금", "세입자", "임차", "퇴거"],
    "채권추심": ["채권", "추심", "빚", "대출", "채무"],
    "등기·경매": ["등기", "경매", "배당", "낙찰"],
    "상사법": ["상사", "상거래", "어음", "수표"],
    "회사법·M&A": ["회사", "주주", "이사회", "합병", "인수"],
    "스타트업": ["스타트업", "창업", "투자", "벤처"],
    "보험": ["보험", "보험금", "약관", "보상"],
    "조세·금융": ["세금", "세무", "국세", "종합소득", "양도세", "증여세"],
    "형사법": ["형사", "고소", "고발", "사기", "폭행", "절도", "횡령", "범죄", "수사"],
    "지식재산권": ["특허", "상표", "디자인", "영업비밀", "지적재산"],
    "노동법": ["노동", "해고", "임금", "퇴직금", "근로", "산재"],
    "행정법": ["행정", "허가", "인허가", "처분", "행정소송"],
    "개인정보": ["개인정보", "정보유출", "CCTV", "개인정보보호"],
    "이혼·가족": ["이혼", "양육", "친권", "재산분할", "위자료", "가족"],
    "상속·신탁": ["상속", "유언", "신탁", "유산", "유류분"],
    "소비자": ["소비자", "환불", "교환", "하자", "AS"],
    "저작권": ["저작권", "복제", "표절", "저작물"],
    "산업재해": ["산재", "산업재해", "작업중", "업무상"],
    "다문화·이주": ["비자", "체류", "외국인", "귀화", "이민"],
    "환경법": ["환경", "오염", "폐기물", "소음"],
    "국가계약": ["국가계약", "조달", "입찰", "관급", "발주"],
    "민사집행": ["강제집행", "가압류", "가처분", "경매", "압류"],
    "국제거래": ["국제", "수출", "수입", "해외거래", "중재"],
    "에너지·자원": ["에너지", "전력", "가스", "신재생", "발전"],
    "해상·항공": ["해상", "항공", "선박", "운송", "화물"],
    "IT·보안": ["IT", "해킹", "보안", "소프트웨어", "플랫폼"],
    "엔터테인먼트": ["연예", "매니지먼트", "전속계약", "방송", "기획사"],
    "조세불복": ["조세불복", "세금불복", "이의신청", "심판청구", "조세소송"],
    "군형법": ["군대", "군인", "영창", "군형법", "군사법원"],
    "무역·관세": ["무역", "관세", "통관", "수출입", "FTA"],
    "게임·콘텐츠": ["게임", "웹툰", "콘텐츠", "스트리밍", "BJ"],
    "공정거래": ["공정거래", "독점", "담합", "카르텔", "하도급"],
    "우주항공": ["우주", "드론", "위성", "항공우주"],
    "헌법": ["헌법", "기본권", "위헌", "헌법소원", "헌법재판"],
    "문화·종교": ["종교", "사찰", "교회", "문화재", "종단"],
    "소년법": ["소년", "미성년", "학교폭력", "소년원", "보호처분"],
    "정보통신": ["통신", "인터넷", "방송통신", "전파", "요금"],
    "인권": ["인권", "차별", "혐오", "인권위", "평등"],
    "사회복지": ["복지", "기초수급", "국민연금", "사회보장"],
    "교육·청소년": ["교육", "학교", "학원", "입학", "징계"],
    "벤처·신산업": ["벤처", "신산업", "규제샌드박스", "핀테크"],
    "문화예술": ["미술", "공연", "출판", "예술", "저작"],
    "식품·보건": ["식품", "의약품", "위생", "보건", "식약처"],
    "종교·전통": ["종교", "전통", "사찰", "종단", "문화재"],
    "광고·언론": ["광고", "언론", "보도", "명예훼손", "정정"],
    "농림·축산": ["농업", "축산", "농지", "임업", "축사"],
    "해양·수산": ["수산", "어업", "양식", "해양", "어업권"],
    "과학기술": ["과학", "연구", "기술유출", "연구부정", "R&D"],
    "장애인·복지": ["장애인", "장애등급", "접근성", "활동지원"],
    "스포츠·레저": ["스포츠", "선수", "도핑", "체육", "레저"],
    "데이터·AI윤리": ["AI", "데이터", "알고리즘", "자동화", "인공지능"],
}


def _build_triage_prompt(
    leader_name: str,
    specialty: str,
    persona: Dict[str, str],
    intake_fields: List[str],
    lang: str = "",
) -> str:
    """인테이크 트리아지 시스템 프롬프트 생성."""
    tone = persona.get("tone", "차분한 존댓말")
    personality = persona.get("personality", "전문적이고 따뜻한")
    catchphrase = persona.get("catchphrase", "")

    fields_str = "\n".join(f"  - {f}" for f in intake_fields)

    if lang == "en":
        return f"""You are '{leader_name}', a legal consultation leader specializing in {specialty}.
Personality: {personality}
Tone: {tone}

Your role is to help users formulate a clear, complete legal question.

## Rules
1. ANALYZE the user's message and conversation history.
2. Decide ONE of three actions:

### Action A: DOMAIN_MISMATCH
If the question is clearly outside your specialty ({specialty}), suggest the appropriate leader.
Output format:
[ACTION:REFERRAL]
(Write a friendly message explaining this isn't your specialty and recommend the right leader by name and specialty)

### Action B: NEED_MORE_INFO
If the question matches your specialty but lacks key information, ask follow-up questions.
Required information for {specialty}:
{fields_str}
Output format:
[ACTION:ASK]
(Write 2-4 specific follow-up questions in your tone, focusing on the missing information)

### Action C: READY
If sufficient information exists, compose a well-structured legal question prompt.
Output format:
[ACTION:PROMPT]
(Write the organized legal question prompt that the user can use for detailed legal analysis. Include all gathered facts clearly structured.)

## Important
- Be warm and professional in your leader persona
- Ask only what's truly missing, don't repeat what the user already told you
- When composing the prompt, organize all facts the user provided into a clear legal question
- ALWAYS start your response with exactly one of: [ACTION:REFERRAL], [ACTION:ASK], or [ACTION:PROMPT]"""
    else:
        return f"""당신은 '{leader_name}' 리더입니다. 전문 분야: {specialty}
성격: {personality}
말투: {tone}
{f'캐치프레이즈: {catchphrase}' if catchphrase else ''}

당신의 역할은 사용자가 명확하고 완전한 법률 질문을 만들도록 돕는 것입니다.

## 규칙
1. 사용자의 메시지와 대화 기록을 분석하세요.
2. 다음 세 가지 중 하나를 결정하세요:

### Action A: 분야 불일치
질문이 당신의 전문분야({specialty})와 맞지 않으면, 적절한 리더를 추천하세요.
출력 형식:
[ACTION:REFERRAL]
(당신의 말투로 친근하게 해당 분야 전문 리더를 소개하는 메시지)

### Action B: 정보 부족
질문이 전문분야와 맞지만 핵심 정보가 부족하면, 추가 질문을 하세요.
{specialty} 분야 필수 정보:
{fields_str}
출력 형식:
[ACTION:ASK]
(2~4개의 구체적인 추가 질문을 당신의 말투로 작성. 부족한 정보만 질문)

### Action C: 정보 충분
충분한 정보가 모이면, 정리된 법률 질문 프롬프트를 작성하세요.
출력 형식:
[ACTION:PROMPT]
(사용자가 수집한 모든 정보를 체계적으로 정리한 법률 질문 프롬프트. 이 프롬프트를 일반 질문에 사용하면 상세한 법률 분석을 받을 수 있습니다.)

## 중요
- 리더 페르소나를 유지하면서 따뜻하고 전문적으로 대화하세요
- 사용자가 이미 알려준 정보는 다시 묻지 마세요
- 프롬프트 작성 시 사용자가 제공한 모든 사실을 체계적으로 정리하세요
- 응답은 반드시 [ACTION:REFERRAL], [ACTION:ASK], [ACTION:PROMPT] 중 하나로 시작하세요"""


async def run_leader_triage(
    gc: Any,
    query: str,
    history: List[Dict],
    leader_info: Dict[str, str],
    persona: Dict[str, str],
    lang: str = "",
) -> Dict[str, Any]:
    """리더 인테이크 트리아지 실행.

    Returns:
        {"action": "referral"|"ask"|"prompt", "text": "응답 텍스트"}
    """
    leader_name = leader_info.get("name", "마디")
    specialty = leader_info.get("specialty", "통합")
    intake_fields = _get_intake_fields(specialty)

    system_prompt = _build_triage_prompt(
        leader_name, specialty, persona, intake_fields, lang,
    )

    # 대화 기록 구성
    messages = []
    for msg in history:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user" and content:
            messages.append({"role": "user", "parts": [{"text": content[:2000]}]})
        elif role in ("assistant", "model") and content:
            messages.append({"role": "model", "parts": [{"text": content[:2000]}]})

    from google.genai import types as genai_types

    config = genai_types.GenerateContentConfig(
        system_instruction=system_prompt,
        max_output_tokens=800,
    )

    model = get_model(mode="leader_chat")  # lite 모델

    try:
        loop = asyncio.get_running_loop()

        def _call():
            chat = gc.chats.create(
                model=model,
                config=config,
                history=messages,
            )
            return chat.send_message(query)

        resp = await asyncio.wait_for(
            loop.run_in_executor(None, _call),
            timeout=15.0,
        )

        text = ""
        if hasattr(resp, "text") and resp.text:
            text = resp.text
        elif hasattr(resp, "candidates") and resp.candidates:
            for part in resp.candidates[0].content.parts:
                if hasattr(part, "text"):
                    text += part.text

        # 액션 파싱
        action = "ask"  # 기본: 추가 질문
        clean_text = text

        if "[ACTION:REFERRAL]" in text:
            action = "referral"
            clean_text = text.replace("[ACTION:REFERRAL]", "").strip()
        elif "[ACTION:PROMPT]" in text:
            action = "prompt"
            clean_text = text.replace("[ACTION:PROMPT]", "").strip()
        elif "[ACTION:ASK]" in text:
            action = "ask"
            clean_text = text.replace("[ACTION:ASK]", "").strip()

        logger.info(f"[LeaderIntake] {leader_name}({specialty}) action={action} query={query[:50]}")
        return {"action": action, "text": clean_text}

    except asyncio.TimeoutError:
        logger.warning(f"[LeaderIntake] 타임아웃 (15초) → 파이프라인 fallback")
        return {"action": "fallback", "text": ""}
    except Exception as e:
        logger.warning(f"[LeaderIntake] 실패: {e} → 파이프라인 fallback")
        return {"action": "fallback", "text": ""}
