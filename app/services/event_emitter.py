"""
Platform Spec V4 — Event model. Events als lijm tussen agents, DB en Knowledge Graph.
Sectie 7.1. Geen externe queue; synchroon schrijven, asynchroon verwerken waar nodig.
"""
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
logger = logging.getLogger(__name__)


class EventType(str, Enum):
    # Task events
    TASK_CREATED = "TaskCreated"
    TASK_EVIDENCE_COLLECTED = "TaskEvidenceCollected"
    TASK_FIX_PROPOSED = "TaskFixProposed"
    TASK_VALIDATED = "TaskValidated"
    TASK_REJECTED = "TaskRejected"
    # Lesson events
    LESSON_PROPOSED = "LessonProposed"
    LESSON_APPROVED = "LessonApproved"
    LESSON_REJECTED = "LessonRejected"
    # Pattern events
    PATTERN_REGISTERED = "PatternRegistered"
    # Governance (V7)
    GOVERNANCE_BREACH_DETECTED = "GovernanceBreachDetected"


class EventEmitter:
    """Emit events naar events tabel. Defensief: emit mag NOOIT een job blokkeren."""

    async def emit(
        self,
        pool,
        event_type: EventType,
        agent_id: str | None = None,
        task_id: str | None = None,
        job_id: str | None = None,
        lesson_id: str | None = None,
        confidence_score: float | None = None,
        payload: dict | None = None,
    ) -> Optional[str]:
        """
        Schrijft event naar events tabel.
        Return: event_id (UUID als string), of None bij fout.

        Payload formaat (platform spec sectie 7.1) wordt aangevuld met
        event_type, timestamp, agent_id, task_id, lesson_id, confidence_score.
        """
        try:
            payload = dict(payload or {})
            payload["event_type"] = event_type.value
            payload["timestamp"] = datetime.now(timezone.utc).isoformat()
            if agent_id is not None:
                payload["agent_id"] = agent_id
            if task_id is not None:
                payload["task_id"] = task_id
            if lesson_id is not None:
                payload["lesson_id"] = lesson_id
            if confidence_score is not None:
                payload["confidence_score"] = confidence_score

            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO events (
                        event_type, agent_id, task_id, job_id, lesson_id,
                        confidence_score, payload
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                    RETURNING event_id
                    """,
                    event_type.value,
                    agent_id,
                    task_id,
                    job_id,
                    lesson_id,
                    confidence_score,
                    __import__("json").dumps(payload, default=lambda o: getattr(o, "isoformat", lambda: str(o))()),
                )
                if row and row["event_id"]:
                    return str(row["event_id"])
                return None
        except Exception as e:
            logger.warning("Event emit failed (non-blocking): %s", e)
            return None

    async def get_events_for_job(
        self,
        pool,
        job_id: str,
        event_types: list[EventType] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Haalt events op voor een job, optioneel gefilterd op event_type.
        Gesorteerd op created_at ASC (chronologisch).
        """
        try:
            async with pool.acquire() as conn:
                if event_types:
                    types = [t.value for t in event_types]
                    rows = await conn.fetch(
                        """
                        SELECT event_id, event_type, agent_id, task_id, job_id, lesson_id,
                               confidence_score, payload, created_at
                        FROM events
                        WHERE job_id = $1 AND event_type = ANY($2::text[])
                        ORDER BY created_at ASC
                        """,
                        job_id,
                        types,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT event_id, event_type, agent_id, task_id, job_id, lesson_id,
                               confidence_score, payload, created_at
                        FROM events
                        WHERE job_id = $1
                        ORDER BY created_at ASC
                        """,
                        job_id,
                    )
                return [_event_row_to_dict(r) for r in rows]
        except Exception as e:
            logger.warning("get_events_for_job failed: %s", e)
            return []

    async def get_events_for_task(
        self,
        pool,
        task_id: str,
    ) -> list[dict[str, Any]]:
        """Haalt alle events op voor een specifieke task."""
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT event_id, event_type, agent_id, task_id, job_id, lesson_id,
                           confidence_score, payload, created_at
                    FROM events
                    WHERE task_id = $1
                    ORDER BY created_at ASC
                    """,
                    task_id,
                )
                return [_event_row_to_dict(r) for r in rows]
        except Exception as e:
            logger.warning("get_events_for_task failed: %s", e)
            return []


def _event_row_to_dict(r) -> dict[str, Any]:
    created = r.get("created_at")
    return {
        "event_id": str(r["event_id"]) if r.get("event_id") else None,
        "event_type": r.get("event_type"),
        "agent_id": r.get("agent_id"),
        "task_id": r.get("task_id"),
        "job_id": r.get("job_id"),
        "lesson_id": r.get("lesson_id"),
        "confidence_score": float(r["confidence_score"]) if r.get("confidence_score") is not None else None,
        "payload": dict(r["payload"]) if r.get("payload") is not None else {},
        "created_at": created.isoformat() if created else None,
    }
