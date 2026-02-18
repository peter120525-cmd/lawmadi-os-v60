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
                    "기술", "시스템", "아키텍처", "AI", "무결성",
                    "알고리즘", "검증", "테스트", "성능", "보안"
                ],
                "specialty": "기술 아키텍처 및 AI 검증"
            },
            "CCO": {
                "names": ["유나", "CCO", "Chief Content"],
                "triggers": [
                    "콘텐츠", "사용자", "UX", "UI", "인터페이스",
                    "경험", "디자인", "가독성", "설명", "표현"
                ],
                "specialty": "콘텐츠 및 사용자 경험 설계"
            }
        }

    def detect_clevel_call(self, query: str) -> Optional[Tuple[str, str]]:
        """
        Query에서 C-Level 임원 명시적 호출 감지

        Returns:
            Tuple[executive_id, reason] or None
        """
        query_lower = query.lower()

        # 1. 직접 호출 (이름)
        for exec_id, config in self.call_patterns.items():
            for name in config["names"]:
                if name in query or name.lower() in query_lower:
                    logger.info(f"🎯 C-Level 명시적 호출: {exec_id} ({name})")
                    return (exec_id, f"명시적 호출: '{name}'")

        # 2. 전문 영역 탐지
        for exec_id, config in self.call_patterns.items():
            matched_triggers = []
            for trigger in config["triggers"]:
                if trigger in query_lower:
                    matched_triggers.append(trigger)

            # 3개 이상 키워드 매칭 시 해당 임원 호출
            if len(matched_triggers) >= 3:
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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 당신의 역할: {name} ({role})
🎯 의미: {meaning}
🎯 프로필: {profile}
🎯 전문 영역: {specialty}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 응답 형식: 계층 구조 + C-Level 관점
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
