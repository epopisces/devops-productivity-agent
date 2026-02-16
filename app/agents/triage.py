"""Triage Agent — classifies user intent and extracts metadata.

Custom Executor that wraps a ChatAgent. It takes raw user text,
invokes the LLM to classify intent (question / ingestion / both),
extract domain and tags, and outputs a structured TriageResult.
"""

import json
import logging
import re

from agent_framework import ChatAgent, Executor, WorkflowContext, handler

from app.chat_client import create_chat_client
from app.config import get_config, load_instructions
from app.models import TriageResult
from app.tools.knowledge_retrieval import get_available_tags

logger = logging.getLogger("workflow.triage")

_FALLBACK_INSTRUCTIONS = """\
You are a Triage agent. Classify the user's intent and extract metadata.

Your job is to analyze the user's input and output ONLY a JSON object:
{{
  "intent": "question" | "ingestion" | "both",
  "domain": "<one of the configured knowledge domains>",
  "tags": ["tag1", "tag2"],
  "cleaned_query": "<the question, if any>",
  "raw_content": "<content to ingest, if any>",
  "source_url": "<URL if user provided one, else null>"
}}

Guidelines:
- "question": the user is asking a question or requesting information
- "ingestion": the user is providing information to store (a URL, notes, facts)
- "both": the user is providing info AND asking a question about it
- Extract tags that would help find relevant knowledge (technologies, concepts, teams)
- If a URL is present, include it in source_url

## Available Domains
{domain_list}

You MUST choose one of the domains listed above.
"""


class TriageExecutor(Executor):
    """Classify user intent and extract domain/tags via LLM.

    Input:  str (raw user message)
    Output: TriageResult (structured classification)
    """

    agent: ChatAgent

    def __init__(self, *, id: str = "triage"):
        config = get_config()
        client = create_chat_client(purpose="triage")

        instructions = load_instructions(
            config.agents.triage.instructions_file
        )
        if instructions is None:
            instructions = _FALLBACK_INSTRUCTIONS

        # Provide available tags as context so the LLM can match existing ones
        try:
            available = get_available_tags()
        except Exception:
            available = "No tags available yet."

        # Build domain list from config so the LLM picks valid domains
        domain_lines = []
        for dname, dcfg in config.knowledge.domains.items():
            desc = dcfg.description or dname
            domain_lines.append(f"- **{dname}**: {desc}")
        domain_list = "\n".join(domain_lines) if domain_lines else "- general"

        # Format placeholders in instructions
        try:
            instructions = instructions.format(domain_list=domain_list)
        except KeyError:
            pass  # template may not have the placeholder yet

        full_instructions = (
            f"{instructions}\n\n"
            f"## Currently available tags in the knowledge base:\n{available}"
        )

        self.agent = client.as_agent(
            name=config.agents.triage.name,
            description=config.agents.triage.description,
            instructions=full_instructions,
        )
        super().__init__(id=id)

    @handler
    async def handle(self, user_input: str, ctx: WorkflowContext[TriageResult]) -> None:
        """Classify the user's message and extract metadata."""
        logger.info(f"[TRIAGE] Processing: {user_input[:100]}...")

        # Check for URL in input
        url_match = re.search(r'https?://\S+', user_input)
        source_url = url_match.group(0) if url_match else None

        # Run the LLM
        response = await self.agent.run(user_input)
        raw_text = response.text.strip()
        logger.debug(f"[TRIAGE] Raw LLM response: {raw_text[:300]}")

        # Parse structured output from LLM response
        triage = self._parse_response(raw_text, user_input, source_url)
        logger.info(
            f"[TRIAGE] Result: intent={triage.intent}, "
            f"domain={triage.domain}, tags={triage.tags}"
        )

        await ctx.send_message(triage)

    def _parse_response(
        self, raw_text: str, user_input: str, detected_url: str | None
    ) -> TriageResult:
        """Parse LLM response into TriageResult, with fallback heuristics."""
        # Try to extract JSON from the response
        json_match = re.search(r'\{[^{}]*\}', raw_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                return TriageResult(
                    intent=data.get("intent", "question"),
                    domain=data.get("domain"),
                    tags=data.get("tags", []),
                    cleaned_query=data.get("cleaned_query", user_input),
                    raw_content=data.get("raw_content"),
                    source_url=data.get("source_url", detected_url),
                )
            except (json.JSONDecodeError, KeyError):
                logger.warning("[TRIAGE] Failed to parse JSON from LLM, using heuristics")

        # Fallback: simple heuristics
        return self._heuristic_classify(user_input, detected_url)

    def _heuristic_classify(
        self, user_input: str, detected_url: str | None
    ) -> TriageResult:
        """Fallback classification when LLM output can't be parsed."""
        text_lower = user_input.lower()
        question_indicators = ["?", "what ", "how ", "why ", "when ", "where ", "who ", "can you", "tell me", "explain"]
        ingestion_indicators = ["save", "store", "remember", "note that", "add this", "index this", "record"]

        is_question = any(ind in text_lower for ind in question_indicators)
        is_ingestion = detected_url is not None or any(ind in text_lower for ind in ingestion_indicators)

        if is_question and is_ingestion:
            intent = "both"
        elif is_ingestion:
            intent = "ingestion"
        else:
            intent = "question"

        return TriageResult(
            intent=intent,
            domain=None,
            tags=[],
            cleaned_query=user_input if intent in ("question", "both") else None,
            raw_content=user_input if intent in ("ingestion", "both") else None,
            source_url=detected_url,
        )
