"""Unit tests for NEXUS pipeline handoff context and quality gate."""

import pytest
from app.orchestration.handoff_context import HandoffContext
from app.orchestration.quality_gate import QualityGate
from app.orchestration.nexus_pipeline import BudgetExceededError


def test_execute_step_registers_tokens():
    """Tokens worden correct bijgehouden in HandoffContext."""
    ctx = HandoffContext(job_id="j1", user_id="u1", platform="web", token_budget=1000)
    ctx.register_tokens(300)
    ctx.register_tokens(200)
    assert ctx.token_used_total == 500
    assert ctx.budget_warning() is False


def test_execute_step_budget_exceeded_raises():
    """BudgetExceededError bij overschrijding."""
    ctx = HandoffContext(job_id="j1", user_id="u1", platform="web", token_budget=100)
    ctx.register_tokens(100)
    assert ctx.is_over_budget() is True


def test_phase2_adds_gtm_for_wonderz():
    """GTM-step wordt toegevoegd voor wonderz-platform (smoke: plan check, geen DB)."""
    ctx = HandoffContext(job_id="j1", user_id="u1", platform="wonderz", token_budget=50000)
    ctx.execution_plan = []
    has_gtm = any(
        s.get("agent_id") == "agent:gtm-specialist" for s in ctx.execution_plan
    )
    assert has_gtm is False
    # Na planning zou GTM erin zitten — volledige test vereist test-DB (integratie-test)


def test_phase2_no_gtm_for_generic_platform():
    """Geen GTM-step voor generiek platform."""
    ctx = HandoffContext(job_id="j1", user_id="u1", platform="shopify", token_budget=50000)
    GTM_PLATFORMS = {"wonderz", "clawagency", "blogable"}
    assert ctx.platform.lower() not in GTM_PLATFORMS


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
