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

# LawmadiLM API 설정 (모든 티어 공통 — 주력 50%)
LAWMADILM_API_URL = os.getenv("LAWMADILM_API_URL", "https://lawmadilm-api-938146962157.asia-northeast3.run.app")
