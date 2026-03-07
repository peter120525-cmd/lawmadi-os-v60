"""
Vertex AI Search 커넥터 — law_cache 기반 키워드 매칭을 시맨틱 검색으로 대체.

match_ssot_sources, build_ssot_context, build_cache_context의 Vertex AI Search 버전.
google-cloud-discoveryengine SDK 사용, asyncio.to_thread로 async 래핑.
에러 시 빈 결과 반환 (fail-soft).

추가 기능:
- Ranking API: 검색 결과를 ML 모델로 재정렬하여 관련성 향상
- Check Grounding API: AI 답변이 법률 데이터에 근거하는지 검증
"""

import json
import asyncio
import logging
from typing import List, Dict, Optional, Tuple

from core.constants import (
    VERTEX_SEARCH_PROJECT_ID,
    VERTEX_SEARCH_LOCATION,
    VERTEX_SEARCH_DATA_STORE_ID,
    VERTEX_SEARCH_ENGINE_ID,
)

logger = logging.getLogger("LawmadiOS.VertexSearch")

# Lazy-init SDK clients (모듈 임포트 시 초기화하지 않음)
_search_client = None
_serving_config = None
_rank_client = None
_grounding_client = None


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


def _get_rank_client():
    """Discovery Engine RankServiceClient 싱글턴."""
    global _rank_client
    if _rank_client is not None:
        return _rank_client

    from google.cloud import discoveryengine_v1 as discoveryengine

    _rank_client = discoveryengine.RankServiceClient()
    logger.info("✅ Vertex AI Rank client initialized")
    return _rank_client


def _get_grounding_client():
    """Discovery Engine GroundedGenerationServiceClient 싱글턴."""
    global _grounding_client
    if _grounding_client is not None:
        return _grounding_client

    from google.cloud import discoveryengine_v1 as discoveryengine

    _grounding_client = discoveryengine.GroundedGenerationServiceClient()
    logger.info("✅ Vertex AI Grounding client initialized")
    return _grounding_client


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
        content_search_spec=discoveryengine.SearchRequest.ContentSearchSpec(
            extractive_content_spec=discoveryengine.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
                max_extractive_answer_count=3,
                max_extractive_segment_count=3,
                return_extractive_segment_score=True,
            ),
            snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
                return_snippet=True,
            ),
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

        content = doc_data.get("content", "")

        # Extractive Answers & Segments 추출
        extractive_answers = []
        extractive_segments = []
        try:
            derived = getattr(doc, "derived_struct_data", None)
            if derived:
                derived_dict = dict(derived) if hasattr(derived, '__iter__') else {}
                for ea in derived_dict.get("extractive_answers", []):
                    ea_content = ea.get("content", "") if isinstance(ea, dict) else getattr(ea, "content", "")
                    if ea_content:
                        extractive_answers.append(ea_content.strip())
                for es in derived_dict.get("extractive_segments", []):
                    es_content = es.get("content", "") if isinstance(es, dict) else getattr(es, "content", "")
                    es_score = es.get("relevance_score", 0) if isinstance(es, dict) else getattr(es, "relevance_score", 0)
                    if es_content:
                        extractive_segments.append({
                            "content": es_content.strip(),
                            "score": float(es_score or 0),
                        })
        except Exception as e:
            logger.debug(f"[VertexSearch] extractive 파싱 실패 (무시): {e}")

        # Snippet 추출
        snippet = ""
        try:
            derived = getattr(doc, "derived_struct_data", None)
            if derived:
                derived_dict = dict(derived) if hasattr(derived, '__iter__') else {}
                snippets = derived_dict.get("snippets", [])
                if snippets:
                    s0 = snippets[0]
                    snippet = s0.get("snippet", "") if isinstance(s0, dict) else getattr(s0, "snippet", "")
        except Exception:
            pass

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
            "_content": content,
            "extractive_answers": extractive_answers[:3],
            "extractive_segments": extractive_segments[:3],
            "snippet": snippet,
        })

    # ─── Ranking API로 재정렬 ───
    if results and len(results) >= 2:
        results = _rerank_results(query, results)

    logger.info(f"[VertexSearch] '{query[:30]}...' → {len(results)}건 검색 완료 (ranked)")
    return results


def _rerank_results(query: str, results: List[Dict]) -> List[Dict]:
    """Ranking API로 검색 결과를 ML 모델 기반 재정렬."""
    from google.cloud import discoveryengine_v1 as discoveryengine

    try:
        rank_client = _get_rank_client()
        ranking_config = (
            f"projects/{VERTEX_SEARCH_PROJECT_ID}"
            f"/locations/{VERTEX_SEARCH_LOCATION}"
            f"/rankingConfigs/default_ranking_config"
        )

        records = []
        for i, r in enumerate(results):
            title = f"{r['law']} ({r['label']})"
            content = r.get("_content", "") or title
            records.append(discoveryengine.RankingRecord(
                id=str(i),
                title=title,
                content=content[:2000],
            ))

        request = discoveryengine.RankRequest(
            ranking_config=ranking_config,
            query=query,
            records=records,
            top_n=len(records),
        )

        response = rank_client.rank(request)

        # 재정렬된 순서로 결과 재배치
        reranked = []
        for record in response.records:
            idx = int(record.id)
            item = results[idx].copy()
            item["score"] = record.score
            reranked.append(item)

        logger.info(f"[Ranking] {len(reranked)}건 재정렬 완료")
        return reranked

    except Exception as e:
        logger.warning(f"[Ranking] 재정렬 실패 (원본 순서 유지): {e}")
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

            # Extractive Answers 우선 (가장 관련성 높은 원문 구절)
            for ea in s.get("extractive_answers", []):
                lines.append(f"  ★ 핵심 원문: {ea}")

            # Extractive Segments (주변 문맥 포함 구절)
            for es in s.get("extractive_segments", []):
                seg_text = es.get("content", "") if isinstance(es, dict) else es
                if seg_text:
                    lines.append(f"  📄 관련 구절: {seg_text}")

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


