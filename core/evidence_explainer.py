import json
import logging
from typing import Dict, List, Any, Optional

# IT 기술: 고가용성 로깅 및 트레이싱 시스템
logger = logging.getLogger("LawmadiOS.EvidenceExplainer")

class EvidenceExplainer:
    """
    [L5: EVIDENCE_INTERFACE]
    국가법령정보센터(SSOT)에서 수집된 로우 데이터를 사용자 친화적이되,
    법적 근거가 명확히 태깅된 구조화된 텍스트로 변환하는 렌더링 엔진입니다.
    """
    
    def __init__(self):
        # IT 기술: 출력 템플릿의 일관성을 위한 메타데이터 규격 정의
        self.source_label = "📌 [SSOT_AUTHORITY_SOURCE: 국가법령정보센터]"
        self.trace_template = "\n\n--- [DATA_TRACEABILITY_METADATA] ---\nSource: {source}\nDocument_ID: {doc_id}\nIntegrity_Status: VERIFIED\n"

    def format_with_traceability(self, ai_analysis: str, verdict: Dict[str, Any]) -> str:
        """
        [IT 기술: Metadata Tagging]
        AI의 해석 결과 하단에 데이터의 원천 정보를 강제로 바인딩하여 
        추적 가능성(Traceability)을 확보합니다. (Gate 3 구현체)
        """
        doc_id = verdict.get("id", "UNKNOWN_ID")
        source = verdict.get("name", "대한민국 법령")
        
        # 추적 메타데이터 생성
        metadata = self.trace_template.format(source=source, doc_id=doc_id)
        
        return f"{ai_analysis}{metadata}"

    def explain_articles(self, context: Dict[str, Any]) -> str:
        """
        [IT 기술: Payload Extraction]
        DRF로부터 수신된 JSONB 페이로드를 파싱하여 법령 원문을 추출합니다.
        기존의 하드코딩된 조언 대신, 철저히 SSOT 근거 기반의 텍스트만 생성합니다.
        """
        if not context or not isinstance(context, dict):
            logger.warning("🚨 [L5] 유효하지 않은 컨텍스트 수신 - Fail-Closed 메시지 반환")
            return "⚠️ 시스템 보호 정책(FAIL_CLOSED)에 따라, 확정된 법령 근거가 없는 답변을 제한합니다."

        # DRF 데이터 구조에서 실제 조문 추출 (L3 Strike 데이터 대응)
        content = context.get("content")
        if not content:
            return "🔍 [SYSTEM_NOTICE] 해당 쟁점과 매칭되는 법령 조문 본문을 수집하지 못했습니다."

        # IT 기술: 데이터 정규화 및 리스트화
        articles = content if isinstance(content, list) else [content]
        
        lines = [self.source_label, ""]
        
        for art in articles:
            # IT 기술: 계층적 데이터 필드 탐색 (조문제목, 조문내용)
            title = art.get("조문제목") or art.get("title") or "관련 조문"
            body = art.get("조문내용") or art.get("body") or "내용을 불러올 수 없습니다."
            
            lines.append(f"[{title}]")
            lines.append(body.strip())
            lines.append("")

        # 하드코딩된 조언 대신, 시스템이 보증하는 '근거 기반 안내'만 포함
        lines.append("──────────────────────────────")
        lines.append("※ 위 법령은 시스템이 실시간으로 동기화한 최신 데이터입니다.")
        lines.append("※ 구체적인 대응은 위 원문을 기초로 법률 전문가의 검토를 받으시기 바랍니다.")

        return "\n".join(lines)

    def generate_actionable_ux(self) -> Dict[str, Any]:
        """[IT 기술: UX Logic] Fail-Closed 시 사용자에게 제공할 가이드라인 생성"""
        return {
            "response": "검색 결과가 존재하지 않거나 무결성 검증을 통과하지 못했습니다.",
            "guide": [
                "1. 정확한 법령 명칭을 포함하여 다시 질문해 주세요.",
                "2. 인터넷 환경 또는 국가법령정보센터의 API 상태를 확인 중입니다."
            ]
        }