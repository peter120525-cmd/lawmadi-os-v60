"""
Lawmadi OS v60 — 헌법 적합성 검증 모듈.
main.py에서 분리됨 (Item 7).
"""
import re


def validate_constitutional_compliance(response_text: str) -> bool:
    if not response_text or len(response_text.strip()) < 10:
        return False

    t = response_text

    # 1) 변호사 사칭 금지
    if "변호사입니다" in t or "변호사로서" in t:
        return False

    # 2) placeholder 날짜/타임라인 금지
    banned_patterns = [
        r"2024-MM-DD",
        r"YYYY-MM-DD",
        r"HH:MM:SS",
        r"ASCII_TIMELINE_V2\(SYSTEM_CORE_CHECK\)",
    ]
    for p in banned_patterns:
        if re.search(p, t):
            return False

    # 3) 근거 없는 상태 단정 차단
    banned_phrases = [
        "Ready and Verified",
        "완벽하게 작동",
        "모듈이 모두 활성화",
        "즉각적인 접근이 가능",
    ]
    if any(x in t for x in banned_phrases):
        return False

    # 4) 법조문 참조 없는 단정적 법률 주장 차단
    legal_assertion_patterns = [
        r"(?:위법|불법|합법|적법)(?:입니다|합니다|이다)",
        r"(?:의무|권리)가\s*(?:있습니다|없습니다|발생합니다)",
        r"(?:처벌|처분|제재)(?:을\s*)?(?:받습니다|됩니다|받게\s*됩니다)",
    ]
    has_legal_assertion = any(re.search(p, t) for p in legal_assertion_patterns)
    has_legal_source = bool(re.search(r'제\s?\d+\s?조|판례|대법원|헌법재판소|법령|법률\s+제\d+호', t))
    if has_legal_assertion and not has_legal_source:
        return False

    # 5) 불법 행위 조장 차단
    illegal_incitement = [
        "증거를 인멸",
        "증거를 없애",
        "증거 인멸",
        "증거를 숨기",
        "뇌물을 제공",
        "뇌물을 주",
        "허위 진술",
        "위증을 하",
        "위조하",
        "문서를 조작",
        "탈세 방법",
        "세금을 탈루",
    ]
    if any(phrase in t for phrase in illegal_incitement):
        return False

    # 6) 결과 보장 차단
    guarantee_patterns = [
        r"반드시\s*승소",
        r"100\s*%\s*(?:이길|승소|성공|확실)",
        r"무조건\s*(?:이길|승소|성공)",
        r"확실히\s*(?:이길|승소|이깁니다)",
        r"틀림없이\s*(?:이길|승소|이깁니다)",
        r"보장합니다",
        r"장담합니다",
    ]
    if any(re.search(p, t) for p in guarantee_patterns):
        return False

    return True
