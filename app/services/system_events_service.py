"""
SystemEventsService
-------------------
Verantwoordelijk voor het loggen van operationele platform-events.

Architectuurnoot: Dit is GEEN vervanging van development_points.
- development_points  = agent-kwaliteitsproblemen, HR approval flow
- system_events       = orchestrator/platform fouten, operator monitoring

Gebruik: await system_events_service.log_event(...)
Vanuit routes: request.app.state.system_events
Vanuit pipeline/celery: get_system_events() (returns None als niet geïnitialiseerd)
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_global_instance: Optional["SystemEventsService"] = None


def set_global_instance(service: "SystemEventsService") -> None:
    """Zet de globale service (aan te roepen vanuit main.py lifespan)."""
    global _global_instance
    _global_instance = service


def get_system_events() -> Optional["SystemEventsService"]:
    """Voor code zonder request (job_pipeline, nexus_pipeline). Returns None als niet geïnitialiseerd."""
    return _global_instance


class SystemEventsService:

    # Event types (canonieke waarden, gebruik deze constanten)
    ORCHESTRATOR_ERROR = "orchestrator_error"
    TOKEN_BUDGET_EXCEEDED = "token_budget_exceeded"
    JOB_STALLED = "job_stalled"
    AGENT_TIMEOUT = "agent_timeout"
    VALIDATION_LOOP = "validation_loop"
    INTAKE_LOOP_DETECTED = "intake_loop_detected"
    TOOL_FAILURE = "tool_failure"
    SYSTEM_WARNING = "system_warning"

    # Severity levels
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    def __init__(self, db_pool):
        self.pool = db_pool

    async def log_event(
        self,
        event_type: str,
        message: str,
        severity: str = "warning",
        job_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Log een system event. Geeft het event_id terug, of None bij fout.
        Faalt altijd stilletjes: een logfout mag de normale flow nooit breken.
        """
        try:
            async with self.pool.acquire() as conn:
                event_id = await conn.fetchval(
                    """
                    INSERT INTO system_events
                        (event_type, severity, job_id, agent_id, message, details)
                    VALUES ($1, $2, $3::uuid, $4, $5, $6::jsonb)
                    RETURNING event_id
                    """,
                    event_type,
                    severity,
                    job_id,
                    agent_id,
                    message,
                    json.dumps(details or {}),
                )
                logger.info(
                    f"[SystemEvent] {severity.upper()} | {event_type} | "
                    f"job={job_id} | agent={agent_id} | {message}"
                )
                return str(event_id)
        except Exception as e:
            logger.error(f"[SystemEventsService] Kon event niet loggen: {e}")
            return None

    async def resolve_event(
        self,
        event_id: str,
        resolved_by: str = "operator",
    ) -> bool:
        """Markeer een event als opgelost."""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE system_events
                    SET resolved = true,
                        resolved_at = now(),
                        resolved_by = $2
                    WHERE event_id = $1::uuid AND resolved = false
                    """,
                    event_id,
                    resolved_by,
                )
                return result == "UPDATE 1"
        except Exception as e:
            logger.error(f"[SystemEventsService] Kon event niet resolven: {e}")
            return False

    async def get_events(
        self,
        job_id: Optional[str] = None,
        unresolved_only: bool = False,
        limit: int = 50,
    ) -> list:
        """Haal events op, optioneel gefilterd op job of openstaand."""
        try:
            conditions = []
            params = []

            if job_id:
                params.append(job_id)
                conditions.append("job_id = $1")

            if unresolved_only:
                conditions.append("resolved = false")

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            params.append(limit)
            limit_param = f"${len(params)}"

            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""
                    SELECT event_id, event_type, severity, job_id, agent_id,
                           message, details, resolved, resolved_at, resolved_by,
                           created_at
                    FROM system_events
                    {where}
                    ORDER BY created_at DESC
                    LIMIT {limit_param}
                    """,
                    *params,
                )
                out = []
                for row in rows:
                    d = dict(row)
                    if d.get("event_id") is not None:
                        d["event_id"] = str(d["event_id"])
                    if d.get("job_id") is not None:
                        d["job_id"] = str(d["job_id"])
                    if d.get("resolved_at") is not None and hasattr(d["resolved_at"], "isoformat"):
                        d["resolved_at"] = d["resolved_at"].isoformat()
                    if d.get("created_at") is not None and hasattr(d["created_at"], "isoformat"):
                        d["created_at"] = d["created_at"].isoformat()
                    out.append(d)
                return out
        except Exception as e:
            logger.error(f"[SystemEventsService] Kon events niet ophalen: {e}")
            return []
