"""
Vertex AI Search 커넥터 — law_cache 기반 키워드 매칭을 시맨틱 검색으로 대체.

match_ssot_sources, build_ssot_context, build_cache_context의 Vertex AI Search 버전.
google-cloud-discoveryengine SDK 사용, asyncio.to_thread로 async 래핑.
에러 시 빈 결과 반환 (fail-soft).
"""

import json
import asyncio
import logging
from typing import List, Dict, Optional

from core.constants import (
    VERTEX_SEARCH_PROJECT_ID,
    VERTEX_SEARCH_LOCATION,
    VERTEX_SEARCH_DATA_STORE_ID,
    VERTEX_SEARCH_ENGINE_ID,
)

logger = logging.getLogger("LawmadiOS.VertexSearch")

# Lazy-init SDK client (모듈 임포트 시 초기화하지 않음)
_search_client = None
_serving_config = None


def _get_client():
    """Discovery Engine SearchServiceClient 싱글턴."""
    global _search_client, _serving_config
    if _search_client is not None:
        return _search_client, _serving_config

    from google.cloud import discoveryengine_v1 as discoveryengine

    _search_client = discoveryengine.SearchServiceClient()
    _serving_config = (
        f"projects/{VERTEX_SEARCH_PROJECT_ID}"
        f"/locations/{VERTEX_SEARCH_LOCATION}"
        f"/collections/default_collection"
        f"/engines/{VERTEX_SEARCH_ENGINE_ID}"
        f"/servingConfigs/default_search"
    )
    logger.info(f"✅ Vertex AI Search client initialized: {VERTEX_SEARCH_ENGINE_ID}")
    return _search_client, _serving_config


def _sync_search(query: str, top_k: int = 10, ssot_type_filter: str = "") -> List[Dict]:
    """동기 Vertex AI Search 호출 → match_ssot_sources 호환 결과 반환."""
    from google.cloud import discoveryengine_v1 as discoveryengine

    client, serving_config = _get_client()

    request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query=query,
        page_size=top_k,
        query_expansion_spec=discoveryengine.SearchRequest.QueryExpansionSpec(
            condition=discoveryengine.SearchRequest.QueryExpansionSpec.Condition.AUTO,
        ),
        spell_correction_spec=discoveryengine.SearchRequest.SpellCorrectionSpec(
            mode=discoveryengine.SearchRequest.SpellCorrectionSpec.Mode.AUTO,
        ),
    )

    # ssot_type 필터 (선택적)
    if ssot_type_filter:
        request.filter = f'ssot_type: ANY("{ssot_type_filter}")'

    try:
        response = client.search(request)
    except Exception as e:
        logger.warning(f"[VertexSearch] API 호출 실패: {e}")
        return []

    results = []
    for result in response.results:
        doc = result.document

        # 데이터 추출: struct_data 또는 json_data에서 (oneof)
        doc_data = {}
        if doc.struct_data:
            doc_data = dict(doc.struct_data)
        if doc.json_data:
            try:
                parsed = json.loads(doc.json_data)
                doc_data.update(parsed)
            except (json.JSONDecodeError, TypeError):
                pass

        # key_articles, key_article_texts, key_precedents, key_qa를 JSON 복원
        key_articles = []
        key_article_texts = []
        key_precedents = []
        key_qa = []
        try:
            key_articles = json.loads(doc_data.get("key_articles_json", "[]"))
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            key_article_texts = json.loads(doc_data.get("key_article_texts_json", "[]"))
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            key_precedents = json.loads(doc_data.get("key_precedents_json", "[]"))
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            key_qa = json.loads(doc_data.get("key_qa_json", "[]"))
        except (json.JSONDecodeError, TypeError):
            pass

        keywords_str = doc_data.get("keywords", "")
        keywords = [k.strip() for k in keywords_str.split(",") if k.strip()] if keywords_str else []

        results.append({
            "type": doc_data.get("ssot_type", ""),
            "law": doc_data.get("law_name", ""),
            "label": doc_data.get("label", ""),
            "target": doc_data.get("target", ""),
            "endpoint": doc_data.get("endpoint", ""),
            "key_articles": key_articles[:20],
            "key_article_texts": key_article_texts[:20],
            "key_precedents": key_precedents[:10],
            "key_qa": key_qa[:5],
            "keywords": keywords[:5],
            "score": float(getattr(result, "relevance_score", 0) or 0),
            "_content": doc_data.get("content", ""),  # 디버깅용
        })

    logger.info(f"[VertexSearch] '{query[:30]}...' → {len(results)}건 검색 완료")
    return results


# ─── Async wrappers ───────────────────────────────────────────

async def search_legal_documents(
    query: str, top_k: int = 8, ssot_type_filter: str = ""
) -> List[Dict]:
    """
    시맨틱 검색 — match_ssot_sources 대체.
    반환 형식은 match_ssot_sources와 동일.
    """
    try:
        return await asyncio.to_thread(_sync_search, query, top_k, ssot_type_filter)
    except Exception as e:
        logger.warning(f"[VertexSearch] search_legal_documents 실패: {e}")
        return []


async def build_vertex_context(query: str, top_k: int = 30) -> str:
    """
    build_ssot_context 대체 — 법률명+조문원문+판례요지+Q&A.
    """
    try:
        sources = await search_legal_documents(query, top_k=top_k)
        if not sources:
            return ""

        lines = ["[SSOT 매칭 결과 — Vertex AI Search]"]
        for s in sources:
            lines.append(f"\n■ {s['law']} ({s['label']})")
            for art in s.get("key_article_texts", [])[:20]:
                lines.append(f"  조문: {art}")
            for prec in s.get("key_precedents", [])[:10]:
                lines.append(f"  판례: {prec}")
            for qa in s.get("key_qa", [])[:5]:
                lines.append(f"  참고Q: {qa.get('q', '')}")
                lines.append(f"  참고A: {qa.get('a', '')}")

        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"[VertexSearch] build_vertex_context 실패: {e}")
        return ""


async def build_vertex_cache_context(query: str, top_k: int = 30) -> str:
    """
    build_cache_context 대체 — 요약 컨텍스트.
    """
    try:
        sources = await search_legal_documents(query, top_k=top_k)
        if not sources:
            return ""

        lines = ["[사전 캐시 매칭 결과 — Vertex AI Search]"]
        for s in sources:
            arts = s.get("key_articles", [])
            art_strs = [
                f"{a['조문']}({a.get('제목', '')})"
                for a in arts if a.get("조문")
            ]
            lines.append(
                f"• [{s['label']}] {s['law']}: "
                f"핵심 조문={', '.join(art_strs) if art_strs else '없음'} "
                f"(DRF target={s['target']}, endpoint={s['endpoint']})"
            )
        lines.append("[위 캐시를 참고하되, 정확한 조문은 반드시 DRF 도구로 실시간 검증하세요]")
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"[VertexSearch] build_vertex_cache_context 실패: {e}")
        return ""
