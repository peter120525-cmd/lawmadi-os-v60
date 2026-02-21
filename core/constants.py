"""
Lawmadi OS v60 — 전역 상수 모음.
main.py에서 분리됨.

사용법:
    from core.constants import OS_VERSION, DEFAULT_GEMINI_MODEL, LAWMADILM_API_URL
"""
import os

# [감사 #3.6] 버전 단일 소스
OS_VERSION = "v60.0.0"

# Gemini 모델명 통일 상수 (항목 #6)
DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"

# LawmadiLM API 설정 (주력 답변 생성기)
LAWMADILM_API_URL = os.getenv("LAWMADILM_API_URL", "https://lawmadilm-api-938146962157.asia-northeast3.run.app")

# LawmadiLM RAG 서비스 URL (ChromaDB + multilingual-e5-large 임베딩 검색)
LAWMADILM_RAG_URL = os.getenv("LAWMADILM_RAG_URL", "")

# Lawmadi OS 메인 API URL (테스트/모니터링/스크립트 공통)
LAWMADI_OS_API_URL = os.getenv("LAWMADI_OS_API_URL", "https://lawmadi-os-v60-938146962157.asia-northeast3.run.app")

# FAIL_CLOSED 응답: 검증 실패 시 사용자에게 반환
FAIL_CLOSED_RESPONSE = (
    "⚠️ **법률 정보 검증 실패**\n\n"
    "답변에 포함된 법률 근거의 정확성을 충분히 확인하지 못했습니다.\n"
    "부정확한 정보를 전달하는 것보다 안전을 우선합니다.\n\n"
    "## 지금 하실 수 있는 일\n\n"
    "1. **질문을 더 구체적으로** 다시 작성해 주세요\n"
    "   - 예: \"전세 보증금\" → \"전세 보증금 3억 원, 계약 만료 후 2개월 경과, 임대인이 반환 거부\"\n"
    "2. **국가법령정보센터**에서 직접 검색: https://law.go.kr\n"
    "3. **무료 법률 상담** 이용:\n"
    "   - 대한법률구조공단 ☎ 132\n"
    "   - 법률홈닥터 ☎ 1600-6503\n\n"
    "다시 질문해 주시면 더 정확한 답변을 드리겠습니다."
)
