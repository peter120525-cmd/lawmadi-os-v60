"""Pydantic request/response models for MCP parameter descriptions."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# /ask
# ---------------------------------------------------------------------------

class CurrentLeader(BaseModel):
    """Leader context for handoff/deliberation."""
    model_config = ConfigDict(extra="ignore")
    name: str = Field(default="", description="Leader name (e.g. '담우')")
    specialty: str = Field(default="", description="Leader specialty (e.g. '노동법')")


class AskRequest(BaseModel):
    """Legal question request body."""
    model_config = ConfigDict(extra="ignore")
    query: str = Field(
        ...,
        description="Legal question in Korean or English (max 2000 chars). "
                    "Example: '부당해고를 당했는데 어떻게 해야 하나요?'",
    )
    history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Conversation history (max 6 recent turns). "
                    "Each item: {role: 'user'|'model', content: '...'}",
    )
    lang: str = Field(
        default="",
        description="Response language: 'ko' (Korean) or 'en' (English). "
                    "Auto-detected from query if omitted.",
    )
    current_leader: Optional[CurrentLeader] = Field(
        default=None,
        description="Current leader context for handoff/deliberation.",
    )
    is_first_question: bool = Field(
        default=True,
        description="Whether this is the user's first question in the session.",
    )


# ---------------------------------------------------------------------------
# /ask-stream
# ---------------------------------------------------------------------------

class AskStreamRequest(BaseModel):
    """SSE streaming legal question request body."""
    model_config = ConfigDict(extra="ignore")
    query: str = Field(
        ...,
        description="Legal question in Korean or English (max 2000 chars).",
    )
    history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Conversation history (max 6 recent turns).",
    )
    lang: str = Field(
        default="",
        description="Response language: 'ko' or 'en'. Auto-detected if omitted.",
    )
    mode: str = Field(
        default="general",
        description="Stream mode: 'general' (default), 'leader_chat', or 'expert'.",
    )
    current_leader: Optional[CurrentLeader] = Field(
        default=None,
        description="Current leader context for handoff.",
    )
    leader_id: str = Field(
        default="",
        description="Specific leader ID (e.g. 'L01') for 1:1 chat mode.",
    )
    is_first_question: bool = Field(
        default=True,
        description="Whether this is the user's first question in the session.",
    )


# ---------------------------------------------------------------------------
# /ask-expert
# ---------------------------------------------------------------------------

class AskExpertRequest(BaseModel):
    """Expert mode (4-Stage Legal Pipeline) request body."""
    model_config = ConfigDict(extra="ignore")
    query: str = Field(
        ...,
        description="Legal question for expert analysis (max 2000 chars).",
    )
    original_response: str = Field(
        default="",
        description="Original /ask response for deeper expert analysis.",
    )
    lang: str = Field(
        default="",
        description="Response language: 'ko' or 'en'. Auto-detected if omitted.",
    )


# ---------------------------------------------------------------------------
# /api/chat-leader
# ---------------------------------------------------------------------------

class ChatLeaderRequest(BaseModel):
    """1:1 leader chat request body."""
    model_config = ConfigDict(extra="ignore")
    leader_id: str = Field(
        ...,
        description="Leader identifier (e.g. 'L01', 'L32', 'CCO'). "
                    "Use GET /api/leaders to see all available leaders.",
    )
    query: str = Field(
        ...,
        description="Question to ask the specific leader (max 2000 chars).",
    )
    history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Conversation history with this leader.",
    )


# ---------------------------------------------------------------------------
# /suggest-questions
# ---------------------------------------------------------------------------

class SuggestQuestionsRequest(BaseModel):
    """Follow-up question suggestion request body."""
    model_config = ConfigDict(extra="ignore")
    query: str = Field(
        ...,
        description="Current user question (max 500 chars).",
    )
    leader: str = Field(
        default="",
        description="Current leader name (e.g. '담우').",
    )
    specialty: str = Field(
        default="",
        description="Current leader's legal specialty (e.g. '노동법').",
    )
