"""Agents package for the workflow-based architecture.

New agents:
- TriageExecutor: Classifies user intent and extracts metadata
- QuestionHandlerExecutor: Answers questions from knowledge context
- IngestionPreviewExecutor: Proposes knowledge-base writes
"""

from .triage import TriageExecutor
from .question_handler import QuestionHandlerExecutor
from .ingestion_preview import IngestionPreviewExecutor

__all__ = [
    "TriageExecutor",
    "QuestionHandlerExecutor",
    "IngestionPreviewExecutor",
]
