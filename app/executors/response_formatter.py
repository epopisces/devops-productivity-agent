"""Response Formatter Executor.

Fan-in executor that merges outputs from the Question Handler and/or
Ingestion Preview paths into a single WorkflowOutput for the UI layer.
"""

import logging
from typing import Any

from agent_framework import Executor, WorkflowContext, handler
from typing_extensions import Never

from app.models import (
    QuestionResult,
    IngestionPreviewResult,
    WorkflowOutput,
)

logger = logging.getLogger("workflow.response_formatter")


class ResponseFormatterExecutor(Executor):
    """Merge fan-in results into a unified WorkflowOutput.

    When the intent is "both", this executor receives a list containing
    results from both the Question Handler and Ingestion Preview executors.
    For single-intent flows, it wraps the single result.
    """

    @handler
    async def handle_list(
        self,
        results: list[Any],
        ctx: WorkflowContext[Never, WorkflowOutput],
    ) -> None:
        """Handle fan-in: list of results from parallel branches."""
        logger.info(f"[EXECUTOR] ResponseFormatter: received {len(results)} fan-in results")
        await self._merge_and_output(results, ctx)

    @handler
    async def handle_question(
        self,
        result: QuestionResult,
        ctx: WorkflowContext[Never, WorkflowOutput],
    ) -> None:
        """Handle single question result (question-only intent)."""
        logger.info("[EXECUTOR] ResponseFormatter: received QuestionResult")
        await self._merge_and_output([result], ctx)

    @handler
    async def handle_ingestion(
        self,
        result: IngestionPreviewResult,
        ctx: WorkflowContext[Never, WorkflowOutput],
    ) -> None:
        """Handle single ingestion result (ingestion-only intent)."""
        logger.info("[EXECUTOR] ResponseFormatter: received IngestionPreviewResult")
        await self._merge_and_output([result], ctx)

    async def _merge_and_output(
        self,
        results: list[Any],
        ctx: WorkflowContext[Never, WorkflowOutput],
    ) -> None:
        """Merge results into a WorkflowOutput and yield it."""
        question_result: QuestionResult | None = None
        ingestion_result: IngestionPreviewResult | None = None
        all_sources: list[dict] = []
        intent = "question"  # default

        for r in results:
            if isinstance(r, QuestionResult):
                question_result = r
                all_sources.extend(r.sources_used)
                if r.triage:
                    intent = r.triage.intent
            elif isinstance(r, IngestionPreviewResult):
                ingestion_result = r
                all_sources.extend(r.related_existing)
                if r.triage:
                    intent = r.triage.intent

        # Deduplicate and sort sources by confidence descending
        seen = set()
        unique_sources: list[dict] = []
        for s in all_sources:
            key = s.get("title", "") + s.get("url", "") + s.get("filename", "")
            if key not in seen:
                seen.add(key)
                unique_sources.append(s)
        unique_sources.sort(key=lambda s: s.get("confidence", 0), reverse=True)

        # Build summary
        summary_parts = []
        if question_result:
            if question_result.suggest_web_search:
                summary_parts.append(
                    "Could not fully answer from existing knowledge. "
                    "A web search is recommended."
                )
            else:
                summary_parts.append("Answer generated from knowledge base.")
        if ingestion_result:
            summary_parts.append(
                f"Proposed {ingestion_result.action}: {ingestion_result.title}"
            )

        output = WorkflowOutput(
            intent=intent,
            question_result=question_result,
            ingestion_result=ingestion_result,
            sources=unique_sources,
            summary=" | ".join(summary_parts) if summary_parts else "Workflow complete.",
        )

        logger.info(f"[EXECUTOR] ResponseFormatter: yielding output (intent={intent})")
        await ctx.yield_output(output)
