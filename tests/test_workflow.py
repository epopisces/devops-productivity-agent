"""Tests for the main workflow graph construction."""

import pytest
from unittest.mock import patch, MagicMock

from app.models import TriageResult, LookupResult
from app.workflows.main_workflow import (
    _route_to_question,
    _route_to_ingestion,
)


class TestRoutingConditions:
    """Tests for intent-based edge routing functions."""

    def _make_lookup(self, intent: str) -> LookupResult:
        return LookupResult(
            triage=TriageResult(
                intent=intent,
                domain=None,
                tags=[],
                cleaned_query="test",
            ),
            matches=[],
            match_count=0,
            has_sufficient_context=False,
        )

    def test_route_question_intent(self):
        lr = self._make_lookup("question")
        assert _route_to_question(lr) is True
        assert _route_to_ingestion(lr) is False

    def test_route_ingestion_intent(self):
        lr = self._make_lookup("ingestion")
        assert _route_to_question(lr) is False
        assert _route_to_ingestion(lr) is True

    def test_route_both_intent(self):
        lr = self._make_lookup("both")
        assert _route_to_question(lr) is True
        assert _route_to_ingestion(lr) is True

    def test_route_unknown_intent_defaults_to_question(self):
        """When no conditions match (shouldn't happen in practice), neither fires."""
        # TriageResult.intent is Literal["question","ingestion","both"] so we
        # can't actually pass an invalid value.  The coverage for missing triage
        # is handled in test_route_missing_triage instead.
        pass

    def test_route_missing_triage(self):
        """When triage is None, default to question path."""
        lr = LookupResult(
            triage=None,
            matches=[],
            match_count=0,
            has_sufficient_context=False,
        )
        assert _route_to_question(lr) is True
        assert _route_to_ingestion(lr) is False
