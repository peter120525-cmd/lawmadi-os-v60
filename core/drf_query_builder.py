import logging
from typing import List, Dict, Any

# IT 기술: 고가용성 로깅 및 시스템 트레이싱 설정
logger = logging.getLogger("LawmadiOS.DRFQueryBuilder")

class DRFQueryBuilder:
    """
    [L5: RECON_ENGINE]
    사용자 패킷의 요약 정보를 바탕으로 국가법령정보센터(DRF) API를 정밀 타격하기 위한
    지능형 쿼리 파이프라인을 구축하는 엔진입니다.
    """

    def __init__(self):
        # IT 기술: 시맨틱 매핑 레지스트리 (Scalable Registry)
        # 하드코딩된 if문 대신 데이터 구조화된 매핑 테이블을 사용하여 유지보수성을 극대화합니다.
        self.SEMANTIC_REGISTRY = {
            "주택임대차보호법": ["주택임대차보호법 보증금 반환", "임대차 계약 해지 조항"],
            "상가건물임대차보호법": ["상가건물 임대차보호법 권리금", "상가 임대차 계약 갱신"],
            "민법": ["민법 임대차 보증금", "민법 손해배상 청구"],
            "형법": ["형법 사기죄 구성요건", "형사 고소 절차"],
            "근로기준법": ["근로기준법 부당해고", "임금체불 구제"]
        }
        
        # IT 기술: 기본 검색 가중치 설정
        self.MAX_QUERY_COUNT = 5

    def build_optimized_queries(self, summary: Dict[str, Any]) -> List[str]:
        """
        [IT 기술: Deterministic Query Expansion]
        단순 키워드를 법리적 맥락을 포함한 정밀 검색어로 확장하여 데이터 수집(Recon)의 성공률을 높입니다.
        """
        keywords = summary.get("keywords", [])
        case_type = summary.get("case_type", "UNKNOWN")
        
        # 1. 기본 쿼리 생성 (Identity Query)
        optimized_queries = []
        if case_type != "UNKNOWN":
            optimized_queries.append(case_type)

        # 2. 시맨틱 확장 (Semantic Expansion)
        # 레지스트리를 스캔하여 매칭되는 전문 법리 쿼리를 추가합니다.
        for kw in keywords:
            for registry_key, expansion_list in self.SEMANTIC_REGISTRY.items():
                if registry_key in kw:
                    optimized_queries.extend(expansion_list)
                    break # 최적의 매칭 하나만 선택하여 노이즈 방지

        # 3. 데이터 무결성 및 중복 제거 (De-duplication)
        # 중복된 쿼리를 제거하고 API 호출 비용 최적화를 위해 개수를 제한합니다.
        unique_queries = list(dict.fromkeys(optimized_queries))
        final_queries = unique_queries[:self.MAX_QUERY_COUNT]

        if not final_queries:
            # IT 기술: 데이터 고갈 방지를 위한 폴백(Fallback) 로직
            logger.warning("⚠️ [L5] 생성된 쿼리 부재 - 기본 키워드로 폴백 실행")
            return keywords if keywords else ["대한민국 법령"]

        logger.info(f"✅ [L5] {len(final_queries)}개의 지능형 정찰 쿼리 생성 완료")
        return final_queries

    def update_registry(self, new_mapping: Dict[str, List[str]]):
        """[IT 기술: Dynamic Infrastructure] 시스템 가동 중에도 매핑 테이블을 업데이트할 수 있습니다."""
        self.SEMANTIC_REGISTRY.update(new_mapping)
        logger.info("📡 [L5] 시맨틱 레지스트리 동적 업데이트 완료")

# 전역 유틸리티 함수 (기존 코드와의 하위 호환성 유지)
def build_queries(summary: Dict[str, Any]) -> List[str]:
    builder = DRFQueryBuilder()
    return builder.build_optimized_queries(summary)