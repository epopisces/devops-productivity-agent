"""Tests for the Streamlit web interface module.

These tests validate imports, helper functions, and output formatting
without requiring a running Streamlit server.
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Import / module-level checks
# ---------------------------------------------------------------------------

class TestWebImports:
    """Verify that web.py can be imported and its dependencies resolve."""

    def test_import_web_module(self):
        """web.py should import without errors (catches ModuleNotFoundError)."""
        # Streamlit must be importable; if not installed the whole module fails
        import app.web  # noqa: F401

    def test_web_module_has_main(self):
        """web.py should expose a main() entry point."""
        from app.web import main
        assert callable(main)

    def test_web_module_has_format_workflow_output(self):
        """web.py should expose format_workflow_output."""
        from app.web import format_workflow_output
        assert callable(format_workflow_output)

    def test_web_module_has_process_message(self):
        """web.py should expose async process_message."""
        import asyncio
        from app.web import process_message
        assert asyncio.iscoroutinefunction(process_message)


# ---------------------------------------------------------------------------
# format_workflow_output
# ---------------------------------------------------------------------------

class TestFormatWorkflowOutput:
    """Test the format_workflow_output helper."""

    def test_empty_outputs(self):
        from app.web import format_workflow_output
        result = format_workflow_output([])
        assert "No response" in result

    def test_question_output(self):
        from app.web import format_workflow_output
        from app.models import WorkflowOutput, QuestionResult

        qr = QuestionResult(answer="42 is the answer.", confidence=0.9)
        output = WorkflowOutput(
            intent="question",
            question_result=qr,
            summary="test",
        )
        result = format_workflow_output([output])
        assert "42 is the answer" in result

    def test_low_confidence_warning(self):
        from app.web import format_workflow_output
        from app.models import WorkflowOutput, QuestionResult

        qr = QuestionResult(answer="Maybe.", confidence=0.3, suggest_web_search=False)
        output = WorkflowOutput(
            intent="question",
            question_result=qr,
            summary="test",
        )
        result = format_workflow_output([output])
        assert "Low confidence" in result

    def test_suggest_web_search(self):
        from app.web import format_workflow_output
        from app.models import WorkflowOutput, QuestionResult

        qr = QuestionResult(
            answer="Not sure.",
            confidence=0.8,
            suggest_web_search=True,
            search_query="kubernetes pod scheduling",
        )
        output = WorkflowOutput(
            intent="question",
            question_result=qr,
            summary="test",
        )
        result = format_workflow_output([output])
        assert "kubernetes pod scheduling" in result

    def test_ingestion_output(self):
        from app.web import format_workflow_output
        from app.models import WorkflowOutput, IngestionPreviewResult

        ip = IngestionPreviewResult(
            action="create_note",
            title="New Note",
            domain="engineering",
            tags=["k8s", "infra"],
            preview_content="Some content here.",
            confidence=0.95,
        )
        output = WorkflowOutput(
            intent="ingestion",
            ingestion_result=ip,
            summary="test",
        )
        result = format_workflow_output([output])
        assert "New Note" in result
        assert "create_note" in result
        # Badge-style HTML should be present
        assert "<span" in result
        assert "engineering" in result
        assert "k8s" in result
        assert "infra" in result
        assert "95%" in result

    def test_sources_deduplication(self):
        from app.web import format_workflow_output
        from app.models import WorkflowOutput, QuestionResult

        sources = [
            {"title": "Doc A", "confidence": 0.9},
            {"title": "Doc A", "confidence": 0.9},  # duplicate
            {"title": "Doc B", "confidence": 0.8},
        ]
        qr = QuestionResult(answer="Answer.", confidence=0.9)
        output = WorkflowOutput(
            intent="question",
            question_result=qr,
            sources=sources,
            summary="test",
        )
        result = format_workflow_output([output])
        # Should show 2 unique sources, not 3
        assert result.count("Doc A") == 1
        assert "Doc B" in result


# ---------------------------------------------------------------------------
# web_runner
# ---------------------------------------------------------------------------

class TestWebRunner:
    """Verify the web_runner entry point."""

    def test_import_web_runner(self):
        """web_runner.py should import without errors."""
        import app.web_runner  # noqa: F401

    def test_web_runner_has_main(self):
        from app.web_runner import main
        assert callable(main)
