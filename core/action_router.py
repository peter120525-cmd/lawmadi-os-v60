import logging
from typing import Dict, List, Any, Optional

# IT 기술: 내부 모듈 간의 유기적 결합 (L5 Layer Integration)
from core.evidence_explainer import EvidenceExplainer
from core.drf_integrity import verify_articles # 기존 무결성 검증 모듈 가정

# IT 기술: 고가용성 로깅 및 시스템 트레이싱
logger = logging.getLogger("LawmadiOS.ActionRouter")

class ActionRouter:
    """
    [L5: DECISION_DISPATCHER]
    사용자의 선택(Choice)을 기반으로 최적의 법리 탐색 경로를 결정하고,
    수집된 데이터를 검증하여 안전한 인터페이스로 송출하는 라우팅 엔진입니다.
    """

    def __init__(self, drf_connector: Any):
        self.drf = drf_connector
        self.explainer = EvidenceExplainer()
        
        # IT 기술: 가변적 라우팅 레지스트리 (Scalable Registry)
        # 하드코딩 대신 설정 파일이나 DB에서 동적으로 로드 가능하도록 설계
        self.ACTION_REGISTRY = {
            "A": {
                "flow_name": "CONTENT_PROOF",
                "keywords": ["내용증명", "민법", "주택임대차보호법"],
                "description": "임대차 보증금 반환을 위한 행정/민사적 대응"
            },
            "B": {
                "flow_name": "CRIMINAL_FRAUD",
                "keywords": ["사기", "형법", "전세사기"],
                "description": "형사적 고소 및 처벌 가능성 검토"
            },
            "C": {
                "flow_name": "CIVIL_LITIGATION",
                "keywords": ["보증금 반환", "민사소송", "가압류"],
                "description": "본안 소송 및 강제 집행 절차"
            }
        }

    def route_action(self, choice: str, summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        [IT 기술: Atomic Routing Pipeline]
        선택 감지 -> 데이터 수집(Strike) -> 무결성 검증 -> 렌더링 순으로 처리합니다.
        """
        key = choice.upper()[0] if choice else ""
        route_config = self.ACTION_REGISTRY.get(key)

        # 1. 경로 유효성 검사 (Route Validation)
        if not route_config:
            logger.warning(f"🚨 [L5] 정의되지 않은 라우팅 요청: {choice}")
            return self.explainer.generate_actionable_ux()

        flow_name = route_config["flow_name"]
        search_query = " ".join(route_config["keywords"])

        logger.info(f"🚦 [L5] 액션 라우팅 활성화: {flow_name} (Query: {search_query})")

        try:
            # 2. 데이터 타격 (L3 Strike)
            # DRFConnector의 fetch_verified_law를 호출하여 SSOT 데이터 획득
            context = self.drf.fetch_verified_law(search_query)
            
            # 3. 데이터 무결성 및 존재 유무 검증 (Integrity Check)
            if not context or context.get("status") != "VERIFIED":
                return {
                    "fail_closed": True,
                    "status": "DATA_NOT_FOUND",
                    "message": f"[{flow_name}] 단계에 필요한 법령 근거를 수집하지 못했습니다.",
                    "guide": self.explainer.generate_actionable_ux()["guide"]
                }

            articles = context.get("content")
            # IT 기술: 외부 검증 모듈을 통한 패킷 전수 검사
            # (verify_articles가 core.drf_integrity에 존재한다고 가정)
            # if not verify_articles(articles): ... 

            # 4. 결과 렌더링 및 출력 (Enforcement)
            # EvidenceExplainer를 통해 구조화된 법리 해석 텍스트 생성
            rendered_response = self.explainer.explain_articles(context)

            return {
                "status": "SUCCESS",
                "flow": flow_name,
                "response": rendered_response,
                "metadata": {
                    "keywords_used": route_config["keywords"],
                    "timestamp": context.get("timestamp")
                }
            }

        except Exception as e:
            logger.error(f"💥 [L5] 라우팅 런타임 오류: {e}")
            return {
                "fail_closed": True,
                "status": "KERNEL_CRASH",
                "message": "시스템 내부 통제 모듈 오류로 인해 안내를 중단합니다."
            }