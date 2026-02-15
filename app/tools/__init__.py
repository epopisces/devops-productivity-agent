"""Standalone tool functions for the workflow.

These are plain Python functions (not agent wrappers) that can be registered
as tools on any agent or used directly by workflow executors.
"""

from .url_scraper import fetch_url
from .knowledge_retrieval import get_available_tags, search_by_tags
from .knowledge_ingestion import (
    add_url_to_index,
    update_instructions_file,
    create_note,
    get_knowledge_status,
)
from .org_context import (
    get_instructions_context,
    get_notes_index,
    read_note,
    get_url_index,
    search_knowledge,
)

__all__ = [
    # URL scraping
    "fetch_url",
    # Knowledge retrieval (read-only queries)
    "get_available_tags",
    "search_by_tags",
    # Knowledge ingestion (write operations)
    "add_url_to_index",
    "update_instructions_file",
    "create_note",
    "get_knowledge_status",
    # Org context (read-only lookups)
    "get_instructions_context",
    "get_notes_index",
    "read_note",
    "get_url_index",
    "search_knowledge",
]
