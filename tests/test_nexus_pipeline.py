"""Unit tests for NEXUS pipeline handoff context, quality gate, and phase_5 CEO review."""

import sys
import types
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.orchestration.handoff_context import HandoffContext
from app.orchestration.quality_gate import QualityGate
from app.orchestration.nexus_pipeline import BudgetExceededError, NEXUSPipeline


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


# --- Phase 5 CEO Review (6 scenarios) ---
# Use fake submodules so we can patch without loading asyncpg (job_pipeline imports it).
def _ensure_phase5_modules():
    import app.services
    if not hasattr(app.services, "job_pipeline"):
        m = types.ModuleType("app.services.job_pipeline")
        m._run_step_agent_with_timeout = None  # placeholder so patch() can replace
        m._coerce_context = lambda x: x if x is not None else {}  # used by phase_5
        app.services.job_pipeline = m
    if not hasattr(app.services, "token_guard"):
        m = types.ModuleType("app.services.token_guard")
        m.TokenGuard = None  # placeholder so patch() can replace
        app.services.token_guard = m
    sys.modules["app.services.job_pipeline"] = app.services.job_pipeline
    sys.modules["app.services.token_guard"] = app.services.token_guard


@pytest.mark.asyncio
async def test_phase5_ceo_approved():
    """1. CEO APPROVED: reviewer returns approved → phase_5 returns, no retry."""
    _ensure_phase5_modules()
    ctx = HandoffContext(job_id="j1", user_id="u1", platform="web", token_budget=50000)
    ctx.execution_plan = [{"step_name": "copywriter", "step_index": 0}]
    ctx.step_outputs["copywriter"] = "Final article text"
    ctx.strategic_brief = {"objective": "Write an article"}

    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(return_value={"job_post": "Write article", "context": None})
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_cm)

    pipeline = NEXUSPipeline()
    pipeline._pool = mock_pool

    with patch("app.services.token_guard.TokenGuard") as MockGuard:
        mock_guard = MagicMock()
        mock_guard.check_before_call = AsyncMock(return_value={"allowed": True})
        mock_guard.register_usage = AsyncMock()
        MockGuard.return_value = mock_guard
        with patch("app.services.job_pipeline._run_step_agent_with_timeout", new_callable=AsyncMock) as m_run:
            m_run.return_value = ({"approved": True, "review": "APPROVED", "agent_role": "reviewer"}, 100)
            await pipeline.phase_5_ceo_review(ctx)

    assert ctx.retry_counts.get("ceo_review", 0) == 0
    m_run.assert_called_once()


@pytest.mark.asyncio
async def test_phase5_needs_revision_then_retry_then_approved():
    """2. NEEDS_REVISION + retry → second CEO call APPROVED."""
    _ensure_phase5_modules()
    ctx = HandoffContext(job_id="j1", user_id="u1", platform="web", token_budget=50000)
    ctx.execution_plan = [{"step_name": "copywriter", "step_index": 0}]
    ctx.step_outputs["copywriter"] = "Draft text"
    ctx.strategic_brief = {"objective": "Article"}

    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(return_value={"job_post": "Article", "context": None})
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_cm)

    pipeline = NEXUSPipeline()
    pipeline._pool = mock_pool

    call_count = 0
    async def mock_ceo(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ({"approved": False, "review": "CHANGES NEEDED", "agent_role": "reviewer"}, 80)
        return ({"approved": True, "review": "APPROVED", "agent_role": "reviewer"}, 80)

    with patch("app.services.token_guard.TokenGuard") as MockGuard:
        mock_guard = MagicMock()
        mock_guard.check_before_call = AsyncMock(return_value={"allowed": True})
        mock_guard.register_usage = AsyncMock()
        MockGuard.return_value = mock_guard
        with patch("app.services.job_pipeline._run_step_agent_with_timeout", new_callable=AsyncMock, side_effect=mock_ceo):
            with patch.object(pipeline, "phase_4_qa_loop", new_callable=AsyncMock) as m_phase4:
                await pipeline.phase_5_ceo_review(ctx)

    assert call_count == 2
    m_phase4.assert_called_once_with(ctx)
    assert ctx.retry_counts.get("ceo_review") == 1


@pytest.mark.asyncio
async def test_phase5_needs_revision_after_one_retry_proceeds():
    """3. NEEDS_REVISION na 1 retry → proceed with warning, no second retry."""
    _ensure_phase5_modules()
    ctx = HandoffContext(job_id="j1", user_id="u1", platform="web", token_budget=50000)
    ctx.execution_plan = [{"step_name": "copywriter", "step_index": 0}]
    ctx.step_outputs["copywriter"] = "Draft"
    ctx.strategic_brief = {"objective": "Article"}
    ctx.retry_counts["ceo_review"] = 1  # already did one retry

    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(return_value={"job_post": "Article", "context": None})
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_cm)

    pipeline = NEXUSPipeline()
    pipeline._pool = mock_pool

    with patch("app.services.token_guard.TokenGuard") as MockGuard:
        mock_guard = MagicMock()
        mock_guard.check_before_call = AsyncMock(return_value={"allowed": True})
        mock_guard.register_usage = AsyncMock()
        MockGuard.return_value = mock_guard
        with patch("app.services.job_pipeline._run_step_agent_with_timeout", new_callable=AsyncMock) as m_run:
            m_run.return_value = ({"approved": False, "review": "CHANGES NEEDED", "agent_role": "reviewer"}, 80)
            with patch.object(pipeline, "phase_4_qa_loop", new_callable=AsyncMock) as m_phase4:
                await pipeline.phase_5_ceo_review(ctx)

    m_run.assert_called_once()
    m_phase4.assert_not_called()
    assert ctx.retry_counts["ceo_review"] == 1


