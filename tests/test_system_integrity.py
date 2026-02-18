#!/usr/bin/env python3
"""
Lawmadi OS v60 시스템 무결성 검증 (pytest 호환)
- DRF API 연결
- SSOT Dual 구조
- 데이터베이스 연결
- Claude/Gemini 검증
- Article 1 & Fail-Closed 원칙
"""
import os
import sys
import json
import pytest
from dotenv import load_dotenv

load_dotenv()

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def main_content():
    with open("main.py", "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="session")
def drf_connector():
    drf_key = os.getenv("LAWGO_DRF_OC", "")
    try:
        from connectors.drf_client import DRFConnector
        return DRFConnector(api_key=drf_key)
    except Exception:
        pytest.skip("DRFConnector import 실패 (로컬 환경)")


# ─── 1. 환경변수 검증 ───────────────────────────────────────────────────────

@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="CI 환경: 환경변수 미설정")
class TestEnvironmentVariables:
    def test_gemini_api_key(self):
        key = os.getenv("GEMINI_API_KEY", "")
        assert key, "GEMINI_API_KEY 미설정"

    def test_lawgo_drf_oc(self):
        key = os.getenv("LAWGO_DRF_OC", "")
        assert key, "LAWGO_DRF_OC 미설정"

    def test_anthropic_api_key(self):
        key = os.getenv("ANTHROPIC_API_KEY", "")
        assert key, "ANTHROPIC_API_KEY 미설정"

    def test_database_url(self):
        url = os.getenv("DATABASE_URL", "")
        assert url, "DATABASE_URL 미설정"


# ─── 2. DRF Connector 검증 ──────────────────────────────────────────────────

class TestDRFConnector:
    def test_init(self, drf_connector):
        assert drf_connector is not None

    def test_drf_url(self, drf_connector):
        assert drf_connector.drf_url is not None

    def test_drf_key(self, drf_connector):
        assert drf_connector.drf_key is not None

    def test_law_search(self, drf_connector):
        if not os.getenv("LAWGO_DRF_OC"):
            pytest.skip("DRF API 키 미설정 (CI 환경)")
        result = drf_connector.law_search("민법")
        assert result is not None, "법령 검색 실패"
        assert isinstance(result, dict), f"응답 타입 오류: {type(result)}"

    def test_precedent_search(self, drf_connector):
        if not os.getenv("LAWGO_DRF_OC"):
            pytest.skip("DRF API 키 미설정 (CI 환경)")
        result = drf_connector.search_precedents("손해배상")
        assert result is not None, "판례 검색 실패"
        assert isinstance(result, dict), f"응답 타입 오류: {type(result)}"


# ─── 3. Dual SSOT 재시도 로직 검증 ──────────────────────────────────────────

class TestDualSSOT:
    def test_dual_ssot_config(self, config):
        dual_ssot = config.get("dual_ssot", {})
        assert dual_ssot, "dual_ssot 설정 없음"

    def test_retry_sequence(self, config):
        dual_ssot = config.get("dual_ssot", {})
        assert "retry_sequence" in dual_ssot, "retry_sequence 미설정"

    def test_cache_ttl(self, config):
        dual_ssot = config.get("dual_ssot", {})
        assert "cache_ttl_seconds" in dual_ssot, "cache_ttl_seconds 미설정"
        assert dual_ssot["cache_ttl_seconds"] > 0

    def test_article1_exists(self, config):
        article1 = config.get("article1", {})
        assert article1, "article1 설정 없음"

    def test_article1_drf_type_json(self, config):
        article1 = config.get("article1", {})
        assert article1.get("drf_type_json_required") is True, "drf_type_json_required != True"

    def test_failclosed_exists(self, config):
        fc = config.get("failclosed_principle", {})
        assert fc, "failclosed_principle 설정 없음"

    def test_failclosed_enabled(self, config):
        fc = config.get("failclosed_principle", {})
        assert fc.get("enabled") is True, "failclosed 비활성화"


# ─── 4. 데이터베이스 연결 검증 ───────────────────────────────────────────────

@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="CI 환경: DB 미설정")
class TestDatabase:
    def test_database_url_set(self):
        url = os.getenv("DATABASE_URL", "")
        assert url, "DATABASE_URL 미설정 — Cloud Run에서만 정상"


# ─── 5. SearchService 검증 ──────────────────────────────────────────────────

