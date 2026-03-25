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


async def _find_candidates_for_role_key(
    conn: asyncpg.Connection,
    missing_role_key: str,
    missing_role_label: str,
    *,
    min_readiness: int = 70,
    limit: int = 8,
) -> list[dict[str, Any]]:
    missing_key_norm = _norm(missing_role_key)
    missing_label_norm = _norm(missing_role_label)
    if not missing_key_norm and not missing_label_norm:
        return []

    rows = await conn.fetch(
        """
        SELECT newbie_id, newbie_name, suggested_role, readiness_score
        FROM newbies
        WHERE status = 'ready'
          AND readiness_score >= $1
          AND suggested_role IS NOT NULL
          AND trim(suggested_role) <> ''
        ORDER BY readiness_score DESC
        LIMIT 200
        """,
        min_readiness,
    )

    def match(suggested_role: Any) -> bool:
        suggested_norm = _norm(suggested_role)
        if not suggested_norm:
            return False
        # Either key matches label, or label matches suggested, or suggested contains either.
        return (
            (missing_key_norm and suggested_norm.find(missing_key_norm) >= 0)
            or (missing_label_norm and suggested_norm.find(missing_label_norm) >= 0)
            or (missing_key_norm and missing_key_norm.find(suggested_norm) >= 0)
            or (missing_label_norm and missing_label_norm.find(suggested_norm) >= 0)
        )

    out: list[dict[str, Any]] = []
    for r in rows:
        if match(r.get("suggested_role")):
            out.append(
                {
                    "newbie_id": r["newbie_id"],
                    "newbie_name": r["newbie_name"],
                    "suggested_role": r.get("suggested_role"),
                    "readiness_score": int(r.get("readiness_score") or 0),
                }
            )
            if len(out) >= limit:
                break

    return out


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

        # Dedupe on (job_id + missing_role_key) while OPEN.
        job_need = json.dumps(job_id_str)
        key_need = json.dumps(missing_role_key)
        needle = f"%{{\\\"job_id\\\":{job_need}%\"missing_role_key\\\":{key_need}%}}%"
        # The above is too brittle for JSON order; use a simpler combined needle:
        needle = f'%\"job_id\":\"{job_id_str}\"%' + f'%\"missing_role_key\":\"{missing_role_key}\"%'

        existing = await conn.fetchrow(
            """
            SELECT id
            FROM agent_improvements
            WHERE source = 'hr_blocked_job_notifier'
              AND status = 'OPEN'
              AND details::text LIKE $1
            LIMIT 1
            """,
            needle,
        )

        severity = "HIGH" if len(missing_entries) >= 2 else "MEDIUM"
        title = f"HR: BLOCKED job ontbreekt rol — {missing_role_label}"

        try:
            if existing:
                await conn.execute(
                    """
                    UPDATE agent_improvements
                    SET agent_name = $1,
                        title = $2,
                        summary = $3,
                        details = $4,
                        severity = $5,
                        updated_at = now()
                    WHERE id = $6
                    """,
                    missing_role_label,
                    title,
                    block_reason,
                    details,
                    severity,
                    existing["id"],
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO agent_improvements
                        (agent_id, agent_name, title, summary, details, severity, status, source)
                    VALUES
                        ($1, $2, $3, $4, $5, $6, 'OPEN', 'hr_blocked_job_notifier')
                    """,
                    missing_role_key,
                    missing_role_label,
                    title,
                    block_reason,
                    details,
                    severity,
                )
        except Exception:
            logger.exception(
                "[HR blocked notifier] failed to insert/update improvement job=%s role=%s",
                job_id_str,
                missing_role_key,
            )

    logger.info(
        "[HR blocked notifier] processed job=%s missing_roles=%d",
        job_id_str,
        len(missing_entries),
    )

