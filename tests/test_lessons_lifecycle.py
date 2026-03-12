"""
Platform Spec V3 — LessonsLifecycle unit tests.
Test A: propose (lesson_id format, pending).
Test B: approve score >= 0.70 → active.
Test C: approve score < 0.70 → rejected.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.lessons_lifecycle import LessonsLifecycle, _role_prefix, _next_lesson_id_prefix


def test_role_prefix():
    assert _role_prefix("agent:frontend-engineer") == "FE"
    assert _role_prefix("agent:backend-engineer") == "BE"
    assert _role_prefix("agent:copywriter") == "CP"
    assert _role_prefix("agent:seo") == "SE"
    assert _role_prefix("other") == "GE"
    assert _role_prefix("") == "GE"


def test_next_lesson_id_prefix():
    p = _next_lesson_id_prefix("FE")
    assert p.startswith("FE-")
    assert len(p.split("-")) >= 3


def _mock_pool_with_conn():
    pool = MagicMock()
    conn = AsyncMock()
    acm = MagicMock()
    acm.__aenter__ = AsyncMock(return_value=conn)
    acm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = acm
    return pool, conn


@pytest.mark.asyncio
async def test_approve_high_score_returns_active():
    """Test B: approve met score 0.85 → lesson_status = 'active'."""
    pool, conn = _mock_pool_with_conn()
    conn.execute = AsyncMock()

    lifecycle = LessonsLifecycle()
    result = await lifecycle.approve(
        pool, "FE-2026-03-001", 0.85, "agent:talent", {}
    )
    assert result["approved"] is True
    assert result["lesson_id"] == "FE-2026-03-001"
    assert result["lesson_status"] == "active"


@pytest.mark.asyncio
async def test_approve_low_score_returns_rejected():
    """Test C: approve met score 0.65 → lesson_status = 'rejected'."""
    pool, conn = _mock_pool_with_conn()
    conn.execute = AsyncMock()

    lifecycle = LessonsLifecycle()
    result = await lifecycle.approve(
        pool, "BE-2026-03-002", 0.65, "agent:talent", {}
    )
    assert result["approved"] is False
    assert result["lesson_status"] == "rejected"
    assert "confidence_score" in result.get("reason", "")


@pytest.mark.asyncio
async def test_propose_returns_lesson_id_format():
    """Test A: propose returns lesson_id in format ROLE-YYYY-MM-###."""
    pool, conn = _mock_pool_with_conn()
    conn.execute = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)  # no existing lesson_id for next number
    # check_contradictions: fetchrow (new lesson), fetch (existing lessons)
    conn.fetchrow = AsyncMock(
        return_value={"title": "Bug in login", "gevonden": "Bug", "agent_id": "agent:copywriter"}
    )
    conn.fetch = AsyncMock(return_value=[])  # no conflicts

    lifecycle = LessonsLifecycle()
    worker_output = {
        "gevonden": "Bug in login",
        "oorzaak": "Missing check",
        "fix_voorstel": "Add guard",
        "volgende_actie": "Deploy",
    }
    lesson_id = await lifecycle.propose(pool, worker_output, "job-1", "agent:copywriter")
    assert lesson_id.startswith("CP-")
    parts = lesson_id.split("-")
    assert len(parts) >= 4
    assert parts[-1].isdigit()
