"""Organizational Context Tool Functions.

Read-only functions for retrieving org context, notes, and URL indexes.
Extracted from the old OrgContextAgent — no agent wrapper needed.
"""

import logging
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import Field

from app.config import get_config
from app.metrics import track_tool_call

# Logger for Org Context
logger = logging.getLogger("workflow.org_context")


# ============================================================================
# Helpers
# ============================================================================

def _get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


# ============================================================================
# Public Tool Functions
# ============================================================================

@track_tool_call("org_context")
def get_instructions_context() -> str:
    """Get the high-level organizational context from the context file.

    This is the PRIMARY source of organizational context.

    Returns:
        The contents of the context file, or an error message.
    """
    logger.info("[TOOL CALL] get_instructions_context")
    config = get_config()

    try:
        project_root = _get_project_root()
        context_path = project_root / config.knowledge.context_file

        if not context_path.exists():
            logger.warning(f"Context file not found: {context_path}")
            return "No organizational context file found. The organization context has not been set up yet."

        with open(context_path, "r", encoding="utf-8") as f:
            content = f.read()

        logger.info(f"[TOOL RESULT] get_instructions_context: {len(content)} chars")
        return f"=== Organizational Context ===\n\n{content}"

    except Exception as e:
        logger.error(f"Failed to read context file: {e}")
        return f"Error reading context file: {e}"


@track_tool_call("org_context")
def get_notes_index() -> str:
    """Get the index of all available notes with their metadata.

    Returns:
        A formatted list of available notes with summaries and tags.
    """
    logger.info("[TOOL CALL] get_notes_index")
    config = get_config()

    try:
        project_root = _get_project_root()
        all_notes = []

        for topic, topic_config in config.knowledge.notes_topics.items():
            index_path = project_root / topic_config.directory / "_index.yaml"

            if not index_path.exists():
                continue

            with open(index_path, "r", encoding="utf-8") as f:
                index_data = yaml.safe_load(f) or {}

            for note in index_data.get("notes", []):
                all_notes.append({
                    "topic": topic,
                    "filename": note.get("filename", ""),
                    "title": note.get("title", "Untitled"),
                    "domain": note.get("domain", "general"),
                    "category": note.get("category", "general"),
                    "summary": note.get("summary", ""),
                    "tags": note.get("tags", []),
                    "created": note.get("created", ""),
                    "confidence": note.get("confidence", 1.0),
                    "relevance": note.get("relevance", 1.0),
                })

        if not all_notes:
            logger.info("[TOOL RESULT] get_notes_index: no notes found")
            return "No notes found in the knowledge base."

        output_lines = ["=== Available Notes ===\n"]
        for note in all_notes:
            tags_str = ", ".join(note["tags"]) if note["tags"] else "none"
            output_lines.append(f"**{note['title']}**")
            output_lines.append(f"  - File: {note['filename']}")
            output_lines.append(f"  - Topic: {note['topic']} | Domain: {note['domain']} | Category: {note['category']}")
            output_lines.append(f"  - Tags: {tags_str}")
            output_lines.append(f"  - Summary: {note['summary']}")
            output_lines.append(f"  - Created: {note['created']} | Confidence: {note['confidence']} | Relevance: {note['relevance']}")
            output_lines.append("")

        result = "\n".join(output_lines)
        logger.info(f"[TOOL RESULT] get_notes_index: {len(all_notes)} notes")
        return result

    except Exception as e:
        logger.error(f"Failed to read notes index: {e}")
        return f"Error reading notes index: {e}"


@track_tool_call("org_context")
def read_note(
    filename: Annotated[str, Field(description="The filename of the note to read (e.g., '20251227-my-note.md')")]
) -> str:
    """Read the full content of a specific note file.

    Args:
        filename: The filename of the note to read.

    Returns:
        The full content of the note, or an error message.
    """
    logger.info(f"[TOOL CALL] read_note: {filename}")
    config = get_config()

    try:
        project_root = _get_project_root()

        for _topic, topic_config in config.knowledge.notes_topics.items():
            note_path = project_root / topic_config.directory / filename

            if note_path.exists():
                with open(note_path, "r", encoding="utf-8") as f:
                    content = f.read()

                logger.info(f"[TOOL RESULT] read_note: {filename} ({len(content)} chars)")
                return f"=== Note: {filename} ===\n\n{content}"

        logger.warning(f"Note not found: {filename}")
        return f"Note not found: {filename}. Use get_notes_index to see available notes."

    except Exception as e:
        logger.error(f"Failed to read note {filename}: {e}")
        return f"Error reading note: {e}"


