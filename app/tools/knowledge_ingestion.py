"""Knowledge Ingestion Tool Functions.

Standalone sync functions for writing to the knowledge base.
No agent wrapper — these are registered directly as tools on agents that need them.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, Field

from app.config import get_config
from app.metrics import track_tool_call

# Logger for Knowledge Ingestion
logger = logging.getLogger("workflow.knowledge_ingestion")


# ============================================================================
# Data Models
# ============================================================================

class URLIndexEntry(BaseModel):
    """Entry in the URL index."""
    url: str
    title: str
    domain: str = Field(description="Domain of knowledge (e.g., 'engineering', 'hr', 'finance')")
    context: str = Field(description="Brief context about why this URL is relevant")
    summary: str = Field(description="Content summary")
    tags: list[str] = Field(default_factory=list)
    added_date: str = Field(default_factory=lambda: datetime.now().isoformat())
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    relevance: float = Field(default=1.0, ge=0.0, le=1.0)


class NoteMetadata(BaseModel):
    """Frontmatter metadata for a note file."""
    title: str
    created: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    updated: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    domain: str = Field(default="general", description="Domain of knowledge")
    category: str = Field(default="general")
    tags: list[str] = Field(default_factory=list)
    summary: str = Field(default="")
    source_url: str | None = Field(default=None)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    relevance: float = Field(default=1.0, ge=0.0, le=1.0)
    reviewed: bool = Field(default=False)
    priority: str = Field(default="medium")


class NotesIndexEntry(BaseModel):
    """Entry in the notes index."""
    filename: str
    title: str
    domain: str
    category: str
    summary: str
    tags: list[str] = Field(default_factory=list)
    created: str
    updated: str
    confidence: float = Field(default=1.0)
    relevance: float = Field(default=1.0)


# ============================================================================
# Helpers
# ============================================================================

def _get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


def _ensure_directory(path: Path) -> None:
    """Ensure a directory exists."""
    path.mkdir(parents=True, exist_ok=True)


def _update_notes_index(topic: str, metadata: NoteMetadata, filename: str) -> None:
    """Update the notes index for a topic after creating/updating a note."""
    config = get_config()
    project_root = _get_project_root()

    topic_config = config.knowledge.notes_topics.get(topic, config.knowledge.notes_topics["default"])
    notes_dir = project_root / topic_config.directory
    index_path = notes_dir / "_index.yaml"

    index_data: list[dict] = []
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}
            index_data = existing.get("notes", [])

    entry = NotesIndexEntry(
        filename=filename,
        title=metadata.title,
        domain=metadata.domain,
        category=metadata.category,
        summary=metadata.summary,
        tags=metadata.tags,
        created=metadata.created,
        updated=metadata.updated,
        confidence=metadata.confidence,
        relevance=metadata.relevance,
    )

    for i, existing_entry in enumerate(index_data):
        if existing_entry.get("filename") == filename:
            index_data[i] = entry.model_dump()
            break
    else:
        index_data.append(entry.model_dump())

    with open(index_path, "w", encoding="utf-8") as f:
        yaml.dump(
            {"topic": topic, "description": topic_config.description, "notes": index_data},
            f, default_flow_style=False, sort_keys=False,
        )


# ============================================================================
# Public Tool Functions
# ============================================================================

@track_tool_call("knowledge_ingestion")
def add_url_to_index(
    url: Annotated[str, Field(description="The URL to add to the index")],
    title: Annotated[str, Field(description="Title of the page")],
    domain: Annotated[str, Field(description="Domain of knowledge (e.g., 'engineering', 'hr', 'finance')")],
    context: Annotated[str, Field(description="Brief context about why this URL is relevant to the org")],
    summary: Annotated[str, Field(description="Summary of the content")],
    tags: Annotated[str, Field(description="Comma-separated list of tags")] = "",
    confidence: Annotated[float, Field(description="Confidence score 0.0-1.0")] = 1.0,
    relevance: Annotated[float, Field(description="Relevance score 0.0-1.0")] = 1.0,
) -> str:
    """Add a URL entry to the organizational URL index.

    Args:
        url: The URL to index.
        title: Page title.
        domain: Knowledge domain.
        context: Why this URL is relevant.
        summary: Content summary.
        tags: Comma-separated tags.
        confidence: Confidence in the content quality (0.0-1.0).
        relevance: Relevance to the organization (0.0-1.0).

    Returns:
        Status message indicating success or failure.
    """
    logger.info(f"[TOOL CALL] add_url_to_index: {url}")
    config = get_config()

    if confidence < config.knowledge.confidence_threshold or relevance < config.knowledge.relevance_threshold:
        review_reasons = []
        if confidence < config.knowledge.confidence_threshold:
            review_reasons.append(f"confidence ({confidence:.2f}) below threshold ({config.knowledge.confidence_threshold})")
        if relevance < config.knowledge.relevance_threshold:
            review_reasons.append(f"relevance ({relevance:.2f}) below threshold ({config.knowledge.relevance_threshold})")

        logger.info(f"[TOOL RESULT] add_url_to_index requires review: {', '.join(review_reasons)}")
        return (
            f"REVIEW_REQUIRED: Cannot add URL without human approval. Reasons: {', '.join(review_reasons)}. "
            f"Please confirm you want to add URL '{title}' ({url}) with domain='{domain}'."
        )

    try:
        project_root = _get_project_root()
        index_path = project_root / config.knowledge.url_index_file
        _ensure_directory(index_path.parent)

        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

        entry = URLIndexEntry(
            url=url, title=title, domain=domain, context=context,
            summary=summary, tags=tag_list, confidence=confidence, relevance=relevance,
        )

        index_data: list[dict] = []
        if index_path.exists():
            with open(index_path, "r", encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
                index_data = existing.get("urls", [])

        for existing_entry in index_data:
            if existing_entry.get("url") == url:
                logger.info(f"[TOOL RESULT] URL already in index, updating: {url}")
                existing_entry.update(entry.model_dump())
                break
        else:
            index_data.append(entry.model_dump())

        with open(index_path, "w", encoding="utf-8") as f:
            yaml.dump({"urls": index_data}, f, default_flow_style=False, sort_keys=False)

        logger.info(f"[TOOL RESULT] add_url_to_index completed: {url}")
        return f"Successfully added URL to index: {title} ({url}). Domain: {domain}, Tags: {tag_list}"

    except Exception as e:
        logger.error(f"Failed to add URL to index: {e}")
        return f"Error adding URL to index: {e}"


@track_tool_call("knowledge_ingestion")
def update_instructions_file(
    section: Annotated[str, Field(description="Section header to update (e.g., 'Team Structure', 'Processes')")],
    content: Annotated[str, Field(description="The content to add or update under this section")],
    action: Annotated[Literal["append", "replace"], Field(description="Whether to append to or replace the section")] = "append",
    confidence: Annotated[float, Field(description="Confidence score 0.0-1.0")] = 1.0,
    relevance: Annotated[float, Field(description="Relevance score 0.0-1.0")] = 1.0,
) -> str:
    """Update the organizational instructions file with new context.

    Args:
        section: The section header to update.
        content: Content to add under this section.
        action: Whether to 'append' to existing content or 'replace' it.
        confidence: Confidence in the content accuracy (0.0-1.0).
        relevance: Relevance to the organization (0.0-1.0).

    Returns:
        Status message indicating success or failure.
    """
    logger.info(f"[TOOL CALL] update_instructions_file: section='{section}', action={action}")
    config = get_config()

    if confidence < config.knowledge.confidence_threshold or relevance < config.knowledge.relevance_threshold:
        review_reasons = []
        if confidence < config.knowledge.confidence_threshold:
            review_reasons.append(f"confidence ({confidence:.2f}) below threshold ({config.knowledge.confidence_threshold})")
        if relevance < config.knowledge.relevance_threshold:
            review_reasons.append(f"relevance ({relevance:.2f}) below threshold ({config.knowledge.relevance_threshold})")

        logger.info(f"[TOOL RESULT] update_instructions_file requires review: {', '.join(review_reasons)}")
        return (
            f"REVIEW_REQUIRED: Cannot update context file without human approval. Reasons: {', '.join(review_reasons)}. "
            f"Please confirm you want to {action} section '{section}'. Content preview: {content[:200]}..."
        )

    try:
        project_root = _get_project_root()
        context_path = project_root / config.knowledge.context_file
        _ensure_directory(context_path.parent)

        if context_path.exists():
            with open(context_path, "r", encoding="utf-8") as f:
                file_content = f.read()
        else:
            file_content = f"# Organizational Instructions\n\nLast Updated: {datetime.now().strftime('%Y-%m-%d')}\n\n"

        section_header = f"## {section}"
        section_pattern = rf"(## {re.escape(section)})\n(.*?)(?=\n## |\Z)"

        if section_header in file_content:
            if action == "replace":
                file_content = re.sub(
                    section_pattern,
                    f"{section_header}\n\n{content}\n",
                    file_content,
                    flags=re.DOTALL,
                )
            else:
                def append_content(match):
                    return f"{match.group(1)}\n{match.group(2).rstrip()}\n\n{content}\n"
                file_content = re.sub(section_pattern, append_content, file_content, flags=re.DOTALL)
        else:
            file_content = file_content.rstrip() + f"\n\n{section_header}\n\n{content}\n"

        file_content = re.sub(
            r"Last Updated: \d{4}-\d{2}-\d{2}",
            f"Last Updated: {datetime.now().strftime('%Y-%m-%d')}",
            file_content,
        )

        with open(context_path, "w", encoding="utf-8") as f:
            f.write(file_content)

        logger.info(f"[TOOL RESULT] update_instructions_file completed: section='{section}'")
        return f"Successfully updated instructions file section: {section} (action: {action})"

    except Exception as e:
        logger.error(f"Failed to update instructions file: {e}")
        return f"Error updating instructions file: {e}"


@track_tool_call("knowledge_ingestion")
def create_note(
    title: Annotated[str, Field(description="Title of the note")],
    content: Annotated[str, Field(description="Main content of the note in markdown format")],
    topic: Annotated[str, Field(description="Topic/category key from config (e.g., 'default')")] = "default",
    domain: Annotated[str, Field(description="Domain of knowledge (e.g., 'engineering', 'processes')")] = "general",
    category: Annotated[str, Field(description="Category for the note")] = "general",
    tags: Annotated[str, Field(description="Comma-separated list of tags")] = "",
    summary: Annotated[str, Field(description="Brief summary of the note")] = "",
    source_url: Annotated[str | None, Field(description="Source URL if content was extracted from web")] = None,
    confidence: Annotated[float, Field(description="Confidence score 0.0-1.0")] = 1.0,
    relevance: Annotated[float, Field(description="Relevance score 0.0-1.0")] = 1.0,
) -> str:
    """Create a new note file with frontmatter metadata.

    Args:
        title: Note title (used for filename).
        content: Markdown content of the note.
        topic: Topic key for organizing notes.
        domain: Knowledge domain.
        category: Note category.
        tags: Comma-separated tags.
        summary: Brief summary.
        source_url: Optional source URL.
        confidence: Confidence in content accuracy (0.0-1.0).
        relevance: Relevance to organization (0.0-1.0).

    Returns:
        Status message with file path or error.
    """
    logger.info(f"[TOOL CALL] create_note: title='{title}', topic={topic}")
    config = get_config()

    if confidence < config.knowledge.confidence_threshold or relevance < config.knowledge.relevance_threshold:
        review_reasons = []
        if confidence < config.knowledge.confidence_threshold:
            review_reasons.append(f"confidence ({confidence:.2f}) below threshold ({config.knowledge.confidence_threshold})")
        if relevance < config.knowledge.relevance_threshold:
            review_reasons.append(f"relevance ({relevance:.2f}) below threshold ({config.knowledge.relevance_threshold})")

        logger.info(f"[TOOL RESULT] create_note requires review: {', '.join(review_reasons)}")
        return (
            f"REVIEW_REQUIRED: Cannot create note without human approval. Reasons: {', '.join(review_reasons)}. "
            f"Note title: '{title}', domain: '{domain}'. Content preview: {content[:200]}..."
        )

    try:
        project_root = _get_project_root()

        if topic not in config.knowledge.notes_topics:
            logger.warning(f"Topic '{topic}' not found, using 'default'")
            topic = "default"

        topic_config = config.knowledge.notes_topics[topic]
        notes_dir = project_root / topic_config.directory
        _ensure_directory(notes_dir)

        safe_title = re.sub(r'[^\w\s-]', '', title.lower())
        safe_title = re.sub(r'[-\s]+', '-', safe_title).strip('-')
        filename = f"{datetime.now().strftime('%Y%m%d')}-{safe_title}.md"
        filepath = notes_dir / filename

        counter = 1
        while filepath.exists():
            filename = f"{datetime.now().strftime('%Y%m%d')}-{safe_title}-{counter}.md"
            filepath = notes_dir / filename
            counter += 1

        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

        defaults = topic_config.frontmatter_defaults

        metadata = NoteMetadata(
            title=title,
            domain=domain,
            category=category or defaults.get("category", "general"),
            tags=tag_list,
            summary=summary,
            source_url=source_url,
            confidence=confidence,
            relevance=relevance,
            reviewed=defaults.get("reviewed", False),
            priority=defaults.get("priority", "medium"),
        )

        frontmatter = yaml.dump(metadata.model_dump(exclude_none=True), default_flow_style=False, sort_keys=False)
        file_content = f"---\n{frontmatter}---\n\n{content}"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(file_content)

        _update_notes_index(topic, metadata, filename)

        relative_path = filepath.relative_to(project_root)
        logger.info(f"[TOOL RESULT] create_note completed: {relative_path}")
        return f"Successfully created note: {relative_path}"

    except Exception as e:
        logger.error(f"Failed to create note: {e}")
        return f"Error creating note: {e}"


@track_tool_call("knowledge_ingestion")
def get_knowledge_status() -> str:
    """Get the current status of all knowledge stores.

    Returns:
        Status summary of all knowledge stores.
    """
    logger.info("[TOOL CALL] get_knowledge_status")
    config = get_config()
    project_root = _get_project_root()

    status_parts = []

    context_path = project_root / config.knowledge.context_file
    if context_path.exists():
        with open(context_path, "r", encoding="utf-8") as f:
            content = f.read()
        sections = re.findall(r"^## (.+)$", content, re.MULTILINE)
        status_parts.append(f"Context File: {len(sections)} sections - {', '.join(sections)}")
    else:
        status_parts.append("Context File: Not created yet")

    url_index_path = project_root / config.knowledge.url_index_file
    if url_index_path.exists():
        with open(url_index_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        url_count = len(data.get("urls", []))
        status_parts.append(f"URL Index: {url_count} URLs indexed")
    else:
        status_parts.append("URL Index: Not created yet")

    for topic, topic_config in config.knowledge.notes_topics.items():
        notes_dir = project_root / topic_config.directory
        index_path = notes_dir / "_index.yaml"
        if index_path.exists():
            with open(index_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            note_count = len(data.get("notes", []))
            status_parts.append(f"Notes ({topic}): {note_count} notes in {topic_config.directory}/")
        else:
            status_parts.append(f"Notes ({topic}): No notes yet in {topic_config.directory}/")

    status_parts.append(
        f"\nThresholds - Confidence: {config.knowledge.confidence_threshold}, "
        f"Relevance: {config.knowledge.relevance_threshold}"
    )

    result = "\n".join(status_parts)
    logger.info("[TOOL RESULT] get_knowledge_status completed")
    return result
