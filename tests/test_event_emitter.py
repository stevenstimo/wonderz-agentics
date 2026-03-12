"""
Platform Spec V4 — EventEmitter unit tests.
Stap 1: emit returns event_id, row in DB.
Stap 2: Failsafe: invalid pool → no exception, returns None, warning logged.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.event_emitter import EventEmitter, EventType


def _mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    acm = MagicMock()
    acm.__aenter__ = AsyncMock(return_value=conn)
    acm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = acm
    return pool, conn


@pytest.mark.asyncio
async def test_emit_returns_event_id_and_row_in_db():
    """Stap 1: emit LESSON_APPROVED → event_id not None, SELECT returns row."""
    pool, conn = _mock_pool()
    from uuid import uuid4
    fake_id = uuid4()
    conn.fetchrow = AsyncMock(
        return_value={"event_id": fake_id}
    )

    emitter = EventEmitter()
    event_id = await emitter.emit(
        pool,
        EventType.LESSON_APPROVED,
        agent_id="agent:test",
        lesson_id="TEST-001",
        confidence_score=0.85,
    )

    assert event_id is not None
    assert event_id == str(fake_id)
    assert conn.fetchrow.called
    # fetchrow(sql, *params): params are event_type, agent_id, task_id, job_id, lesson_id, confidence_score, payload_json
    call_args = conn.fetchrow.call_args[0]
    assert call_args[1] == "LessonApproved"
    assert call_args[2] == "agent:test"
    assert call_args[3] is None  # task_id
    assert call_args[4] is None  # job_id
    assert call_args[5] == "TEST-001"
    assert call_args[6] == 0.85


@pytest.mark.asyncio
async def test_emit_failsafe_invalid_pool_returns_none():
    """Stap 2: Emit with failing pool → no exception, returns None, warning logged."""
    pool = MagicMock()
    acm = MagicMock()
    acm.__aenter__ = AsyncMock(side_effect=Exception("DB connection failed"))
    acm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = acm

    emitter = EventEmitter()
    with patch("app.services.event_emitter.logger") as mock_log:
        event_id = await emitter.emit(
            pool,
            EventType.TASK_CREATED,
            agent_id="agent:test",
            task_id="job-1",
            job_id="job-1",
        )

    assert event_id is None
    mock_log.warning.assert_called_once()
    assert "Event emit failed" in str(mock_log.warning.call_args)


@pytest.mark.asyncio
async def test_get_events_for_job_empty():
    """get_events_for_job with no rows returns []."""
    pool, conn = _mock_pool()
    conn.fetch = AsyncMock(return_value=[])

    emitter = EventEmitter()
    events = await emitter.get_events_for_job(pool, "job-123")
    assert events == []


@pytest.mark.asyncio
async def test_get_events_for_job_with_type_filter():
    """get_events_for_job with event_types filters correctly."""
    pool, conn = _mock_pool()
    from datetime import datetime, timezone
    row = {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "event_type": "TaskValidated",
        "agent_id": "agent:talent",
        "task_id": "job-1",
        "job_id": "job-1",
        "lesson_id": None,
        "confidence_score": 0.92,
        "payload": {},
        "created_at": datetime.now(timezone.utc),
    }
    conn.fetch = AsyncMock(return_value=[row])

    emitter = EventEmitter()
    events = await emitter.get_events_for_job(
        pool, "job-1", event_types=[EventType.TASK_VALIDATED]
    )
    assert len(events) == 1
    assert events[0]["event_type"] == "TaskValidated"
    assert events[0]["confidence_score"] == 0.92
