"""Main workflow graph.

Builds the WorkflowBuilder graph that wires together:

    User text (str)
        → TriageExecutor          (LLM: classify intent, extract tags)
        → KnowledgeLookupExecutor (deterministic: query knowledge indexes)
        ── conditional routing ──
        → QuestionHandlerExecutor (LLM: answer question from context)
        → IngestionPreviewExecutor(LLM: propose knowledge-base write)
        ── merge ──
        → ResponseFormatterExecutor (deterministic: format WorkflowOutput)

Routing rules (based on TriageResult.intent):
  • "question"  → QuestionHandler only
  • "ingestion" → IngestionPreview only
  • "both"      → both handlers fire (two WorkflowOutput objects are yielded)
  • unknown     → falls through to QuestionHandler (safe default)
"""

import logging

from agent_framework import Workflow, WorkflowBuilder

from app.agents.triage import TriageExecutor
from app.agents.question_handler import QuestionHandlerExecutor
from app.agents.ingestion_preview import IngestionPreviewExecutor
from app.executors.knowledge_lookup import KnowledgeLookupExecutor
from app.executors.response_formatter import ResponseFormatterExecutor
from app.models import LookupResult

logger = logging.getLogger("workflow.main")


# ── Edge conditions ────────────────────────────────────────────────────────
def _route_to_question(lookup_result: LookupResult) -> bool:
    """Route to QuestionHandler when intent is 'question' or 'both'."""
    intent = lookup_result.triage.intent if lookup_result.triage else "question"
    return intent in ("question", "both")


def _route_to_ingestion(lookup_result: LookupResult) -> bool:
    """Route to IngestionPreview when intent is 'ingestion' or 'both'."""
    intent = lookup_result.triage.intent if lookup_result.triage else "question"
    return intent in ("ingestion", "both")


# ── Workflow factory ───────────────────────────────────────────────────────
def build_workflow() -> Workflow:
    """Construct and return the main agent workflow.

    Returns an immutable Workflow ready to be executed via ``workflow.run(user_input)``.
    """
    logger.info("[WORKFLOW] Building main workflow graph")

    workflow = (
        WorkflowBuilder()
        # Register executor factories (lazy instantiation per workflow run)
        .register_executor(lambda: TriageExecutor(id="triage"), name="triage")
        .register_executor(lambda: KnowledgeLookupExecutor(id="knowledge_lookup"), name="knowledge_lookup")
        .register_executor(lambda: QuestionHandlerExecutor(id="question_handler"), name="question_handler")
        .register_executor(lambda: IngestionPreviewExecutor(id="ingestion_preview"), name="ingestion_preview")
        .register_executor(lambda: ResponseFormatterExecutor(id="response_formatter"), name="response_formatter")
        # Set the entry point
        .set_start_executor("triage")
        # Triage → KnowledgeLookup (always)
        .add_edge("triage", "knowledge_lookup")
        # KnowledgeLookup → QuestionHandler  (intent ∈ {question, both})
        .add_edge("knowledge_lookup", "question_handler", condition=_route_to_question)
        # KnowledgeLookup → IngestionPreview (intent ∈ {ingestion, both})
        .add_edge("knowledge_lookup", "ingestion_preview", condition=_route_to_ingestion)
        # Both handlers → ResponseFormatter (merge into WorkflowOutput)
        .add_edge("question_handler", "response_formatter")
        .add_edge("ingestion_preview", "response_formatter")
        .build()
    )

    logger.info("[WORKFLOW] Main workflow graph built successfully")
    return workflow
