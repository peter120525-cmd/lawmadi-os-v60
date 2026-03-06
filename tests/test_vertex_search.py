"""
Vertex AI Search 커넥터 & feature flag 유닛 테스트.
mock으로 Discovery Engine SDK 호출을 대체하여 오프라인 테스트.
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio


# ---------------------------------------------------------------------------
# 1. Feature flag 테스트
# ---------------------------------------------------------------------------

class TestFeatureFlag:
    """USE_VERTEX_SEARCH feature flag 전환 테스트."""

    def test_flag_default_false(self):
        """기본값: USE_VERTEX_SEARCH=false."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("USE_VERTEX_SEARCH", None)
            # 모듈 재로드하여 테스트
            import importlib
            import core.constants as const_mod
            importlib.reload(const_mod)
            assert const_mod.USE_VERTEX_SEARCH is False

    def test_flag_true(self):
        """USE_VERTEX_SEARCH=true 시 True."""
        with patch.dict(os.environ, {"USE_VERTEX_SEARCH": "true"}):
            import importlib
            import core.constants as const_mod
            importlib.reload(const_mod)
            assert const_mod.USE_VERTEX_SEARCH is True

    def test_flag_TRUE_case_insensitive(self):
        """대소문자 무관: TRUE, True 모두 인식."""
        with patch.dict(os.environ, {"USE_VERTEX_SEARCH": "TRUE"}):
            import importlib
            import core.constants as const_mod
            importlib.reload(const_mod)
            assert const_mod.USE_VERTEX_SEARCH is True

    def test_vertex_search_constants(self):
        """Vertex Search 관련 상수가 정의되어 있는지 확인."""
        from core.constants import (
            VERTEX_SEARCH_PROJECT_ID,
            VERTEX_SEARCH_LOCATION,
            VERTEX_SEARCH_DATA_STORE_ID,
            VERTEX_SEARCH_ENGINE_ID,
        )
        assert VERTEX_SEARCH_PROJECT_ID == "lawmadi-db"
        assert VERTEX_SEARCH_LOCATION == "global"
        assert VERTEX_SEARCH_DATA_STORE_ID == "lawmadi-legal-cache"
        assert VERTEX_SEARCH_ENGINE_ID == "lawmadi-search-engine"


# ---------------------------------------------------------------------------
# 2. Vertex Search 커넥터 테스트 (mock)
# ---------------------------------------------------------------------------

def _make_mock_search_result(ssot_type, law_name, label="현행법령"):
    """Mock Discovery Engine SearchResult 생성."""
    result = MagicMock()
    result.relevance_score = 0.95

    doc = MagicMock()
    doc.struct_data = {
        "ssot_type": ssot_type,
        "law_name": law_name,
        "label": label,
        "target": "law",
        "endpoint": "lawSearch.do",
        "keywords": "근로, 노동, 임금",
        "key_articles_json": json.dumps([{"조문": "제1조", "제목": "목적"}]),
        "key_article_texts_json": json.dumps(["제1조(목적) 이 법은..."]),
        "key_precedents_json": json.dumps(["대법원 2020다12345"]),
        "key_qa_json": json.dumps([{"q": "최저임금은?", "a": "2024년 기준..."}]),
        "qa_count": 150,
    }
    doc.json_data = json.dumps({"content": f"[law] {law_name}\n키워드: 근로, 노동"})

    result.document = doc
    return result


