# NOTE: 이 모듈은 프로덕션 코드(main.py)에서 import되지 않음.
# 향후 L5 Kernel 통합 시 활성화 예정. 삭제하지 말 것.
import re
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

# IT 기술: 내부 모듈 간 의존성 주입 (보여주신 파일 구조 반영)
try:
    from core.drf_query_builder import DRFQueryBuilder
    from core.evidence_explainer import EvidenceExplainer
    from core.drf_integrity import DRFIntegrity
except ImportError:
    # 모듈이 아직 구현 전일 경우를 대비한 폴백 로직
    DRFQueryBuilder = None
    EvidenceExplainer = None
    DRFIntegrity = None

# IT 기술: 고가용성 로깅 및 시스템 트레이싱
logger = logging.getLogger("LawmadiOS.GateKernel")

class EnforcementMode(Enum):
    """[L5] 시스템 출력 모드 강제 정의 (Gate 3)"""
    STRICT_GROUNDING = "STRICT"  # 근거 원문 외 발언 금지 (Sandboxed)
    INTERPRETIVE = "INTERPRET"    # 법리적 유연성 허용 (With Traceability)

class LawmadiGateKernel:
    """
    [L5 KERNEL: 3-Gate Hardening Architecture]
    프로젝트의 core 패키지 내 다양한 서브 모듈을 오케스트레이션하여
    법률적 데이터 무결성을 보장하는 중앙 제어 엔진입니다.
    """
    def __init__(self, mode: EnforcementMode = EnforcementMode.STRICT_GROUNDING):
        self.mode = mode
        # Gate 1: 룰 기반 패턴 엔진 (IT 기술: Deterministic Interceptor)
        self.law_pattern = re.compile(r"제\s?\d+\s?조(?:의\d+)?(?:\s?제\d+\s?항)?")
        
        # [IT 기술: Actionable Fail-Closed UX]
        self.actionable_fail_template = {
            "response": "⚠️ [시스템 보호] 요청하신 내용의 법적 근거를 실시간으로 확정할 수 없습니다.",
            "next_steps": [
                "1. 질문에 구체적인 법령 명칭(예: 민법)을 포함해 주세요.",
                "2. 국가법령정보센터(law.go.kr)에서 해당 조문을 직접 확인하십시오.",
                "3. 시스템이 'STRICT' 모드이므로 근거 없는 답변을 거부합니다."
            ]
        }

    # =========================================================
    # 🛡️ GATE 1: 지능형 정찰 및 강제 호출 (Recon Trigger)
    # =========================================================
    def gate1_intercept(self, query: str) -> Tuple[bool, List[str]]:
        """
        [IT 기술: Semantic Reconnaissance]
        단순 키워드 매칭을 넘어, 시맨틱 매핑 테이블을 통해 검색 후보를 확장합니다.
        하드코딩된 if문 대신 전략 패턴(Strategy Pattern)을 지향합니다.
        """
        match = self.law_pattern.search(query)
        
        # IT 기술: 지능형 쿼리 매핑 테이블 (Scalable Registry)
        # 60대 전문 분야와 연동 가능하도록 설계
        SEMANTIC_MAP = {
            "주택임대차": ["주택임대차보호법 보증금", "임대차계약 해지"],
            "상가임대차": ["상가건물 임대차보호법 권리금", "상가 계약 갱신"],
            "민법": ["민법 임대차", "민법 손해배상"],
            "보증금": ["주택임대차보호법 반환", "전세보증금 반환 소송"],
            "해고": ["근로기준법 부당해고", "징계위원회 절차"]
        }

        search_queries = [query]
        
        # 질문 내 키워드 분석 및 쿼리 확장 (Expansion)
        for key, expanded_queries in SEMANTIC_MAP.items():
            if key in query:
                search_queries.extend(expanded_queries)
        
        # 중복 제거 및 검색 효율 최적화 (Max 5 쿼리 제한)
        search_queries = list(dict.fromkeys(search_queries))[:5]

        if match or len(search_queries) > 1:
            logger.info(f"🚨 [Gate 1] 법적 쟁점 감지 및 정찰 쿼리 확장: {len(search_queries)}건")
            # IT 기술: Query Builder 모듈이 존재할 경우 더 고도화된 쿼리 생성
            if DRFQueryBuilder:
                builder = DRFQueryBuilder()
                search_queries = builder.build_optimized_queries(query)
            return True, search_queries
        
        return False, search_queries

    # =========================================================
    # 🛡️ GATE 2: 데이터 무결성 승인 (Verdict & Integrity)
    # =========================================================
    def gate2_verify_ssot(self, raw_candidates: List[Dict]) -> Optional[Dict]:
        """
        drf_integrity 모듈과 협력하여 수집된 데이터의 지문을 검증하고
        시스템이 신뢰할 수 있는 단 하나의 원본(Verdict)을 확정합니다.
        """
        if not raw_candidates:
            return None
        
        # IT 기술: 데이터 정합성 레이어 활용
        if DRFIntegrity:
            integrity_checker = DRFIntegrity()
            valid_candidates = [c for c in raw_candidates if integrity_checker.verify_packet(c)]
        else:
            valid_candidates = [c for c in raw_candidates if 'id' in c and 'content' in c]
        
        if not valid_candidates:
            return None
            
        # Decision Logic: 첫 번째 유효 후보를 SSOT로 승인
        verdict = valid_candidates[0]
        logger.info(f"✅ [Gate 2] SSOT Verdict 승인 완료: {verdict.get('name')}")
        return verdict

    # =========================================================
    # 🛡️ GATE 3: 출력 샌드박싱 및 해석 (Output Enforcement)
    # =========================================================
    def gate3_enforce_output(self, verdict: Dict, ai_analysis: str) -> str:
        """
        STRICT 모드에서는 샌드박싱을 수행하고, INTERPRETIVE 모드에서는
        evidence_explainer를 통해 법리적 근거를 정교하게 태깅합니다.
        """
        if self.mode == EnforcementMode.STRICT_GROUNDING:
            logger.info("🛡️ [Gate 3] STRICT 모드: 데이터 샌드박싱 실행")
            return f"【법령 원문 근거】\n{verdict.get('content', '내용 없음')}"
        
        else:
            logger.info("🛡️ [Gate 3] INTERPRETIVE 모드: 증거 기반 해석 적용")
            # IT 기술: Evidence Explainer 모듈을 통한 메타데이터 강화
            if EvidenceExplainer:
                explainer = EvidenceExplainer()
                return explainer.format_with_traceability(ai_analysis, verdict)
            
            return f"{ai_analysis}\n\n[출처: {verdict.get('name')} | ID: {verdict.get('id')}]"

    # =========================================================
    # 🚀 Kernel Execution Pipeline
    # =========================================================
    def process_query(self, query: str, fetch_fn: Any) -> Dict[str, Any]:
        """
        3대 게이트 인프라를 관통하는 메인 프로세스입니다.
        """
        try:
            # Step 1: Recon (정찰)
            should_fetch, optimized_queries = self.gate1_intercept(query)
            
            # Step 2: Strike (데이터 타격)
            # fetch_fn은 drf_client의 로직과 연결됨
            raw_data = fetch_fn(optimized_queries[0]) if should_fetch else None
            
            if should_fetch and (not raw_data or raw_data.get('status') != "VERIFIED"):
                return self.actionable_fail_template

            # Step 3: Verdict (확정)
            candidates = raw_data.get('candidates', []) if raw_data else []
            verdict = self.gate2_verify_ssot(candidates)
            
            if should_fetch and not verdict:
                return self.actionable_fail_template

            # Step 4: Enforcement (강제)
            final_response = self.gate3_enforce_output(verdict, "AI 법리 분석 결과") if verdict else "일반 응답"
            
            return {
                "status": "SUCCESS",
                "mode": self.mode.value,
                "response": final_response,
                "trace_id": verdict.get('id') if verdict else None
            }

        except Exception as e:
            logger.error(f"💥 Kernel Runtime Error: {e}")
            return self.actionable_fail_template