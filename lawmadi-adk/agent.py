"""
Lawmadi OS ADK — 루트 에이전트 정의.

Phase 1: 단일 Agent + FunctionTools로 /ask 기능 재현.
ADK CLI: `adk web` 또는 `adk run lawmadi-adk`
배포: `adk deploy agent_engine` → Vertex AI Agent Engine
"""

from google.adk.agents import Agent

from tools.classify import classify_query
from tools.drf_tools import (
    search_law_drf,
    search_precedents_drf,
    get_law_articles,
    search_legal_term_drf,
    search_admin_rules_drf,
    search_constitutional_drf,
    search_ordinance_drf,
    search_expc_drf,
    search_treaty_drf,
)
from tools.rag_tools import get_leader_context, get_leader_law_boost
from tools.verify import verify_law_references, strip_unverified_sentences
from prompts.system_instruction import SYSTEM_INSTRUCTION


root_agent = Agent(
    name="lawmadi_os",
    model="gemini-2.5-flash",
    description=(
        "Lawmadi OS — 대한민국 법률 의사결정 지원 시스템. "
        "59명의 전문 법률 리더가 한국법 전 분야를 지원합니다."
    ),
    instruction=SYSTEM_INSTRUCTION,
    tools=[
        # 1. 질문 분류
        classify_query,
        # 2. 리더 컨텍스트 (LAW_BOOST + 페르소나)
        get_leader_context,
        get_leader_law_boost,
        # 3. DRF 법률 검색 (SSOT 9개 소스)
        search_law_drf,
        search_precedents_drf,
        get_law_articles,
        search_legal_term_drf,
        search_admin_rules_drf,
        search_constitutional_drf,
        search_ordinance_drf,
        search_expc_drf,
        search_treaty_drf,
        # 4. 법률 인용 검증
        verify_law_references,
        strip_unverified_sentences,
    ],
)