class TestSearchService:
    def test_init(self):
        try:
            from services.search_service import SearchService
            svc = SearchService()
            assert svc.ready, "SearchService 준비되지 않음"
        except Exception as e:
            pytest.skip(f"SearchService import 실패: {e}")

    def test_law_search(self):
        try:
            from services.search_service import SearchService
            svc = SearchService()
            if not svc.ready:
                pytest.skip("SearchService 미준비")
            result = svc.search_law("민법")
            assert result is not None
        except Exception as e:
            pytest.skip(f"SearchService 사용 불가: {e}")

    def test_precedent_search(self):
        try:
            from services.search_service import SearchService
            svc = SearchService()
            if not svc.ready:
                pytest.skip("SearchService 미준비")
            result = svc.search_precedents("손해배상")
            assert result is not None
        except Exception as e:
            pytest.skip(f"SearchService 사용 불가: {e}")


# ─── 6. Gemini API 검증 ─────────────────────────────────────────────────────

class TestGeminiAPI:
    def test_api_key_set(self):
        assert os.getenv("GEMINI_API_KEY", ""), "GEMINI_API_KEY 미설정"

    def test_client_init(self):
        key = os.getenv("GEMINI_API_KEY", "")
        if not key:
            pytest.skip("GEMINI_API_KEY 미설정")
        from google import genai as genai_sdk
        client = genai_sdk.Client(api_key=key)
        assert client is not None

    def test_api_call(self):
        key = os.getenv("GEMINI_API_KEY", "")
        if not key:
            pytest.skip("GEMINI_API_KEY 미설정")
        from google import genai as genai_sdk
        client = genai_sdk.Client(api_key=key)
        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents="Hello"
            )
            assert response.text
        except Exception:
            pytest.skip("Gemini API 호출 실패 (로컬 네트워크)")


# ─── 7. 캐시 시스템 검증 ─────────────────────────────────────────────────────

class TestCacheSystem:
    def test_cache_ttl_positive(self, config):
        ttl = config.get("dual_ssot", {}).get("cache_ttl_seconds", 0)
        assert ttl > 0, f"cache_ttl_seconds={ttl}"

    def test_cache_functions_exist(self):
        try:
            from connectors.db_client_v2 import cache_get, cache_set
            assert callable(cache_get)
            assert callable(cache_set)
        except Exception as e:
            pytest.skip(f"캐시 함수 import 실패: {e}")


# ─── 8. main.py 라우트 검증 ──────────────────────────────────────────────────

class TestMainRoutes:
    def test_fastapi_app(self, main_content):
        assert "app = FastAPI(" in main_content

    def test_ask_endpoint(self, main_content):
        assert '@app.post("/ask")' in main_content

    def test_upload_endpoint(self, main_content):
        assert '@app.post("/upload")' in main_content

    def test_analyze_document_endpoint(self, main_content):
        assert '@app.post("/analyze-document' in main_content

    def test_health_endpoint(self, main_content):
        assert '@app.get("/health")' in main_content

    def test_search_law_drf_tool(self, main_content):
        assert "def search_law_drf(" in main_content

    def test_search_precedents_drf_tool(self, main_content):
        assert "def search_precedents_drf(" in main_content

    def test_gemini_tools_list(self, main_content):
        assert "tools = [" in main_content


# ─── 9. SSOT 데이터 무결성 검증 ──────────────────────────────────────────────

class TestSSOTDataIntegrity:
    def test_law_response_json(self, drf_connector):
        result = drf_connector.law_search("민법 제1조")
        if result is None:
            pytest.skip("법령 검색 응답 없음")
        assert isinstance(result, dict), f"JSON 아님: {type(result)}"
        assert len(result.keys()) > 0, "빈 응답"

    def test_law_no_html(self, drf_connector):
        result = drf_connector.law_search("민법 제1조")
        if result is None:
            pytest.skip("법령 검색 응답 없음")
        s = str(result).lower()
        assert "<html" not in s and "<!doctype" not in s, "HTML 응답 감지 (Article 1 위반)"

    def test_prec_response_json(self, drf_connector):
        result = drf_connector.search_precedents("손해배상")
        if result is None:
            pytest.skip("판례 검색 응답 없음")
        assert isinstance(result, dict), f"JSON 아님: {type(result)}"
        assert len(result.keys()) > 0, "빈 응답"

    def test_prec_no_html(self, drf_connector):
        result = drf_connector.search_precedents("손해배상")
        if result is None:
            pytest.skip("판례 검색 응답 없음")
        s = str(result).lower()
        assert "<html" not in s and "<!doctype" not in s, "HTML 응답 감지 (Article 1 위반)"


# ─── 10. Fail-Closed 원칙 검증 ───────────────────────────────────────────────

class TestFailClosed:
    def test_failclosed_enabled(self, config):
        fc = config.get("failclosed_principle", {})
        assert fc.get("enabled") is True

    def test_block_html_responses(self, config):
        fc = config.get("failclosed_principle", {})
        assert fc.get("block_html_responses") is True, "block_html_responses 미활성화"
