"""Shared data models for the workflow-based agent architecture.

These Pydantic models define the structured data that flows between
workflow executors: Triage → Knowledge Lookup → Question Handler / Ingestion Preview → Formatter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field


# ============================================================================
# Triage Stage
# ============================================================================

class TriageResult(BaseModel):
    """Output of the Triage executor — classifies user intent and extracts metadata."""

    intent: Literal["question", "ingestion", "both"]
    """What the user wants to do."""

    domain: str | None = Field(
        default=None,
        description="Knowledge domain (e.g. 'engineering', 'hr', 'finance')",
    )

    tags: list[str] = Field(
        default_factory=list,
        description="Relevant tags extracted from the user input",
    )

    cleaned_query: str | None = Field(
        default=None,
        description="The user's question, cleaned for knowledge lookup (question / both path)",
    )

    raw_content: str | None = Field(
        default=None,
        description="Raw content to ingest (ingestion / both path)",
    )

    source_url: str | None = Field(
        default=None,
        description="URL submitted by the user, if any",
    )

    has_image: bool = Field(
        default=False,
        description="Whether the user submitted an image",
    )


# ============================================================================
# Knowledge Lookup Stage
# ============================================================================

@dataclass
class SourceReference:
    """A single knowledge source reference with confidence scoring."""

    source_type: str  # "note" or "url"
    title: str
    summary: str
    confidence: float = 1.0
    relevance: float = 1.0
    tags: list[str] = field(default_factory=list)
    # Note-specific
    filename: str | None = None
    domain: str | None = None
    category: str | None = None
    # URL-specific
    url: str | None = None


class LookupResult(BaseModel):
    """Output of the Knowledge Lookup executor."""

    model_config = {"arbitrary_types_allowed": True}

    triage: TriageResult | None = None
    """Pass-through of triage data for downstream executors."""

    matches: list[dict] = Field(default_factory=list)
    """Knowledge matches from search_by_tags, as serializable dicts."""

    match_count: int = 0
    """Number of matches found."""

    has_sufficient_context: bool = False
    """True if enough context exists to likely answer a question confidently."""

    available_tags: list[str] = Field(default_factory=list)
    """Tags that were searched."""


# ============================================================================
# Question Handler Stage
# ============================================================================

class QuestionResult(BaseModel):
    """Output of the Question Handler executor."""

    answer: str = ""
    """The synthesized answer text."""

    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="How confident the answer is based on available sources",
    )

    sources_used: list[dict] = Field(default_factory=list)
    """Source references used to build the answer."""

    suggest_web_search: bool = False
    """True if the agent couldn't answer from existing knowledge."""

    search_query: str | None = None
    """Suggested web search query if suggest_web_search is True."""

    triage: TriageResult | None = None
    """Pass-through for downstream use."""


# ============================================================================
# Ingestion Preview Stage
# ============================================================================

class IngestionPreviewResult(BaseModel):
    """Output of the Ingestion Preview executor."""

    action: Literal["create_note", "update_note", "add_url", "update_context", "skip"]
    """What kind of write operation is proposed."""

    target_path: str = ""
    """File path or URL index that would be modified."""

    preview_content: str = ""
    """Preview of the content that would be written."""

    title: str = ""
    """Title for the new/updated entry."""

    domain: str = "general"
    """Knowledge domain for the entry."""

    tags: list[str] = Field(default_factory=list)
    """Proposed tags."""

    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    relevance: float = Field(default=1.0, ge=0.0, le=1.0)

    related_existing: list[dict] = Field(default_factory=list)
    """Existing knowledge items that are related."""

    requires_review: bool = False
    """True if scores are below thresholds."""

    review_reason: str | None = None
    """Why review is required."""

    triage: TriageResult | None = None
    """Pass-through for downstream use."""


# ============================================================================
# Workflow Output (Response Formatter)
# ============================================================================

class WorkflowOutput(BaseModel):
    """Final output of the workflow, rendered by the UI layer."""

    intent: Literal["question", "ingestion", "both"]
    """Original user intent for UI routing."""

    # Question path results
    question_result: QuestionResult | None = None

    # Ingestion path results
    ingestion_result: IngestionPreviewResult | None = None

    # Shared
    sources: list[dict] = Field(default_factory=list)
    """All source references sorted by confidence, for display."""

    summary: str = ""
    """Human-readable summary of the workflow result."""
