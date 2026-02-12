import hashlib
import json
import logging
from typing import List, Dict, Any, Optional

# IT 기술: 고가용성 로깅 및 보안 트레이싱 설정
logger = logging.getLogger("LawmadiOS.DRFIntegrity")

class DRFIntegrity:
    """
    [L5: PACKET_INTEGRITY_SHIELD]
    DRF로부터 수신된 개별 조문 패킷의 암호화 지문을 검증하여 
    데이터의 위변조 여부를 결정론적으로 판별하는 보안 엔진입니다.
    """

    def __init__(self):
        # IT 기술: 보안 버전 관리 및 알고리즘 정의
        self.algo = hashlib.sha256
        self.encoding = "utf-8"
        self.version = "v50.2.4-HARDENED"

    def generate_article_hash(self, article: Dict[str, Any]) -> str:
        """
        [IT 기술: Deterministic Hashing]
        데이터의 순서를 고정(sort_keys=True)하여 직렬화함으로써 
        환경에 관계없이 동일한 지문(Fingerprint)을 생성합니다.
        """
        try:
            # IT 기술: 변조 가능성이 있는 핵심 필드를 결합하여 해시 생성
            # 조문 본문뿐만 아니라 제목, ID 등을 포함하여 무결성 범위를 확장함
            target_data = {
                "id": article.get("id") or article.get("법령ID"),
                "title": article.get("title") or article.get("조문제목"),
                "body": article.get("body") or article.get("조문내용")
            }
            
            serialized = json.dumps(target_data, sort_keys=True, ensure_ascii=False)
            return self.algo(serialized.encode(self.encoding)).hexdigest()
        except Exception as e:
            logger.error(f"🚨 [L5] 해시 생성 중 직렬화 오류: {e}")
            return "HASH_FAILURE"

    def verify_articles(self, articles: List[Dict[str, Any]]) -> bool:
        """
        [IT 기술: Zero-Trust Verification]
        수신된 모든 조문 패킷에 대해 전수 조사를 실시합니다.
        단 하나의 패킷이라도 무결성이 파괴되었다면 'Fail-Closed' 원칙에 따라 즉시 차단합니다.
        """
        if not articles:
            logger.warning("⚠️ [L5] 검증할 데이터 패킷이 존재하지 않습니다.")
            return False

        for idx, art in enumerate(articles):
            body = art.get("body") or art.get("조문내용")
            stored_hash = art.get("hash") or art.get("signature")

            # 1. 필수 보안 필드 존재 확인
            if not body or not stored_hash:
                logger.error(f"❌ [L5] 무결성 필드 누락 (Index: {idx})")
                return False

            # 2. 실시간 해시 대조 (IT 기술: Runtime Integrity Check)
            computed_hash = self.generate_article_hash(art)
            
            if computed_hash != stored_hash:
                logger.critical(
                    f"🚨 [INTEGRITY_VIOLATION] 데이터 오염 감지!\n"
                    f"Expected: {stored_hash}\n"
                    f"Computed: {computed_hash}"
                )
                return False

        logger.info(f"✅ [L5] {len(articles)}개 조문 패킷 무결성 검증 통과")
        return True

    def sanitize_packet(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """[IT 기술: Data Normalization] 전송 전 데이터의 규격을 표준화합니다."""
        article["body"] = (article.get("body") or "").strip()
        article["hash"] = self.generate_article_hash(article)
        return article

# 전역 유틸리티 함수 (기존 코드와의 호환성 유지)
def verify_articles(articles: List[Dict[str, Any]]) -> bool:
    engine = DRFIntegrity()
    return engine.verify_articles(articles)

def validate_drf_xml(xml_text: str) -> bool:
    """
    DRF XML 응답 기본 검증
    - XML 형식 기본 체크
    - 에러 태그 확인
    """
    if not xml_text or len(xml_text) < 10:
        logger.warning("⚠️ DRF XML 응답이 비어있거나 너무 짧습니다")
        return False

    # 기본 XML 구조 확인
    if not xml_text.strip().startswith('<'):
        logger.warning("⚠️ DRF 응답이 XML 형식이 아닙니다")
        return False

    # 에러 태그 확인
    if '<error>' in xml_text.lower() or '<err>' in xml_text.lower():
        logger.warning("⚠️ DRF XML에 에러 태그가 포함되어 있습니다")
        return False

    return True