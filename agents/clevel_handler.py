#!/usr/bin/env python3
"""
Lawmadi OS C-Level 임원 핸들러

3명의 C-Level 임원:
- 서연 (CSO): Chief Strategy Officer - 전략 분석
- 지유 (CTO): Chief Technology Officer - 기술 자문
- 유나 (CCO): Chief Content Officer - 콘텐츠 설계
"""
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger("LawmadiOS.CLevelHandler")


class CLevelHandler:
    """
    C-Level 임원 호출 및 전문 영역 라우팅
    """

    def __init__(self, core_registry: Dict):
        self.executives = core_registry

        # C-Level 호출 키워드 매핑
        self.call_patterns = {
            "CSO": {
                "names": ["서연", "CSO", "Chief Strategy"],
                "triggers": [
                    "전략", "분석", "방향", "로드맵", "기획",
                    "컨설팅", "의사결정", "우선순위", "방침"
                ],
                "specialty": "전략 및 의사결정 지원"
            },
            "CTO": {
                "names": ["지유", "CTO", "Chief Technology"],
                "triggers": [
                    "기술", "시스템", "아키텍처", "ai", "무결성",
                    "알고리즘", "검증", "테스트", "성능", "보안"
                ],
                "specialty": "기술 아키텍처 및 AI 검증"
            },
            "CCO": {
                "names": ["유나", "CCO", "Chief Content"],
                "triggers": [
                    "콘텐츠", "사용자", "ux", "ui", "인터페이스",
                    "경험", "디자인", "가독성", "설명", "표현"
                ],
                "specialty": "콘텐츠 및 사용자 경험 설계"
            }
        }

    # 법률 도메인 키워드 — 이름 호출이 있어도 전문 리더에게 위임해야 할 질문 감지용
    LEGAL_DOMAIN_KEYWORDS = [
        # 헌법
        "헌법", "위헌", "기본권", "헌재", "헌법재판소", "위헌법률",
        # 형사
        "형법", "형사", "사기", "횡령", "폭행", "살인", "절도", "성범죄",
        "고소", "처벌", "범죄", "기소", "구속", "수사", "검찰", "배임",
        "명예훼손", "허위사실", "모욕", "비방",
        # 민사
        "민법", "손해배상", "계약", "채권", "물권", "채무",
        # 가족
        "이혼", "양육권", "상속", "유언", "친권", "위자료", "혼인",
        # 노동
        "노동", "해고", "임금", "산재", "퇴직금", "근로기준법", "부당해고", "노동조합",
        # 부동산/임대차
        "임대차", "전세", "보증금", "월세",
        "부동산", "등기", "경매", "재개발",
        # 사고/보험
        "교통사고", "보험", "의료사고", "의료", "병원", "의료과실",
        # 지식재산
        "저작권", "특허", "상표", "지식재산", "특허권", "상표권", "발명", "표절",
        # 행정
        "행정소송", "행정심판", "공정거래", "행정처분",
        # 조세
        "조세", "세금", "탈세", "과세", "국세", "지방세", "상속세", "증여",
        # IT/개인정보
        "개인정보", "정보통신", "데이터", "gdpr", "ai", "ai윤리", "인공지능",
        "it", "보안", "해킹", "사이버", "알고리즘",
        # 기타 법률 분야
        "소비자", "소년법", "군형법",
        "환경", "오염", "폐기물",
        "무역", "관세", "수출", "수입",
        "스타트업", "벤처", "투자",
        "산업재해", "산업안전",
        "게임", "콘텐츠",
        "해상", "항공", "선박",
        "에너지", "자원", "전력",
        "장애인", "차별", "인권",
    ]

    def _has_legal_domain(self, query: str) -> bool:
        """질문에 법률 도메인 키워드가 포함되어 있는지 확인"""
        query_lower = query.lower()
        return any(kw in query_lower for kw in self.LEGAL_DOMAIN_KEYWORDS)

    def detect_clevel_call(self, query: str) -> Optional[Tuple[str, str]]:
        """
        Query에서 C-Level 임원 명시적 호출 감지

        Returns:
            Tuple[executive_id, reason] or None
        """
        query_lower = query.lower()

        # 1. 직접 호출 (이름) — 단, 자기소개 요청만 direct로 처리
        #    법률 도메인 키워드가 포함되면 전문 리더에게 위임 (swarm 보강)
        for exec_id, config in self.call_patterns.items():
            for name in config["names"]:
                if name in query or name.lower() in query_lower:
                    if self._has_legal_domain(query):
                        logger.info(f"🎯 C-Level 이름 호출 + 법률 도메인 감지: {exec_id} → swarm 보강으로 전환")
                        return (exec_id, f"이름 호출 '{name}' + 법률 도메인 → 전문 리더 위임")
                    logger.info(f"🎯 C-Level 명시적 호출: {exec_id} ({name})")
                    return (exec_id, f"명시적 호출: '{name}'")

        # 2. 전문 영역 탐지
        for exec_id, config in self.call_patterns.items():
            matched_triggers = []
            for trigger in config["triggers"]:
                if trigger in query_lower:
                    matched_triggers.append(trigger)

            # 2개 이상 키워드 매칭 시 해당 임원 호출
            if len(matched_triggers) >= 2:
                logger.info(f"🎯 C-Level 전문 영역 감지: {exec_id} (키워드: {matched_triggers})")
                return (exec_id, f"전문 영역 감지: {', '.join(matched_triggers[:3])}")

        return None

    def get_clevel_system_instruction(
        self,
        exec_id: str,
        base_instruction: str
    ) -> str:
        """
        C-Level 임원별 시스템 지시 생성

        Args:
            exec_id: CSO, CTO, CCO
            base_instruction: 기본 시스템 지시

        Returns:
            str: C-Level 전용 시스템 지시
        """
        exec_info = self.executives.get(exec_id, {})
        name = exec_info.get("name", "Unknown")
        role = exec_info.get("role", "Unknown")
        meaning = exec_info.get("meaning", "")
        profile = exec_info.get("profile", "")

        config = self.call_patterns.get(exec_id, {})
        specialty = config.get("specialty", "")

        instruction = f"""{base_instruction}

🎯 당신의 역할: {name} ({role})
🎯 의미: {meaning}
🎯 프로필: {profile}
🎯 전문 영역: {specialty}

당신은 Lawmadi OS의 C-Level 임원으로서, 다음과 같은 관점에서 분석하세요:
"""

        if exec_id == "CSO":
            instruction += """
**서연 (CSO) - 전략적 관점:**

1. **전략적 우선순위 설정**
   - 사안의 핵심 쟁점은 무엇인가?
   - 가장 먼저 해결해야 할 것은?
   - 장기적 vs 단기적 관점

2. **의사결정 지원**
   - 선택지(Options)와 각각의 장단점
   - 리스크와 기회 분석
   - 최선의 전략 제안

3. **로드맵 제시**
   - 단계별 실행 계획
   - 예상되는 장애물과 대응 방안
   - 성공 지표(KPI)

4. **컨설팅 관점**
   - 사건을 전체적으로 조망
   - 숲과 나무를 모두 보는 시각
   - 실행 가능성 검증

반드시 "[서연 (CSO) 전략 분석]"으로 시작하세요.
"""

        elif exec_id == "CTO":
            instruction += """
**지유 (CTO) - 기술적 관점:**

1. **시스템 아키텍처 분석**
   - 법률 시스템의 구조적 이해
   - 각 법률/규정 간의 의존 관계
   - 무결성 검증 (모순 없는지)

2. **AI 검증 및 무결성**
   - 답변의 논리적 정합성
   - 법률 해석의 일관성
   - 근거의 타당성 검증

3. **성능 최적화**
   - 가장 효율적인 절차는?
   - 불필요한 단계 제거
   - 시간/비용 최소화 방안

4. **기술 가이드**
   - 법률 테크 활용 방안
   - 디지털 증거 관리
   - 온라인 절차 활용

반드시 "[지유 (CTO) 기술 분석]"으로 시작하세요.
"""

        elif exec_id == "CCO":
            instruction += """
**유나 (CCO) - 콘텐츠 관점:**

1. **사용자 경험 최적화**
   - 일반인이 이해하기 쉬운 설명
   - 법률 용어의 친절한 풀이
   - 시각적 구조화 (표, 타임라인)

2. **콘텐츠 설계**
   - 정보의 계층 구조
   - 핵심 메시지 우선 제시
   - 세부 사항은 참고 정보로

3. **인터페이스 디자인**
   - 단계별 명확한 가이드
   - 체크리스트 형식 제공
   - 시각적 요소 활용

4. **커뮤니케이션 전략**
   - 감정적 공감
   - 불안 해소
   - 실행 가능한 조언

반드시 "[유나 (CCO) 콘텐츠 설계]"으로 시작하세요.
"""

        instruction += """

📋 응답 형식: 계층 구조 + C-Level 관점

1. 핵심 요약
   1.1 상황 진단 — C-Level 관점의 현황 파악
   1.2 결론 및 전략 방향 — 법률 전략은 서연(CSO) 관점 우선 반영

2. 법률 근거 분석
   2.1 적용 법령 + C-Level 해석
   2.2 관련 판례/선례

3. 시간축 전략
   3.1 과거 (상황 정리)
   3.2 현재 (골든타임) — 전략적/기술적/UX 관점
   3.3 미래 (대응 시나리오)

4. 실행 계획
   4.1 즉시 조치 — C-Level 관점의 우선순위
   4.2 단계별 가이드
   4.3 체크리스트

5. 추가 정보
   5.1 무료 법률 지원
   5.2 관련 법령 요약 + C-Level 인사이트
"""

        return instruction

    def should_invoke_clevel(self, query: str) -> Dict:
        """
        C-Level 호출 여부 및 대상 결정

        Returns:
            Dict: {
                "invoke": bool,
                "executive_id": str or None,
                "reason": str or None,
                "mode": "direct" | "swarm" | "none"
            }
        """
        # 명시적 호출 확인
        clevel_call = self.detect_clevel_call(query)

        if clevel_call:
            exec_id, reason = clevel_call
            # 법률 도메인 키워드 포함 시 → swarm 보강 (전문 리더가 메인)
            if self._has_legal_domain(query):
                return {
                    "invoke": True,
                    "executive_id": exec_id,
                    "reason": reason,
                    "mode": "swarm"  # 전문 리더 메인 + C-Level 보강
                }
            return {
                "invoke": True,
                "executive_id": exec_id,
                "reason": reason,
                "mode": "direct"  # 직접 호출
            }

        # Swarm 모드에서 C-Level 포함 여부 판단
        # (메타 전략 질문, 시스템 관련 질문 등)
        meta_keywords = [
            "어떻게 해야", "방법", "전략", "계획", "시스템",
            "개선", "최적화", "UX", "사용자"
        ]

        meta_score = sum(1 for kw in meta_keywords if kw in query)

        if meta_score >= 2:
            return {
                "invoke": True,
                "executive_id": "CSO",  # 기본은 CSO
                "reason": f"메타 질문 감지 (키워드 {meta_score}개)",
                "mode": "swarm"  # Swarm에 포함
            }

        return {
            "invoke": False,
            "executive_id": None,
            "reason": None,
            "mode": "none"
        }
