import json
import os
import logging
from google import genai
from google.genai import types as genai_types
from core.constants import GEMINI_MODEL
from core.model_fallback import generate_with_fallback, get_model

# IT 기술: 고가용성 로깅 및 트레이싱 시스템 설정
logger = logging.getLogger("LawmadiOS.LawSelector")

class LawSelector:
    """
    [L5 JURISPRUDENCE: 지능형 법리 매칭 엔진]
    63인의 리더(Leader) 페르소나와 동기화되어, DRF에서 추출된 다중 후보군 중
    가장 적합한 법령을 선정하는 고도의 추론 레이어입니다.
    """
    def __init__(self):
        # [L0 KERNEL] 시스템 환경 변수 로드
        api_key = os.environ.get("GEMINI_KEY", "")
        if not api_key:
            logger.warning("⚠️ GEMINI_KEY 누락: L5 지능형 선택 모듈이 비활성 모드로 전환됩니다.")
            self.client = None
        else:
            self.client = genai.Client(api_key=api_key)

    def select_best_law(self, user_query: str, candidates: list) -> dict:
        """
        [IT 아키텍처: Decision Logic]
        사용자 질문의 맥락을 60여 개 전문 분야(민사, 형사, 우주항공 등)와 매칭하여
        최적의 법령 데이터를 추출합니다.
        """
        # [Fail-Safe] 비정상 입력 및 엔진 미가동 시 즉시 폴백(Fallback)
        if not self.client or not candidates:
            return candidates[0] if candidates else None

        if len(candidates) == 1:
            return candidates[0]

        # [IT 기술: 법리적 맥락 강화 프롬프트]
        prompt = f"""
        당신은 Lawmadi OS의 [L5 법리 매칭 엔진]입니다.
        63인의 리더(부장판사, 특수부 검사, 변리사 등)를 대신하여, 검색된 법령 중
        질문의 '실질적 쟁점'에 가장 부합하는 단 하나의 법령을 선택하십시오.

        [사용자 질문]
        "{user_query}"

        [검색된 법령 후보군]
        {json.dumps(candidates, ensure_ascii=False, indent=2)}

        [판단 가이드라인]
        1. 질문이 60대 전문 분야(예: 임대차, 우주항공, 의료, 형사 등) 중 어디에 속하는지 먼저 분류하십시오.
        2. 질문의 '핵심 의도'와 법령의 '목적'이 가장 가깝게 일치하는 조문을 우선순위로 둡니다.
        3. 단순 키워드 매칭이 아닌, 법리적 맥락(Jurisprudence Context)을 최우선으로 고려하십시오.
        4. 적합한 후보가 전무할 경우 null을 반환하십시오.

        [데이터 출력 규격]
        반드시 아래 JSON 형식으로만 응답하십시오.
        {{
            "selected_id": "법령ID",
            "reason": "전문 리더 관점에서의 법리적 선택 근거",
            "field_category": "60대 리더 분야 중 해당되는 분야명"
        }}
        """

        try:
            # Gemini Structured Output 추론 (429 시 자동 모델 전환)
            response = generate_with_fallback(
                self.client,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.05,
                    top_p=0.95,
                    thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
                ),
            )

            # 응답 데이터 무결성 검증 및 파싱
            result = json.loads(response.text)
            selected_id = result.get("selected_id")

            if not selected_id:
                logger.info(f"ℹ️ L5: 적합한 법령 매칭 실패 (Query: {user_query[:20]}...)")
                return None

            # [IT 기술: 데이터 정합성 보장 로직]
            for cand in candidates:
                # ID 타입 불일치 방지를 위해 문자열 비교 수행
                if str(cand.get('id')) == str(selected_id):
                    logger.info(f"✅ L5 매칭 성공: [{result.get('field_category')}] 리더 관점 분석 적용")
                    return cand

            # 매칭 실패 시 시스템 가용성을 위해 첫 번째 데이터 반환
            return candidates[0]

        except Exception as e:
            logger.error(f"⚠️ [L5] Jurisprudence Engine Runtime Error: {e}")
            # [IT 가용성 정책: Fail-Safe] 엔진 장애 시 서비스 중단 방지를 위해 기본 후보 반환
            return candidates[0] if candidates else None
