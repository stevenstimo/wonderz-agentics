"""
Platform Spec V7 — GovernanceMonitor unit tests.
A: check met lege metrics → breaches_found=0
B: agent met approval_rate=0.90 → HIGH_RISK_RUBBER_STAMP, suspend + breach insert
C: agent met evidence_rate=0.60 → LOW_EVIDENCE_VERIFICATION, suspended
D: release_suspension → is_suspended=false, reason contains released_by
E: agent al gesuspendeerd → _suspend_agent returns False
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.governance_monitor import GovernanceMonitor


def _mock_pool(fetch_return=None, execute_return="UPDATE 0"):
    pool = MagicMock()
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=fetch_return or [])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value=execute_return)
    conn.fetchval = AsyncMock(return_value=1)  # table exists
    acm = MagicMock()
    acm.__aenter__ = AsyncMock(return_value=conn)
    acm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = acm
    return pool, conn


@pytest.mark.asyncio
async def test_check_empty_metrics_no_breaches():
    """Test A: Geen reviews / lege metrics → breaches_found=0, agents_suspended=0."""
    pool, conn = _mock_pool(fetch_return=[])
    monitor = GovernanceMonitor()
    result = await monitor.check_talent_integrity(pool)
    assert result["breaches_found"] == 0
    assert result["agents_suspended"] == 0
    assert result["tasks_blocked"] == 0
    assert conn.execute.call_count == 0


@pytest.mark.asyncio
async def test_check_high_approval_rate_breach_suspend_and_insert():
    """Test B: approval_rate=0.90 → HIGH_RISK_RUBBER_STAMP, _suspend_agent called, governance_breaches INSERT."""
    pool, conn = _mock_pool(
        fetch_return=[
            {
                "talent_agent_id": "agent:talent-test",
                "approval_rate": 0.90,
                "evidence_verification_rate": 0.80,
                "monitoring_status": "HIGH_RISK_RUBBER_STAMP",
                "total_reviews": 10,
            }
        ],
        execute_return="UPDATE 1",
    )
    conn.fetchrow = AsyncMock(return_value={"specialization": "gtm"})
    monitor = GovernanceMonitor()
    mock_suspend = AsyncMock(return_value=True)
    mock_block = AsyncMock(return_value=0)
    with patch.object(monitor, "_suspend_agent", mock_suspend):
        with patch.object(monitor, "_block_domain_tasks", mock_block):
            with patch("app.services.governance_monitor.EventEmitter") as Emitter:
                emitter = MagicMock()
                emitter.emit = AsyncMock(return_value="ev-1")
                Emitter.return_value = emitter
                result = await monitor.check_talent_integrity(pool)
    assert result["breaches_found"] == 1
    assert result["agents_suspended"] == 1
    mock_suspend.assert_called_once()
    args, kwargs = mock_suspend.call_args
    assert args[0] == pool
    assert args[1] == "agent:talent-test"
    reason = args[2] if len(args) > 2 else (kwargs.get("reason") or "")
    assert "HIGH_RISK_RUBBER_STAMP" in reason or "0.90" in reason
    insert_calls = [c for c in conn.execute.call_args_list if c[0] and "INSERT INTO governance_breaches" in str(c[0][0])]
    assert len(insert_calls) >= 1


@pytest.mark.asyncio
async def test_check_low_evidence_rate_breach():
    """Test C: evidence_verification_rate=0.60 (< 0.70) → LOW_EVIDENCE_VERIFICATION, suspended."""
    pool, conn = _mock_pool(
        fetch_return=[
            {
                "talent_agent_id": "agent:evidence-low",
                "approval_rate": 0.70,
                "evidence_verification_rate": 0.60,
                "monitoring_status": "NORMAL",
                "total_reviews": 8,
            }
        ],
        execute_return="UPDATE 1",
    )
    conn.fetchrow = AsyncMock(return_value={"specialization": "sales"})
    monitor = GovernanceMonitor()
    mock_suspend = AsyncMock(return_value=True)
    with patch.object(monitor, "_suspend_agent", mock_suspend):
        with patch.object(monitor, "_block_domain_tasks", new_callable=AsyncMock, return_value=0):
            with patch("app.services.governance_monitor.EventEmitter") as Emitter:
                emitter = MagicMock()
                emitter.emit = AsyncMock(return_value="ev-1")
                Emitter.return_value = emitter
                result = await monitor.check_talent_integrity(pool)
    assert result["breaches_found"] == 1
    assert result["agents_suspended"] == 1
    mock_suspend.assert_called_once()
    assert mock_suspend.call_args[0][1] == "agent:evidence-low"


@pytest.mark.asyncio
async def test_release_suspension_appends_released_by():
    """Test D: release_suspension → is_suspended=false, suspension_reason bevat 'released_by=test_user'."""
    pool, conn = _mock_pool(execute_return="UPDATE 1")
    conn.fetchval = AsyncMock(return_value="original reason")
    monitor = GovernanceMonitor()
    released = await monitor.release_suspension(pool, "agent:test", "test_user")
    assert released is True
    execute_calls = conn.execute.call_args_list
    assert len(execute_calls) >= 1
    call = execute_calls[0]
    sql = call[0][0]
    args = call[0][1:] if len(call[0]) > 1 else []
    assert "is_suspended = false" in sql or "is_suspended = false" in sql.lower()
    assert "released_by=test_user" in (args[0] if args else "") or "released_by" in str(args)


@pytest.mark.asyncio
async def test_suspend_agent_already_suspended_returns_false():
    """Test E: Agent al gesuspendeerd → _suspend_agent retourneert False (UPDATE 0)."""
    pool, conn = _mock_pool(execute_return="UPDATE 0")
    monitor = GovernanceMonitor()
    result = await monitor._suspend_agent(pool, "agent:already-suspended", "some reason")
    assert result is False
