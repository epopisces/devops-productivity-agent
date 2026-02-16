"""Ingestion Preview Agent — proposes knowledge-base writes.

Custom Executor that wraps a ChatAgent with knowledge-ingestion tools.
It receives a LookupResult (triage + existing matches), analyzes the
content to propose a write action (create note, add URL, update context),
and outputs an IngestionPreviewResult for user confirmation.

Actual writes are deferred to user approval in the UI layer.
"""

import json
import logging
import re
from pathlib import Path

from agent_framework import ChatAgent, Executor, WorkflowContext, handler

from app.chat_client import create_chat_client
from app.config import get_config, load_instructions
from app.models import LookupResult, IngestionPreviewResult
from app.tools.knowledge_ingestion import get_knowledge_status
from app.tools.url_scraper import fetch_url

logger = logging.getLogger("workflow.ingestion_preview")

_FALLBACK_INSTRUCTIONS = """\
You are an Ingestion Preview agent. Your job is to analyze content the user
wants to store and propose the best way to ingest it into the knowledge base.

## Storage Options
1. **create_note**: For detailed information, guides, summaries → stored as markdown note
2. **add_url**: For web links worth indexing → stored in URL index with metadata
3. **update_context**: For high-level org context → appended/updated in context file
4. **skip**: If the content doesn't warrant storage

## Rules
1. Review the CONTENT and EXISTING MATCHES provided.
2. If content overlaps with an existing note, mark action as "update_note".
3. If a URL is provided, prefer "add_url" with a summary.
4. For general facts or team info, use "update_context".
5. For detailed content, use "create_note".

## Output Format
Output ONLY a JSON object:
```json
{
  "action": "create_note" | "update_note" | "add_url" | "update_context" | "skip",
  "title": "Proposed title",
  "domain": "general",
  "tags": ["tag1", "tag2"],
  "preview_content": "The actual content to store (markdown for notes, summary for URLs)",
  "target_path": "knowledge/notes/filename.md or 'url_index' or 'context.md'",
  "confidence": 0.9,
  "relevance": 0.8
}
```
"""


