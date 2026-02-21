"""
Lawmadi OS 테스트 공통 Fixture.
외부 API 호출 없이 순수 함수 테스트를 위한 설정.
"""
import sys
import os
import pytest

# 프로젝트 루트를 sys.path에 추가
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


@pytest.fixture
def sample_legal_response():
    """헌법 적합성 검증용 법률 응답 샘플"""
    return (
        "민법 제750조에 따르면 불법행위로 인한 손해배상 책임이 발생합니다. "
        "대법원 2020다12345 판례에서는 이와 같은 사안에서 피해자의 "
        "손해배상청구권이 인정된 바 있습니다. "
        "구체적인 절차는 다음과 같습니다:\n"
        "1. 내용증명 발송\n"
        "2. 민사소송 제기\n"
        "3. 법원 조정 신청"
    )


@pytest.fixture
def sample_invalid_response_lawyer():
    """변호사 사칭이 포함된 응답"""
    return "저는 변호사입니다. 민법 제750조에 따라 손해배상을 청구할 수 있습니다."


@pytest.fixture
def sample_invalid_response_guarantee():
    """결과 보장이 포함된 응답"""
    return "민법 제750조에 따라 반드시 승소할 수 있습니다. 걱정하지 마세요."
