"""
HR notifier — BLOCKED jobs → agent_improvements for HR dashboard.

Pattern: create OPEN agent_improvements rows in `agent_improvements.details` with
missing role + candidate newbie list.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import asyncpg

from app.orchestration.ceo_intent import detect_job_type

logger = logging.getLogger(__name__)


def _norm(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip().lower().replace("_", " ").replace("-", " ")


def _parse_missing_role_key(entry: Any) -> Optional[str]:
    if entry is None:
        return None
    if not isinstance(entry, str):
        entry = str(entry)
    s = entry.strip()
    if not s:
        return None
    if ":" in s:
        return s.split(":", 1)[0].strip() or None
    return s


def _safe_json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _newbie_id_ilike_pattern_for_missing_slot(
    missing_role_key: str, missing_role_label: str
) -> Optional[str]:
    """
    Match kandidaten op newbie_id (bv. agent:talent:… / agent:worker:…), niet op suggested_role
    (die is vaak null). Reviewer/talent-slots → %talent%; overige worker-slots → %worker%.
    """
    combined = _norm(missing_role_key) + " " + _norm(missing_role_label)
    if not combined.strip():
        return None
    # Reviewer / QA / talent-slots → talent-pool in newbie_id
    if any(
        w in combined
        for w in (
            "reviewer",
            "talent",
            "qa",
            "quality",
        )
    ):
        return "%talent%"
    # CEO/COO: geen talent/worker newbie-pool voor hire-suggestie
    if any(w in combined for w in ("ceo", "coo")):
        return None
    return "%worker%"


async def _find_candidates_for_role_key(
    conn: asyncpg.Connection,
    missing_role_key: str,
    missing_role_label: str,
    *,
    min_readiness: int = 0,
    limit: int = 8,
) -> list[dict[str, Any]]:
    pattern = _newbie_id_ilike_pattern_for_missing_slot(missing_role_key, missing_role_label)
    if not pattern:
        return []

    rows = await conn.fetch(
        """
        SELECT newbie_id, newbie_name, suggested_role, readiness_score, status
        FROM newbies
        WHERE status NOT IN ('hired', 'rejected')
          AND COALESCE(readiness_score, 0) >= $1
          AND newbie_id ILIKE $2
        ORDER BY readiness_score DESC NULLS LAST, newbie_name
        LIMIT $3
        """,
        min_readiness,
        pattern,
        limit,
    )

    return [
        {
            "newbie_id": r["newbie_id"],
            "newbie_name": r["newbie_name"],
            "suggested_role": r.get("suggested_role"),
            "readiness_score": int(r.get("readiness_score") or 0),
            "status": r.get("status"),
        }
        for r in rows
    ]


async def notify_blocked_job_improvements(
    conn: asyncpg.Connection,
    job_id: str,
    block_reason: str,
    missing_roles: list[str],
) -> None:
    """
    Create or refresh OPEN agent_improvements rows for each missing role in a BLOCKED job.
    """
    try:
        job = await conn.fetchrow(
            "SELECT job_post FROM jobs WHERE id = $1::uuid",
            job_id,
        )
    except Exception:
        logger.exception("[HR blocked notifier] failed to load job_post for job=%s", job_id)
        return

    job_post = job.get("job_post") if job else ""
    preset_id = None
    try:
        preset_id = await detect_job_type(conn, job_post)
    except Exception:
        logger.exception("[HR blocked notifier] detect_job_type failed job=%s", job_id)

    # Load preset slots so we can map slot keys → human labels.
    slot_role_by_key: dict[str, str] = {}
    if preset_id:
        try:
            row = await conn.fetchrow(
                """
                SELECT agent_slots
                FROM job_type_presets
                WHERE preset_id = $1 AND is_active = true
                """,
                preset_id,
            )
            agent_slots = row.get("agent_slots") if row else []
            if isinstance(agent_slots, list):
                for slot in agent_slots:
                    if not isinstance(slot, dict):
                        continue
                    key = str(slot.get("slot") or "").strip()
                    if not key:
                        continue
                    role_label = str(slot.get("role") or "").strip()
                    if role_label:
                        slot_role_by_key[key] = role_label
        except Exception:
            logger.exception("[HR blocked notifier] failed to load preset slots job=%s", job_id)

    # For each missing role key, create an OPEN agent_improvements row with candidates.
    missing_entries: list[str] = [m for m in (missing_roles or []) if isinstance(m, str) and m.strip()]
    if not missing_entries:
        return

    job_id_str = str(job_id)
    for entry in missing_entries:
        missing_role_key = _parse_missing_role_key(entry) or entry.strip()
        if not missing_role_key:
            continue

        missing_role_label = slot_role_by_key.get(missing_role_key, missing_role_key)
        candidates = await _find_candidates_for_role_key(
            conn, missing_role_key, missing_role_label
        )

        details_obj = {
            "job_id": job_id_str,
            "preset_id": preset_id,
            "block_reason": block_reason,
            "missing_role_key": missing_role_key,
            "missing_role_label": missing_role_label,
            "missing_roles_raw": missing_entries,
            "candidates": candidates,
        }
        details = _safe_json_dumps(details_obj)

        severity = "HIGH" if len(missing_entries) >= 2 else "MEDIUM"
        title = f"HR: BLOCKED job ontbreekt rol — {missing_role_label}"

        # Atomisch upsert: voorkomt dubbele rijen bij gelijktijdige calls (job_pipeline + nexus_pipeline).
        # Vereist migratie 050: uq_agent_improvements_hr_blocked_job_role + kolommen hr_*.
        try:
            await conn.execute(
                """
                INSERT INTO agent_improvements (
                    agent_id,
                    agent_name,
                    title,
                    summary,
                    details,
                    severity,
                    status,
                    source,
                    hr_blocked_job_id,
                    hr_missing_role_key
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, 'OPEN', 'hr_blocked_job_notifier',
                    $7::uuid, $8
                )
                ON CONFLICT (hr_blocked_job_id, hr_missing_role_key)
                    WHERE hr_blocked_job_id IS NOT NULL AND hr_missing_role_key IS NOT NULL
                DO UPDATE SET
                    agent_name = EXCLUDED.agent_name,
                    title = EXCLUDED.title,
                    summary = EXCLUDED.summary,
                    details = EXCLUDED.details,
                    severity = EXCLUDED.severity,
                    updated_at = now()
                """,
                missing_role_key,
                missing_role_label,
                title,
                block_reason,
                details,
                severity,
                job_id_str,
                missing_role_key,
            )
        except Exception:
            logger.exception(
                "[HR blocked notifier] failed to upsert improvement job=%s role=%s",
                job_id_str,
                missing_role_key,
            )

    logger.info(
        "[HR blocked notifier] processed job=%s missing_roles=%d",
        job_id_str,
        len(missing_entries),
    )