# ─── Check Grounding API ─────────────────────────────────────

def _sync_check_grounding(
    answer_text: str,
    facts: List[Dict],
    citation_threshold: float = 0.6,
) -> Dict:
    """동기 Check Grounding API 호출 — 답변이 법률 데이터에 근거하는지 검증."""
    from google.cloud import discoveryengine_v1 as discoveryengine

    grounding_client = _get_grounding_client()

    grounding_config = (
        f"projects/{VERTEX_SEARCH_PROJECT_ID}"
        f"/locations/{VERTEX_SEARCH_LOCATION}"
        f"/groundingConfigs/default_grounding_config"
    )

    grounding_facts = []
    for f in facts:
        grounding_facts.append(discoveryengine.GroundingFact(
            fact_text=f.get("text", "")[:10000],
            attributes={"source": f.get("source", "unknown")},
        ))

    request = discoveryengine.CheckGroundingRequest(
        grounding_config=grounding_config,
        answer_candidate=answer_text[:10000],
        facts=grounding_facts,
        grounding_spec=discoveryengine.CheckGroundingSpec(
            citation_threshold=citation_threshold,
        ),
    )

    response = grounding_client.check_grounding(request)

    claims = []
    for claim in response.claims:
        claims.append({
            "claim_text": claim.claim_text,
            "grounding_check_required": claim.grounding_check_required
                if hasattr(claim, "grounding_check_required") else None,
            "citation_indices": [idx for idx in (claim.citation_indices or [])],
        })

    return {
        "support_score": response.support_score,
        "cited_chunks": [
            {"chunk_text": c.chunk_text if hasattr(c, "chunk_text") else str(c)}
            for c in (response.cited_chunks or [])
        ],
        "claims": claims,
        "total_claims": len(claims),
        "grounded_claims": sum(
            1 for c in claims if c["citation_indices"]
        ),
    }


async def check_grounding(
    answer_text: str,
    rag_sources: List[Dict],
    citation_threshold: float = 0.6,
) -> Dict:
    """
    Check Grounding API — AI 답변이 검색된 법률 데이터에 근거하는지 검증.

    Args:
        answer_text: Stage 3에서 생성된 최종 답변 텍스트
        rag_sources: Stage 1 검색 결과 (search_legal_documents 반환값)
        citation_threshold: 인용 판정 임계값 (0.0~1.0, 기본 0.6)

    Returns:
        {
            "support_score": float,  # 전체 근거 점수 (0.0~1.0)
            "total_claims": int,     # 전체 주장 수
            "grounded_claims": int,  # 근거 확인된 주장 수
            "claims": [...],         # 개별 주장 상세
        }
    """
    if not answer_text or not rag_sources:
        return {"support_score": 1.0, "total_claims": 0, "grounded_claims": 0, "claims": []}

    # RAG 검색 결과를 GroundingFact 형식으로 변환
    facts = []
    for src in rag_sources:
        parts = []
        law_name = src.get("law", "")
        label = src.get("label", "")
        if law_name:
            parts.append(f"법률: {law_name}")
        # Extractive Answers를 최우선 근거로 포함
        for ea in src.get("extractive_answers", []):
            parts.append(ea)
        for es in src.get("extractive_segments", []):
            seg_text = es.get("content", "") if isinstance(es, dict) else es
            if seg_text:
                parts.append(seg_text)
        for art in src.get("key_article_texts", [])[:10]:
            parts.append(art)
        for prec in src.get("key_precedents", [])[:5]:
            parts.append(f"판례: {prec}")
        if parts:
            facts.append({
                "text": "\n".join(parts),
                "source": f"{law_name} ({label})",
            })

    if not facts:
        return {"support_score": 1.0, "total_claims": 0, "grounded_claims": 0, "claims": []}

    try:
        result = await asyncio.to_thread(
            _sync_check_grounding, answer_text, facts, citation_threshold
        )
        logger.info(
            f"[CheckGrounding] support_score={result['support_score']:.2f}, "
            f"grounded={result['grounded_claims']}/{result['total_claims']}"
        )
        return result
    except Exception as e:
        logger.warning(f"[CheckGrounding] API 호출 실패 (검증 스킵): {e}")
        return {"support_score": -1.0, "total_claims": 0, "grounded_claims": 0, "claims": [], "error": str(e)}