class IngestionPreviewExecutor(Executor):
    """Propose knowledge-base writes for user approval.

    Input:  LookupResult (from KnowledgeLookup)
    Output: IngestionPreviewResult
    """

    agent: ChatAgent

    def __init__(self, *, id: str = "ingestion_preview"):
        config = get_config()
        client = create_chat_client(purpose="ingestion_preview")

        instructions = load_instructions(
            config.agents.ingestion_preview.instructions_file
        )
        if instructions is None:
            instructions = _FALLBACK_INSTRUCTIONS

        # Inject configured domain names so the LLM picks valid domains
        domain_lines = []
        for dname, dcfg in config.knowledge.domains.items():
            desc = dcfg.description or dname
            domain_lines.append(f"- **{dname}**: {desc}")
        domain_list = "\n".join(domain_lines) if domain_lines else "- general"

        try:
            instructions = instructions.format(
                domain_list=domain_list,
                confidence_threshold=config.knowledge.confidence_threshold,
                relevance_threshold=config.knowledge.relevance_threshold,
            )
        except KeyError:
            pass

        self.agent = client.as_agent(
            name=config.agents.ingestion_preview.name,
            description=config.agents.ingestion_preview.description,
            instructions=instructions,
            tools=[get_knowledge_status, fetch_url],
        )
        super().__init__(id=id)

    @handler
    async def handle(
        self, lookup: LookupResult, ctx: WorkflowContext[IngestionPreviewResult]
    ) -> None:
        """Analyze content and propose an ingestion action."""
        config = get_config()
        content = lookup.triage.raw_content or lookup.triage.cleaned_query or ""
        logger.info(f"[INGESTION] Analyzing: {content[:100]}...")

        # Build prompt
        prompt_parts = [f"## Content to Ingest\n{content}\n"]

        if lookup.triage.source_url:
            prompt_parts.append(f"## Source URL\n{lookup.triage.source_url}\n")

        if lookup.triage.domain:
            prompt_parts.append(f"## Suggested Domain\n{lookup.triage.domain}\n")

        if lookup.triage.tags:
            prompt_parts.append(f"## Suggested Tags\n{', '.join(lookup.triage.tags)}\n")

        if lookup.matches:
            prompt_parts.append("## Existing Related Knowledge\n")
            for match in lookup.matches[:5]:
                prompt_parts.append(
                    f"- **{match.get('title', 'Untitled')}** "
                    f"({match.get('source_type', '?')}): "
                    f"{match.get('summary', 'N/A')}\n"
                )

        # Load the domain template so the LLM uses its structure
        domain_key = lookup.triage.domain or "general"
        domain_cfg = config.knowledge.get_domain(domain_key)
        project_root = Path(__file__).parent.parent.parent
        tmpl_path = project_root / domain_cfg.template
        if tmpl_path.exists():
            tmpl_text = tmpl_path.read_text(encoding="utf-8")
            # Strip the frontmatter — we only want the body structure
            body_match = re.search(r'^---\n.*?\n---\n+(.+)', tmpl_text, re.DOTALL)
            if body_match:
                tmpl_body = body_match.group(1).strip()
                prompt_parts.append(
                    f"\n## Note Template (use this structure for preview_content)\n"
                    f"```markdown\n{tmpl_body}\n```\n"
                    f"\nIMPORTANT: When the action is `create_note`, format `preview_content` "
                    f"using the section headings from the template above. Fill in each section "
                    f"with the relevant information extracted from the user's content. "
                    f"Do NOT just echo back the raw user input.\n"
                )

        prompt_parts.append(
            "\nPropose the best ingestion action. Output ONLY a JSON object "
            "with: action, title, domain, tags, preview_content, target_path, "
            "confidence, relevance."
        )

        prompt = "\n".join(prompt_parts)

        # Run agent (may use fetch_url for URL content)
        response = await self.agent.run(prompt)
        raw_text = response.text.strip()
        logger.debug(f"[INGESTION] Raw response: {raw_text[:300]}...")

        # Parse result
        result = self._parse_response(raw_text, lookup)
        logger.info(
            f"[INGESTION] Result: action={result.action}, "
            f"title='{result.title}'"
        )

        await ctx.send_message(result)

    def _parse_response(
        self, raw_text: str, lookup: LookupResult
    ) -> IngestionPreviewResult:
        """Parse the agent's response into an IngestionPreviewResult."""
        config = get_config()

        data: dict | None = None

        # Strategy 1: fenced ```json ... ``` block (greedy to handle nested braces)
        json_match = re.search(r'```json\s*(\{.*\})\s*```', raw_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Strategy 2: find the outermost { ... } in the text
        if data is None:
            # Walk forward to find balanced braces
            start = raw_text.find('{')
            if start != -1:
                depth = 0
                end = start
                for i, ch in enumerate(raw_text[start:], start):
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
                try:
                    data = json.loads(raw_text[start:end])
                except json.JSONDecodeError:
                    pass

        # Unwrap tool-call format: {"name": "...", "parameters": {...}}
        if data and "parameters" in data and isinstance(data["parameters"], dict):
            inner = data["parameters"]
            # Carry over name → action if inner doesn't have action
            if "action" not in inner and "name" in data:
                inner["action"] = data["name"]
            data = inner

        # Normalise "name" → "action" at top level too
        if data and "action" not in data and "name" in data:
            data["action"] = data.pop("name")

        if data and ("action" in data or "preview_content" in data):
            try:
                conf = float(data.get("confidence", 0.8))
                rel = float(data.get("relevance", 0.8))
                requires_review = (
                    conf < config.knowledge.confidence_threshold
                    or rel < config.knowledge.relevance_threshold
                )

                return IngestionPreviewResult(
                    action=data.get("action", "create_note"),
                    target_path=data.get("target_path", ""),
                    preview_content=data.get("preview_content", raw_text),
                    title=data.get("title", "Untitled"),
                    domain=data.get("domain", "general"),
                    tags=data.get("tags", lookup.triage.tags),
                    confidence=conf,
                    relevance=rel,
                    related_existing=lookup.matches,
                    requires_review=requires_review,
                    review_reason="Scores below threshold" if requires_review else None,
                    triage=lookup.triage,
                )
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"[INGESTION] Failed to parse JSON: {e}")

        # Fallback: create a note with the raw content
        return IngestionPreviewResult(
            action="create_note",
            target_path="knowledge/notes/",
            preview_content=lookup.triage.raw_content or raw_text,
            title="Untitled Note",
            domain=lookup.triage.domain or "general",
            tags=lookup.triage.tags,
            confidence=0.5,
            relevance=0.5,
            related_existing=lookup.matches,
            requires_review=True,
            review_reason="Could not parse LLM output; manual review recommended",
            triage=lookup.triage,
        )