@track_tool_call("org_context")
def get_url_index() -> str:
    """Get the index of organizational URLs with metadata.

    Returns:
        A formatted list of indexed URLs with context and summaries.
    """
    logger.info("[TOOL CALL] get_url_index")
    config = get_config()

    try:
        project_root = _get_project_root()
        index_path = project_root / config.knowledge.url_index_file

        if not index_path.exists():
            logger.info("[TOOL RESULT] get_url_index: no index found")
            return "No URL index found. No URLs have been indexed yet."

        with open(index_path, "r", encoding="utf-8") as f:
            index_data = yaml.safe_load(f) or {}

        urls = index_data.get("urls", [])

        if not urls:
            logger.info("[TOOL RESULT] get_url_index: no URLs in index")
            return "URL index is empty. No URLs have been indexed yet."

        output_lines = ["=== Indexed URLs ===\n"]
        for url_entry in urls:
            tags_str = ", ".join(url_entry.get("tags", [])) if url_entry.get("tags") else "none"
            output_lines.append(f"**{url_entry.get('title', 'Untitled')}**")
            output_lines.append(f"  - URL: {url_entry.get('url', '')}")
            output_lines.append(f"  - Domain: {url_entry.get('domain', 'general')}")
            output_lines.append(f"  - Context: {url_entry.get('context', '')}")
            output_lines.append(f"  - Summary: {url_entry.get('summary', '')}")
            output_lines.append(f"  - Tags: {tags_str}")
            output_lines.append("")

        result = "\n".join(output_lines)
        logger.info(f"[TOOL RESULT] get_url_index: {len(urls)} URLs")
        return result

    except Exception as e:
        logger.error(f"Failed to read URL index: {e}")
        return f"Error reading URL index: {e}"


@track_tool_call("org_context")
def search_knowledge(
    query: Annotated[str, Field(description="Search terms to find in notes and instructions")]
) -> str:
    """Search across all knowledge sources for relevant content.

    Args:
        query: The search terms to look for.

    Returns:
        Matching content from knowledge sources.
    """
    logger.info(f"[TOOL CALL] search_knowledge: {query}")
    config = get_config()

    try:
        project_root = _get_project_root()
        results = []
        query_lower = query.lower()
        query_terms = query_lower.split()

        # Search context file
        context_path = project_root / config.knowledge.context_file
        if context_path.exists():
            with open(context_path, "r", encoding="utf-8") as f:
                content = f.read()

            if any(term in content.lower() for term in query_terms):
                sections = content.split("\n## ")
                matching_sections = [
                    s[:500] + "..." if len(s) > 500 else s
                    for s in sections
                    if any(term in s.lower() for term in query_terms)
                ]

                if matching_sections:
                    results.append("=== From Org Context ===")
                    results.extend(matching_sections[:3])
                    results.append("")

        # Search notes
        for _topic, topic_config in config.knowledge.notes_topics.items():
            notes_dir = project_root / topic_config.directory
            if not notes_dir.exists():
                continue

            for note_file in notes_dir.glob("*.md"):
                if note_file.name == "_index.yaml":
                    continue

                with open(note_file, "r", encoding="utf-8") as f:
                    content = f.read()

                if any(term in content.lower() for term in query_terms):
                    preview = content[:800] + "..." if len(content) > 800 else content
                    results.append(f"=== From Note: {note_file.name} ===")
                    results.append(preview)
                    results.append("")

        if not results:
            logger.info(f"[TOOL RESULT] search_knowledge: no results for '{query}'")
            return f"No matching content found for: {query}"

        result = "\n".join(results)
        logger.info(f"[TOOL RESULT] search_knowledge: found matches for '{query}'")
        return result

    except Exception as e:
        logger.error(f"Failed to search knowledge: {e}")
        return f"Error searching knowledge: {e}"
