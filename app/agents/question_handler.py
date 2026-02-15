"""Question Handler Agent — synthesizes answers from knowledge context.

Custom Executor that wraps a ChatAgent with knowledge-retrieval tools.
It receives a LookupResult (containing triage + matched sources),
asks the LLM to synthesize an answer, and outputs a QuestionResult.
"""

import json
import logging
import re

from agent_framework import ChatAgent, Executor, WorkflowContext, handler

from app.chat_client import create_chat_client
from app.config import get_config, load_instructions
from app.models import LookupResult, QuestionResult
from app.tools.org_context import (
    get_instructions_context,
    read_note,
    search_knowledge,
)
from app.tools.url_scraper import fetch_url

logger = logging.getLogger("workflow.question_handler")

_FALLBACK_INSTRUCTIONS = """\
You are a Question Answering agent. Answer the user's question using the
provided knowledge context. You have tools to dig deeper into notes and URLs.

## Rules
1. First review the KNOWLEDGE CONTEXT provided in the user message.
2. If the context is sufficient, answer the question directly.
3. If you need more detail from a specific note, use read_note(filename).
4. If you need more detail from a specific URL, use fetch_url(url).
5. If you need to search more broadly, use search_knowledge(query).

## Output Format
After answering, output a JSON block at the END of your response:
```json
{
  "confidence": 0.0-1.0,
  "suggest_web_search": true/false,
  "search_query": "suggested search terms if web search needed"
}
```
"""


class QuestionHandlerExecutor(Executor):
    """Answer questions using knowledge context and retrieval tools.

    Input:  LookupResult (from KnowledgeLookup)
    Output: QuestionResult
    """

    agent: ChatAgent

    def __init__(self, *, id: str = "question_handler"):
        config = get_config()
        client = create_chat_client(purpose="question_handler")

        instructions = load_instructions(
            config.agents.question_handler.instructions_file
        )
        if instructions is None:
            instructions = _FALLBACK_INSTRUCTIONS

        self.agent = client.as_agent(
            name=config.agents.question_handler.name,
            description=config.agents.question_handler.description,
            instructions=instructions,
            tools=[
                get_instructions_context,
                read_note,
                search_knowledge,
                fetch_url,
            ],
        )
        super().__init__(id=id)

    @handler
    async def handle(
        self, lookup: LookupResult, ctx: WorkflowContext[QuestionResult]
    ) -> None:
        """Generate an answer from the lookup context."""
        query = lookup.triage.cleaned_query or "No question provided."
        logger.info(f"[QUESTION] Answering: {query[:100]}...")

        # Build prompt with knowledge context
        context_parts = [f"## User Question\n{query}\n"]

        if lookup.matches:
            context_parts.append("## Knowledge Context (from tag search)\n")
            for i, match in enumerate(lookup.matches[:10], 1):
                context_parts.append(
                    f"{i}. **{match.get('title', 'Untitled')}** "
                    f"({match.get('source_type', 'unknown')})\n"
                    f"   Summary: {match.get('summary', 'N/A')}\n"
                    f"   Tags: {', '.join(match.get('tags', []))}\n"
                    f"   Confidence: {match.get('confidence', 'N/A')}\n"
                )
                if match.get("filename"):
                    context_parts.append(f"   File: {match['filename']}\n")
                if match.get("url"):
                    context_parts.append(f"   URL: {match['url']}\n")
        else:
            context_parts.append(
                "## Knowledge Context\nNo matching sources found in the knowledge base.\n"
            )

        context_parts.append(
            "\nAnswer the question above using the knowledge context. "
            "Use tools if you need more detail. "
            "End with a JSON block: {\"confidence\": 0.0-1.0, "
            "\"suggest_web_search\": true/false, \"search_query\": \"...\"}"
        )

        prompt = "\n".join(context_parts)

        # Run the agent
        response = await self.agent.run(prompt)
        raw_text = response.text.strip()
        logger.debug(f"[QUESTION] Raw response: {raw_text[:300]}...")

        # Parse result
        result = self._parse_response(raw_text, lookup)
        logger.info(
            f"[QUESTION] Result: confidence={result.confidence}, "
            f"suggest_web_search={result.suggest_web_search}"
        )

        await ctx.send_message(result)

    def _parse_response(
        self, raw_text: str, lookup: LookupResult
    ) -> QuestionResult:
        """Parse the agent's response into a QuestionResult."""
        confidence = 0.5
        suggest_web_search = not lookup.has_sufficient_context
        search_query = None

        # Try to extract JSON metadata from the end of the response
        json_match = re.search(r'```json\s*(\{[^}]+\})\s*```', raw_text, re.DOTALL)
        if not json_match:
            json_match = re.search(r'\{[^{}]*"confidence"[^{}]*\}', raw_text, re.DOTALL)

        answer_text = raw_text
        if json_match:
            try:
                meta = json.loads(json_match.group(1) if '```' in raw_text else json_match.group(0))
                confidence = float(meta.get("confidence", confidence))
                suggest_web_search = bool(meta.get("suggest_web_search", suggest_web_search))
                search_query = meta.get("search_query")
                # Remove the JSON block from the answer text
                answer_text = raw_text[:json_match.start()].strip()
            except (json.JSONDecodeError, ValueError):
                pass

        return QuestionResult(
            answer=answer_text,
            confidence=confidence,
            sources_used=lookup.matches,
            suggest_web_search=suggest_web_search,
            search_query=search_query,
            triage=lookup.triage,
        )