# ── Standalone refinement helper ───────────────────────────────────────────

async def refine_ingestion_preview(
    current: IngestionPreviewResult,
    user_feedback: str,
) -> IngestionPreviewResult:
    """Refine an existing ingestion preview based on user feedback.

    Creates a fresh ChatAgent, sends the current preview + user feedback,
    parses the updated JSON response, and returns a new IngestionPreviewResult.
    Fields not present in the LLM response are carried over from *current*.
    """
    config = get_config()
    client = create_chat_client(purpose="ingestion_preview_refine")

    instructions = load_instructions(
        config.agents.ingestion_preview.instructions_file
    )
    if instructions is None:
        instructions = _FALLBACK_INSTRUCTIONS

    # Inject domain list & thresholds
    domain_lines = []
    for dname, dcfg in config.knowledge.domains.items():
        desc = dcfg.description or dname
        domain_lines.append(f"- **{dname}**: {desc}")
    domain_list = "\n".join(domain_lines) if domain_lines else "- general"
    try:
        instructions = instructions.format(
            domain_list=domain_list,
            confidence_threshold=config.knowledge.confidence_threshold,
            relevance_threshold=config.knowledge.relevance_threshold,
        )
    except KeyError:
        pass

    agent = client.as_agent(
        name="ingestion_preview_refine",
        description="Refine a proposed ingestion preview based on user feedback.",
        instructions=instructions,
    )

    # Build the refinement prompt
    current_json = current.model_dump_json(indent=2)
    prompt = (
        "## Current Ingestion Preview\n"
        f"```json\n{current_json}\n```\n\n"
        "## User Feedback\n"
        f"{user_feedback}\n\n"
        "Apply the user's feedback to the preview above and output ONLY "
        "the updated JSON object with the same fields: action, title, domain, "
        "tags, preview_content, target_path, confidence, relevance.\n"
        "Keep any fields the user did not mention unchanged."
    )

    response = await agent.run(prompt)
    raw_text = response.text.strip()
    logger.debug(f"[INGESTION-REFINE] Raw response: {raw_text[:300]}...")

    # Re-use the executor's parser via a temporary instance
    dummy_lookup = LookupResult(
        triage=current.triage,
        matches=current.related_existing,
    )
    executor = IngestionPreviewExecutor.__new__(IngestionPreviewExecutor)
    refined = executor._parse_response(raw_text, dummy_lookup)

    # Carry over fields that the LLM may have omitted
    if not refined.title or refined.title == "Untitled Note":
        refined.title = current.title
    if refined.domain == "general" and current.domain != "general":
        refined.domain = current.domain
    if not refined.tags and current.tags:
        refined.tags = current.tags
    if not refined.target_path and current.target_path:
        refined.target_path = current.target_path
    # Preserve triage from original
    refined.triage = current.triage
    refined.related_existing = current.related_existing

    logger.info(
        f"[INGESTION-REFINE] Refined: action={refined.action}, "
        f"title='{refined.title}'"
    )
    return refined