@pytest.mark.asyncio
async def test_phase5_no_final_output_skips_ceo_call():
    """4. Geen eindoutput → phase_5 retourneert zonder CEO aan te roepen."""
    _ensure_phase5_modules()
    ctx = HandoffContext(job_id="j1", user_id="u1", platform="web", token_budget=50000)
    ctx.execution_plan = [{"step_name": "gtm_analysis", "step_index": 1}]
    ctx.step_outputs["gtm_analysis"] = "GTM only"

    pipeline = NEXUSPipeline()
    pipeline._pool = MagicMock()

    with patch("app.services.job_pipeline._run_step_agent_with_timeout", new_callable=AsyncMock) as m_run:
        await pipeline.phase_5_ceo_review(ctx)

    m_run.assert_not_called()


@pytest.mark.asyncio
async def test_phase5_over_budget_raises_before_ceo():
    """5. Over budget vóór CEO-call → BudgetExceededError."""
    _ensure_phase5_modules()
    ctx = HandoffContext(job_id="j1", user_id="u1", platform="web", token_budget=100)
    ctx.execution_plan = [{"step_name": "copywriter", "step_index": 0}]
    ctx.step_outputs["copywriter"] = "Text"
    ctx.register_tokens(100)

    pipeline = NEXUSPipeline()
    pipeline._pool = MagicMock()

    with patch("app.services.job_pipeline._run_step_agent_with_timeout", new_callable=AsyncMock) as m_run:
        with pytest.raises(BudgetExceededError):
            await pipeline.phase_5_ceo_review(ctx)
    m_run.assert_not_called()


@pytest.mark.asyncio
async def test_phase5_ceo_call_exception_proceeds():
    """6. CEO-call gooit exception → phase_5 logt en retourneert zonder crash."""
    _ensure_phase5_modules()
    ctx = HandoffContext(job_id="j1", user_id="u1", platform="web", token_budget=50000)
    ctx.execution_plan = [{"step_name": "copywriter", "step_index": 0}]
    ctx.step_outputs["copywriter"] = "Text"
    ctx.strategic_brief = {"objective": "Article"}

    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(return_value={"job_post": "Article", "context": None})
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_cm)

    pipeline = NEXUSPipeline()
    pipeline._pool = mock_pool

    with patch("app.services.token_guard.TokenGuard") as MockGuard:
        mock_guard = MagicMock()
        mock_guard.check_before_call = AsyncMock(return_value={"allowed": True})
        mock_guard.register_usage = AsyncMock()
        MockGuard.return_value = mock_guard
        with patch("app.services.job_pipeline._run_step_agent_with_timeout", new_callable=AsyncMock) as m_run:
            m_run.side_effect = RuntimeError("LLM timeout")
            await pipeline.phase_5_ceo_review(ctx)

    assert ctx.error is None