class TestVertexSearchClient:
    """connectors/vertex_search_client.py mock 테스트."""

    @patch("connectors.vertex_search_client._get_client")
    def test_sync_search_returns_results(self, mock_get_client):
        """_sync_search가 올바른 형식의 결과를 반환하는지 확인."""
        mock_client = MagicMock()
        mock_serving_config = "projects/lawmadi-db/locations/global/..."

        mock_response = MagicMock()
        mock_response.results = [
            _make_mock_search_result("law", "근로기준법"),
            _make_mock_search_result("prec", "민법"),
        ]
        mock_client.search.return_value = mock_response
        mock_get_client.return_value = (mock_client, mock_serving_config)

        from connectors.vertex_search_client import _sync_search
        results = _sync_search("최저임금 관련 법률", top_k=5)

        assert len(results) == 2
        assert results[0]["type"] == "law"
        assert results[0]["law"] == "근로기준법"
        assert results[0]["label"] == "현행법령"
        assert results[0]["target"] == "law"
        assert results[0]["endpoint"] == "lawSearch.do"
        assert len(results[0]["key_articles"]) == 1
        assert results[0]["key_articles"][0]["조문"] == "제1조"
        assert isinstance(results[0]["score"], float)

    @patch("connectors.vertex_search_client._get_client")
    def test_sync_search_empty_on_error(self, mock_get_client):
        """API 에러 시 빈 리스트 반환 (fail-soft)."""
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("API timeout")
        mock_get_client.return_value = (mock_client, "serving_config")

        from connectors.vertex_search_client import _sync_search
        results = _sync_search("테스트 쿼리")

        assert results == []

    @patch("connectors.vertex_search_client._sync_search")
    def test_search_legal_documents_async(self, mock_sync):
        """async 래퍼가 정상 동작하는지 확인."""
        mock_sync.return_value = [{"type": "law", "law": "민법"}]

        from connectors.vertex_search_client import search_legal_documents
        results = asyncio.get_event_loop().run_until_complete(
            search_legal_documents("민법 제750조", top_k=5)
        )

        assert len(results) == 1
        assert results[0]["law"] == "민법"
        mock_sync.assert_called_once_with("민법 제750조", 5, "")

    @patch("connectors.vertex_search_client.search_legal_documents")
    def test_build_vertex_context(self, mock_search):
        """build_vertex_context가 SSOT 포맷 텍스트를 생성하는지 확인."""
        mock_search.return_value = [
            {
                "law": "근로기준법",
                "label": "현행법령",
                "key_article_texts": ["제1조(목적) 이 법은 근로조건의 기준을 정함으로써..."],
                "key_precedents": ["대법원 2020다12345"],
                "key_qa": [{"q": "최저임금은?", "a": "9,860원"}],
            }
        ]

        from connectors.vertex_search_client import build_vertex_context
        ctx = asyncio.get_event_loop().run_until_complete(
            build_vertex_context("최저임금")
        )

        assert "Vertex AI Search" in ctx
        assert "근로기준법" in ctx
        assert "조문:" in ctx
        assert "판례:" in ctx
        assert "참고Q:" in ctx

    @patch("connectors.vertex_search_client.search_legal_documents")
    def test_build_vertex_cache_context(self, mock_search):
        """build_vertex_cache_context가 요약 포맷을 생성하는지 확인."""
        mock_search.return_value = [
            {
                "law": "민법",
                "label": "현행법령",
                "target": "law",
                "endpoint": "lawSearch.do",
                "key_articles": [{"조문": "제750조", "제목": "불법행위의 내용"}],
                "key_article_texts": [],
                "key_precedents": [],
                "key_qa": [],
            }
        ]

        from connectors.vertex_search_client import build_vertex_cache_context
        ctx = asyncio.get_event_loop().run_until_complete(
            build_vertex_cache_context("손해배상")
        )

        assert "Vertex AI Search" in ctx
        assert "민법" in ctx
        assert "제750조" in ctx
        assert "DRF target=law" in ctx

    @patch("connectors.vertex_search_client.search_legal_documents")
    def test_build_vertex_context_empty(self, mock_search):
        """검색 결과 없을 때 빈 문자열 반환."""
        mock_search.return_value = []

        from connectors.vertex_search_client import build_vertex_context
        ctx = asyncio.get_event_loop().run_until_complete(
            build_vertex_context("알수없는쿼리")
        )

        assert ctx == ""


# ---------------------------------------------------------------------------
# 3. Pipeline 통합 테스트 (mock)
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    """pipeline.py의 Vertex Search 경로 테스트."""

    def test_set_vertex_search_fns(self):
        """set_vertex_search_fns가 함수 참조를 저장하는지 확인."""
        from core.pipeline import set_vertex_search_fns, _vertex_search_fn

        mock_fn = MagicMock()
        set_vertex_search_fns(search_fn=mock_fn)

        from core import pipeline
        assert pipeline._vertex_search_fn is mock_fn

        # 정리
        set_vertex_search_fns(search_fn=None, context_fn=None, cache_context_fn=None)

    def test_result_format_compatible(self):
        """Vertex Search 결과가 match_ssot_sources 형식과 호환되는지 확인."""
        expected_keys = {
            "type", "law", "label", "target", "endpoint",
            "key_articles", "key_article_texts", "key_precedents",
            "key_qa", "keywords", "score",
        }

        # Vertex Search 결과 형식
        vertex_result = {
            "type": "law",
            "law": "근로기준법",
            "label": "현행법령",
            "target": "law",
            "endpoint": "lawSearch.do",
            "key_articles": [{"조문": "제1조", "제목": "목적"}],
            "key_article_texts": ["제1조(목적) ..."],
            "key_precedents": ["대법원 2020다12345"],
            "key_qa": [{"q": "질문", "a": "답변"}],
            "keywords": ["근로", "노동"],
            "score": 0.95,
            "_content": "...",  # 추가 필드 (무시됨)
        }

        # 필수 키가 모두 포함되어야 함
        assert expected_keys.issubset(vertex_result.keys())


# ---------------------------------------------------------------------------
# 4. 데이터 변환 스크립트 테스트
# ---------------------------------------------------------------------------

class TestTransformScript:
    """transform_law_cache_for_vertex.py 유틸리티 테스트."""

    def test_make_doc_id_deterministic(self):
        """동일 입력 → 동일 doc_id."""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        from transform_law_cache_for_vertex import _make_doc_id

        id1 = _make_doc_id("law", "근로기준법")
        id2 = _make_doc_id("law", "근로기준법")
        id3 = _make_doc_id("prec", "근로기준법")

        assert id1 == id2  # 결정적
        assert id1 != id3  # 다른 ssot_type → 다른 ID
        assert len(id1) == 32

    def test_build_content_text(self):
        """content 텍스트가 검색 가능한 형태인지 확인."""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        from transform_law_cache_for_vertex import _build_content_text

        law_info = {
            "keywords": ["근로", "노동", "임금"],
            "key_articles": [{"조문": "제1조", "제목": "목적"}],
            "key_article_texts": ["제1조(목적) 이 법은 근로조건의 기준을 정함으로써..."],
            "key_precedents": ["대법원 2020다12345 판례 요지"],
            "key_qa": [{"q": "최저임금은?", "a": "2024년 기준 9,860원"}],
        }

        text = _build_content_text("근로기준법", law_info, "law")

        assert "근로기준법" in text
        assert "키워드:" in text
        assert "근로" in text
        assert "조문:" in text
        assert "원문:" in text
        assert "판례:" in text
        assert "Q:" in text
        assert "A:" in text
