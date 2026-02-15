"""Knowledge Lookup Executor.

A non-LLM executor that queries the knowledge base indexes
using tags from the TriageResult. Deterministic — no model needed.
"""

import logging
from typing import Any

from agent_framework import Executor, WorkflowContext, handler

from app.models import TriageResult, LookupResult
from app.tools.knowledge_retrieval import search_by_tags_structured

logger = logging.getLogger("workflow.knowledge_lookup")


class KnowledgeLookupExecutor(Executor):
    """Query knowledge indexes using tags from triage.

    Input:  TriageResult (from Triage AgentExecutor)
    Output: LookupResult (for downstream Question/Ingestion handlers)
    """

    @handler
    async def handle(
        self,
        triage: TriageResult,
        ctx: WorkflowContext[LookupResult],
    ) -> None:
        """Look up knowledge matches for the extracted tags."""
        logger.info(
            f"[EXECUTOR] KnowledgeLookup: intent={triage.intent}, "
            f"tags={triage.tags}, domain={triage.domain}"
        )

        matches = []
        if triage.tags:
            matches = search_by_tags_structured(triage.tags)
            logger.info(f"[EXECUTOR] KnowledgeLookup: found {len(matches)} matches")

        # Sort by confidence descending
        matches.sort(key=lambda m: m.confidence, reverse=True)

        # Determine if we have enough context to answer
        high_confidence_matches = [m for m in matches if m.confidence >= 0.7]
        has_sufficient = len(high_confidence_matches) >= 1

        result = LookupResult(
            triage=triage,
            matches=[m.to_dict() for m in matches],
            match_count=len(matches),
            has_sufficient_context=has_sufficient,
            available_tags=triage.tags,
        )

        logger.info(
            f"[EXECUTOR] KnowledgeLookup: {result.match_count} matches, "
            f"sufficient_context={result.has_sufficient_context}"
        )

        await ctx.send_message(result)
