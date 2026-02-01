import re
import time
from typing import Dict, List, Any


class LawmadiParser:
    """
    [L1] 문서 레이아웃 분석기: 비정형 법률 텍스트의 구조화
    """
    def __init__(self):
        self.article_pattern = re.compile(r"제(\d+)조\((.*?)\)")
        self.paragraph_pattern = re.compile(r"^[①②③④⑤⑥⑦⑧⑨⑩]")

        # 사건번호: 4자리 연도 + 법원 구분자 + 번호
        # 법원 구분자는 실제 대법원 사용 문자로 명시
        self.case_number_pattern = re.compile(
            r"\d{4}[가나다라마바사아자차카타파하"
            r"가나다라마바사아자차카타파하"  # 단일글자
            r"가나다라마바사아자차카타파하"
            r"]\d+"
        )

    def parse_legal_text(self, raw_text: str) -> Dict[str, Any]:
        """raw_text를 분석하여 조문별로 분리된 구조적 데이터를 반환합니다."""
        structured_data = {
            "metadata": self._extract_metadata(raw_text),
            "content": self._split_by_articles(raw_text)
        }
        return structured_data

    def _extract_metadata(self, text: str) -> Dict[str, str]:
        """사건번호, 법령명 등 메타데이터 추출"""
        case_no = self.case_number_pattern.search(text)
        return {
            "case_number": case_no.group() if case_no else "Unknown",
            "analysis_timestamp": str(int(time.time()))  # time 모듈 정상 사용
        }

    def _split_by_articles(self, text: str) -> List[Dict[str, Any]]:
        """텍스트를 '제N조' 단위로 분리"""
        articles = []
        lines = text.split('\n')
        current_article = None

        for line in lines:
            line = line.strip()
            article_match = self.article_pattern.search(line)

            if article_match:
                if current_article:
                    articles.append(current_article)
                current_article = {
                    "article_no": article_match.group(1),
                    "title": article_match.group(2),
                    "paragraphs": []
                }
            elif current_article and self.paragraph_pattern.match(line):
                current_article["paragraphs"].append(line)

        if current_article:
            articles.append(current_article)

        return articles

    def clean_text(self, text: str) -> str:
        """불필요한 특수문자 및 공백 제거"""
        text = re.sub(r"\s+", " ", text)
        return text.strip()
