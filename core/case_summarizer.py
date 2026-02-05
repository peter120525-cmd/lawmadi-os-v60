import re
import logging
from typing import Dict, List, Any, Optional

# IT 기술: 고가용성 로깅 및 시스템 트레이싱
logger = logging.getLogger("LawmadiOS.CaseSummarizer")

class CaseSummarizer:
    """
    [L5: FACT_EXTRACTOR]
    사용자의 비정형 패킷(Natural Language)에서 법률적 쟁점과 사실관계를 
    결정론적 로직으로 추출하여 시스템 정찰(Recon) 데이터를 생성하는 엔진입니다.
    """

    def __init__(self):
        # IT 기술: 정규표현식을 활용한 고속 패턴 매칭 인프라 (Gate 1 연동)
        self.PATTERNS = {
            "LEASE_DISPUTE": re.compile(r"(전세|월세|보증금|임대차|반환|임대인|임차인)"),
            "CRIMINAL_FRAUD": re.compile(r"(사기|기망|고소|편취|처벌|형사)"),
            "LABOR_ISSUE": re.compile(r"(해고|임금|체불|퇴직금|노동|징계)"),
            "CIVIL_DAMAGE": re.compile(r"(손해배상|위자료|불법행위|채무불이행)")
        }

        # IT 기술: 도메인별 사실관계 템플릿 (Structured Schema)
        self.DOMAIN_MAP = {
            "LEASE_DISPUTE": {
                "case_type": "임대차 보증금 분쟁 의심",
                "law_domains": ["REAL_ESTATE", "CIVIL"],
                "base_keywords": ["주택임대차보호법", "민법 임대차", "보증금 반환"]
            },
            "CRIMINAL_FRAUD": {
                "case_type": "형사 사기/기망 의심",
                "law_domains": ["CRIMINAL"],
                "base_keywords": ["형법 사기", "특경법", "고소장 작성"]
            }
        }

    def summarize(self, user_input: str) -> Dict[str, Any]:
        """
        [IT 기술: Deterministic Summarization Pipeline]
        패턴 감지 -> 도메인 바인딩 -> 사실관계 추론 -> 무결성 패키징 순으로 처리합니다.
        """
        text = user_input.strip()
        
        # 기본 스키마 정의 (L5 Integrity 규격 준수)
        summary = {
            "case_type": "UNKNOWN",
            "facts": [],
            "keywords": [],
            "law_domains": [],
            "is_verified": False
        }

        if not text:
            return summary

        # 1. 지능형 쟁점 감지 (Pattern Interception)
        detected_domain = None
        for domain, pattern in self.PATTERNS.items():
            if pattern.search(text):
                detected_domain = domain
                break

        # 2. 결정론적 데이터 매핑 (Domain Binding)
        if detected_domain and detected_domain in self.DOMAIN_MAP:
            config = self.DOMAIN_MAP[detected_domain]
            summary["case_type"] = config["case_type"]
            summary["law_domains"] = config["law_domains"]
            summary["keywords"] = config["base_keywords"]
            summary["is_verified"] = True
            
            # 사실관계 동적 추출 (IT 기술: Heuristic Fact Extraction)
            summary["facts"] = self._extract_facts(text, detected_domain)
            
            logger.info(f"🔍 [L5] 사실관계 요약 완료: {summary['case_type']}")
        else:
            logger.warning(f"⚠️ [L5] 쟁점 미감지 패킷 수신: {text[:20]}...")

        return summary

    def _extract_facts(self, text: str, domain: str) -> List[str]:
        """
        [IT 기술: Logic-based Fact Derivation]
        감지된 도메인에 따라 질문 내에서 필수 법적 요건(Facts)을 추론합니다.
        """
        facts = []
        if domain == "LEASE_DISPUTE":
            if "전세" in text or "월세" in text: facts.append("임대차 계약 관계 존재")
            if "보증금" in text: facts.append("보증금 지급 사실 확인")
            if "안 줘" in text or "못 받" in text: facts.append("보증금 반환 지체 상황")
        
        elif domain == "CRIMINAL_FRAUD":
            if "돈" in text and "속" in text: facts.append("재산상 이익 취득 및 기망 행위 정황")
            
        return facts

    def validate_summary(self, summary: Dict[str, Any]) -> bool:
        """[IT 기술: Summary Integrity Check] 생성된 요약 객체의 유효성을 검증합니다."""
        return summary.get("is_verified", False) and len(summary.get("law_domains", [])) > 0