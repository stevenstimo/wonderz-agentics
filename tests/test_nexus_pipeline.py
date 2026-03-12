"""Unit tests for NEXUS pipeline handoff context and quality gate."""

import pytest
from app.orchestration.handoff_context import HandoffContext
from app.orchestration.quality_gate import QualityGate


def test_handoff_context_budget():
    ctx = HandoffContext(
        job_id="test", user_id="u1", platform="web", token_budget=1000
    )
    ctx.register_tokens(800)
    assert ctx.budget_warning() is True
    assert ctx.is_over_budget() is False
    ctx.register_tokens(200)
    assert ctx.is_over_budget() is True


def test_handoff_context_retry():
    ctx = HandoffContext(job_id="test", user_id="u1", platform="web")
    assert ctx.can_retry("copy_agent") is True
    ctx.increment_retry("copy_agent")
    ctx.increment_retry("copy_agent")
    ctx.increment_retry("copy_agent")
    assert ctx.can_retry("copy_agent") is False


def test_quality_gate_approved():
    gate = QualityGate()
    score = gate.evaluate(
        "copy_agent", "APPROVED: De tekst voldoet aan alle eisen."
    )
    assert score == 1.0
    assert gate.passes("copy_agent", score) is True


def test_quality_gate_needs_changes():
    gate = QualityGate()
    score = gate.evaluate("copy_agent", "NEEDS_CHANGES: Pas de toon aan.")
    assert score < 0.70
    assert gate.passes("copy_agent", score) is False
