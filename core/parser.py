import re
import time
import logging
from typing import Dict, List, Any, Optional

# [IT 기술: 커널 로깅 및 시스템 트레이싱]
logger = logging.getLogger("LawmadiOS.Parser")

class LawmadiParser:
    """
    [L1: DOCUMENT_LAYOUT_ANALYZER]
    비정형 법률 텍스트(판례, 법령 원문)를 정밀 분석하여 
    계층적 구조(조-항-호-목)로 변환하는 지능형 파싱 엔진입니다.
    """
    def __init__(self):
        # IT 기술: 법률 특화 정규표현식 엔진 (Hardened Regex)
        # 조문 패턴: 제100조(제목) 또는 제100조의2(제목) 대응
        self.article_pattern = re.compile(r"제\s?(\d+)\s?조(?:의\d+)?\s?\((.*?)\)")
        
        # 항 패턴: ①, ② 등 원문자 또는 '1.' 형태의 단락 감지
        self.paragraph_pattern = re.compile(r"^[①-⑮]|[1-9]\.")
        
        # [IT 기술: 사법 표준 사건번호 패턴]
        # 4자리 연도 + 법원/사건구분(가~회) + 일련번호 규격화
        # 대법원 판결문 및 하급심 사건번호 체계를 포괄함
        self.case_number_pattern = re.compile(r"\d{4}\s*[가-힣]{1,4}\s*\d+")

    def parse_legal_text(self, raw_text: str) -> Dict[str, Any]:
        """
        [IT 기술: Structural Transformation Pipeline]
        비정형 텍스트를 시스템이 처리 가능한 구조적 데이터(JSONB 규격)로 변환합니다.
        """
        if not raw_text or not raw_text.strip():
            logger.warning("⚠️ [L1] 빈 텍스트 수신 - 파이프라인 중단")
            return {"metadata": {}, "content": [], "status": "EMPTY"}

        try:
            structured_data = {
                "metadata": self._extract_metadata(raw_text),
                "content": self._split_by_hierarchy(raw_text),
                "os_version": "v60.0.0",
                "integrity_check": "PENDING"
            }
            logger.info(f"✅ [L1] 문서 구조화 완료: {structured_data['metadata'].get('case_number')}")
            return structured_data
        except Exception as e:
            logger.error(f"🚨 [L1] 파싱 중 치명적 오류: {e}")
            return {"status": "ERROR", "message": str(e)}

    def _extract_metadata(self, text: str) -> Dict[str, str]:
        """[IT 기술: Metadata Reconnaissance] 핵심 식별 데이터 추출"""
        case_no_match = self.case_number_pattern.search(text)
        return {
            "case_number": case_no_match.group().strip() if case_no_match else "UNKNOWN",
            "analysis_timestamp": str(int(time.time())),
            "encoding": "UTF-8"
        }

    def _split_by_hierarchy(self, text: str) -> List[Dict[str, Any]]:
        """
        [IT 기술: Hierarchical Decomposition]
        텍스트를 '조(Article)' 단위로 선분할하고 내부의 '항(Paragraph)'을 계층적으로 정렬합니다.
        """
        articles = []
        lines = text.split('\n')
        current_article = None

        for line in lines:
            line = line.strip()
            if not line: continue

            # Gate 1: 조문 머리말 감지 (제N조)
            article_match = self.article_pattern.search(line)

            if article_match:
                if current_article:
                    articles.append(current_article)
                
                current_article = {
                    "article_no": article_match.group(1),
                    "title": article_match.group(2),
                    "content_raw": line,
                    "paragraphs": []
                }
            elif current_article:
                # Gate 2: 항(Paragraph) 및 하부 구조 감지
                if self.paragraph_pattern.match(line):
                    current_article["paragraphs"].append(line)
                else:
                    # 이전 항의 연속된 내용일 경우 병합 (IT 기술: Buffer Maintenance)
                    if current_article["paragraphs"]:
                        current_article["paragraphs"][-1] += f" {line}"
                    else:
                        current_article["content_raw"] += f" {line}"

        if current_article:
            articles.append(current_article)

        return articles

    def clean_legal_packet(self, text: str) -> str:
        """
        [IT 기술: Data Sanitization]
        법률 문서 특유의 불필요한 개행 및 중복 공백을 정규화합니다.
        """
        # 연속된 공백 및 탭 제거
        text = re.sub(r"[ \t]+", " ", text)
        # 3번 이상의 연속 개행을 2번으로 축소
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def validate_structure(self, parsed_data: Dict) -> bool:
        """[L5] 파싱 결과의 구조적 무결성 검증"""
        content = parsed_data.get("content", [])
        # 조문 번호가 숫자로 구성되어 있는지 검증하는 IT 보안 로직
        for art in content:
            if not art.get("article_no", "").isdigit():
                return False
        return True