"""
app/agents/hr_manager.py
HR Manager Agent — Crew Intelligent
Spec: Product Spec v1.1, Sectie 6
"""

from datetime import datetime, timezone
from typing import Optional
import asyncpg


async def generate_point_id(conn: asyncpg.Connection) -> str:
    now = datetime.now(timezone.utc)
    prefix = f"DP-{now.year}-{now.month:02d}-"
    row = await conn.fetchrow(
        "SELECT point_id FROM development_points WHERE point_id LIKE $1 ORDER BY point_id DESC LIMIT 1",
        f"{prefix}%",
    )
    if row:
        return f"{prefix}{int(row['point_id'].split('-')[-1]) + 1:03d}"
    return f"{prefix}001"


async def generate_request_id(conn: asyncpg.Connection) -> str:
    now = datetime.now(timezone.utc)
    prefix = f"TR-{now.year}-"
    row = await conn.fetchrow(
        "SELECT request_id FROM training_requests WHERE request_id LIKE $1 ORDER BY request_id DESC LIMIT 1",
        f"{prefix}%",
    )
    if row:
        return f"{prefix}{int(row['request_id'].split('-')[-1]) + 1:03d}"
    return f"{prefix}001"


class HRManager:
    RETRY_THRESHOLD = 3

    def __init__(self, pool: asyncpg.pool.Pool):
        self.pool = pool

    async def scan_job_steps(self, since_days: int = 7) -> list[dict]:
        async with self.pool.acquire() as conn:
            retry_data = await conn.fetch(
                """
                SELECT agent_id, retry_reason, COUNT(*) AS freq,
                       (array_agg(job_id ORDER BY started_at NULLS LAST))[1] AS first_job
                FROM job_steps
                WHERE retry_count > 0
                  AND retry_reason IS NOT NULL AND retry_reason != ''
                  AND started_at > now() - ($1 || ' days')::interval
                  AND agent_id IS NOT NULL
                GROUP BY agent_id, retry_reason
                HAVING COUNT(*) >= $2
                ORDER BY freq DESC
                """,
                str(since_days), self.RETRY_THRESHOLD,
            )
            results = []
            dp_cols = await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='development_points'"
            )
            col_set = {r["column_name"] for r in dp_cols}
            has_proposed_by = "proposed_by" in col_set
            needs_agent_role = "agent_role" in col_set
            for row in retry_data:
                existing = await conn.fetchrow(
                    """
                    SELECT point_id, frequency FROM development_points
                    WHERE agent_id = $1 AND status = 'OPEN'
                      AND lower(trim(issue_description)) = lower(trim($2))
                    LIMIT 1
                    """,
                    row["agent_id"], row["retry_reason"],
                )
                if existing:
                    await conn.execute(
                        "UPDATE development_points SET frequency = frequency + $1 WHERE point_id = $2",
                        row["freq"], existing["point_id"],
                    )
                    results.append({"action": "incremented", "point_id": existing["point_id"],
                                    "agent_id": row["agent_id"], "new_frequency": existing["frequency"] + row["freq"]})
                else:
                    point_id = await generate_point_id(conn)
                    impact = "HIGH" if row["freq"] >= 10 else "MEDIUM" if row["freq"] >= 5 else "LOW"
                    agent_role_val = None
                    if needs_agent_role:
                        role_row = await conn.fetchrow(
                            "SELECT role FROM hired_agents WHERE agent_id = $1", row["agent_id"]
                        )
                        agent_role_val = (role_row["role"] if role_row else "") or ""
                    ev = f"Job {row['first_job']}, {row['freq']}x gezien in {since_days} dagen"
                    if has_proposed_by and needs_agent_role:
                        await conn.execute(
                            """
                            INSERT INTO development_points
                                (point_id, agent_id, agent_role, issue_description, evidence_example, frequency, impact, status, proposed_by)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, 'OPEN', 'hr-manager')
                            """,
                            point_id, row["agent_id"], agent_role_val, row["retry_reason"], ev, row["freq"], impact,
                        )
                    elif has_proposed_by:
                        await conn.execute(
                            """
                            INSERT INTO development_points
                                (point_id, agent_id, issue_description, evidence_example, frequency, impact, status, proposed_by)
                            VALUES ($1, $2, $3, $4, $5, $6, 'OPEN', 'hr-manager')
                            """,
                            point_id, row["agent_id"], row["retry_reason"], ev, row["freq"], impact,
                        )
                    elif needs_agent_role:
                        await conn.execute(
                            """
                            INSERT INTO development_points
                                (point_id, agent_id, agent_role, issue_description, evidence_example, frequency, impact, status)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, 'OPEN')
                            """,
                            point_id, row["agent_id"], agent_role_val, row["retry_reason"], ev, row["freq"], impact,
                        )
                    else:
                        await conn.execute(
                            """
                            INSERT INTO development_points
                                (point_id, agent_id, issue_description, evidence_example, frequency, impact, status)
                            VALUES ($1, $2, $3, $4, $5, $6, 'OPEN')
                            """,
                            point_id, row["agent_id"], row["retry_reason"], ev, row["freq"], impact,
                        )
                    results.append({"action": "created", "point_id": point_id,
                                    "agent_id": row["agent_id"], "issue": row["retry_reason"],
                                    "frequency": row["freq"], "impact": impact})
            return results

    async def scan_direct_chats(self, since_days: int = 7) -> list[dict]:
        """Scan direct_chat_messages for knowledge gap signals. Spec §8.1."""
        results = []
        async with self.pool.acquire() as conn:
            # Check if direct_chat_messages exists
            exists = await conn.fetchval(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'direct_chat_messages'"
            )
            if not exists:
                return results

            # Signal: agent repeatedly says "ik weet het niet" or similar
            unknow_rows = await conn.fetch(
                """
                SELECT dc.agent_id, COUNT(*) AS freq,
                       (array_agg(dcm.content ORDER BY dcm.created_at DESC))[1] AS sample
                FROM direct_chat_messages dcm
                JOIN direct_chats dc ON dcm.chat_id = dc.chat_id
                WHERE dcm.role = 'agent'
                  AND (
                    lower(dcm.content) LIKE '%ik weet het niet%'
                    OR lower(dcm.content) LIKE '%geen informatie%'
                    OR lower(dcm.content) LIKE '%niet beschikbaar%'
                  )
                  AND dcm.created_at > now() - ($1 || ' days')::interval
                GROUP BY dc.agent_id
                HAVING COUNT(*) >= 2
                """,
                str(since_days),
            )
            for row in unknow_rows:
                existing = await conn.fetchrow(
                    """
                    SELECT point_id FROM development_points
                    WHERE agent_id = $1 AND status = 'OPEN'
                      AND lower(issue_description) LIKE '%direct chat%'
                    LIMIT 1
                    """,
                    row["agent_id"],
                )
                if not existing:
                    point_id = await generate_point_id(conn)
                    dp_cols_chat = await conn.fetch(
                        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='development_points'"
                    )
                    col_set_chat = {r["column_name"] for r in dp_cols_chat}
                    has_proposed_by_chat = "proposed_by" in col_set_chat
                    needs_agent_role_chat = "agent_role" in col_set_chat
                    agent_role_chat = ""
                    if needs_agent_role_chat:
                        rrow = await conn.fetchrow("SELECT role FROM hired_agents WHERE agent_id = $1", row["agent_id"])
                        agent_role_chat = (rrow["role"] if rrow else "") or ""
                    desc = "Agent antwoordt herhaaldelijk met 'ik weet het niet' in Direct Chat"
                    sample = (row["sample"] or "")[:200]
                    if has_proposed_by_chat and needs_agent_role_chat:
                        await conn.execute(
                            """INSERT INTO development_points (point_id, agent_id, agent_role, issue_description, evidence_example, frequency, impact, status, proposed_by)
                            VALUES ($1, $2, $3, $4, $5, $6, 'MEDIUM', 'OPEN', 'hr-manager')""",
                            point_id, row["agent_id"], agent_role_chat, desc, sample, row["freq"],
                        )
                    elif has_proposed_by_chat:
                        await conn.execute(
                            """INSERT INTO development_points (point_id, agent_id, issue_description, evidence_example, frequency, impact, status, proposed_by)
                            VALUES ($1, $2, $3, $4, $5, 'MEDIUM', 'OPEN', 'hr-manager')""",
                            point_id, row["agent_id"], desc, sample, row["freq"],
                        )
                    elif needs_agent_role_chat:
                        await conn.execute(
                            """INSERT INTO development_points (point_id, agent_id, agent_role, issue_description, evidence_example, frequency, impact, status)
                            VALUES ($1, $2, $3, $4, $5, $6, 'MEDIUM', 'OPEN')""",
                            point_id, row["agent_id"], agent_role_chat, desc, sample, row["freq"],
                        )
                    else:
                        await conn.execute(
                            """INSERT INTO development_points (point_id, agent_id, issue_description, evidence_example, frequency, impact, status)
                            VALUES ($1, $2, $3, $4, $5, 'MEDIUM', 'OPEN')""",
                            point_id, row["agent_id"], desc, sample, row["freq"],
                        )
                    results.append({"action": "created", "point_id": point_id, "agent_id": row["agent_id"], "source": "direct_chat"})
        return results

    async def generate_weekly_report(self) -> dict:
        async with self.pool.acquire() as conn:
            agents = await conn.fetch(
                "SELECT * FROM hired_agents WHERE is_active = true AND is_suspended = false"
            )
            report = {}
            for agent in agents:
                aid = agent["agent_id"]
                open_points = await conn.fetch(
                    """
                    SELECT point_id, issue_description, root_cause, frequency,
                           impact, status, source_url, created_at
                    FROM development_points WHERE agent_id = $1 AND status = 'OPEN'
                    ORDER BY CASE impact WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, frequency DESC
                    """, aid,
                )
                stats = await conn.fetchrow(
                    """
                    SELECT COUNT(*) AS total_steps,
                           SUM(CASE WHEN retry_count > 0 THEN 1 ELSE 0 END) AS retried_steps,
                           AVG(timing_ms) AS avg_latency_ms,
                           COUNT(DISTINCT job_id) AS jobs_touched
                    FROM job_steps WHERE agent_id = $1
                      AND started_at > now() - interval '7 days'
                    """, aid,
                )
                try:
                    pending = await conn.fetch(
                        "SELECT request_id, reason, confidence_score, suggested_url, created_at FROM training_requests WHERE agent_id = $1 AND status IN ('PENDING', 'pending')",
                        aid,
                    )
                except Exception:
                    pending = []
                total = stats["total_steps"] or 0
                retried = stats["retried_steps"] or 0
                report[aid] = {
                    "agent_name": agent.get("name") or agent.get("agent_name", ""),
                    "role": agent["role"],
                    "open_points": _serialize(open_points), "open_points_count": len(open_points),
                    "pending_training_requests": _serialize(pending),
                    "performance": {
                        "retry_rate": round(retried / total, 3) if total > 0 else 0.0,
                        "retried_steps": retried, "total_steps": total,
                        "avg_latency_ms": round(stats["avg_latency_ms"] or 0),
                        "jobs_touched_7d": stats["jobs_touched"] or 0,
                    },
                }
            return {"generated_at": datetime.now(timezone.utc).isoformat(), "period_days": 7, "agents": report}

    async def create_training_request(self, agent_id, reason, confidence_score, suggested_url) -> dict:
        async with self.pool.acquire() as conn:
            rid = await generate_request_id(conn)
            await conn.execute(
                "INSERT INTO training_requests (request_id, agent_id, reason, confidence_score, suggested_url, status) VALUES ($1,$2,$3,$4,$5,'pending')",
                rid, agent_id, reason, confidence_score, suggested_url,
            )
            return {"request_id": rid, "status": "pending"}

    async def approve_training(self, request_id, approved_by, source_url) -> dict:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM training_requests WHERE request_id = $1", request_id)
            if not row: raise ValueError(f"Request {request_id} niet gevonden")
            if row["status"] not in ("PENDING", "pending"): raise ValueError(f"Status is {row['status']}, verwacht PENDING")
            final_url = source_url or row["suggested_url"]
            cols = await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'training_requests'"
            )
            col_names = {r["column_name"] for r in cols}
            if "approved_url" in col_names and "resolved_at" in col_names:
                await conn.execute(
                    "UPDATE training_requests SET status='approved', approved_by=$1, approved_url=$2, resolved_at=now() WHERE request_id=$3",
                    approved_by, final_url, request_id,
                )
            else:
                await conn.execute(
                    "UPDATE training_requests SET status='approved', approved_by=$1, approved_at=now() WHERE request_id=$2",
                    approved_by, request_id,
                )
            return {"request_id": request_id, "status": "approved", "agent_id": row["agent_id"], "training_url": final_url}

    async def reject_training(self, request_id, rejected_by) -> dict:
        async with self.pool.acquire() as conn:
            cols = await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'training_requests'"
            )
            col_names = {r["column_name"] for r in cols}
            if "resolved_at" in col_names:
                await conn.execute(
                    "UPDATE training_requests SET status='rejected', approved_by=$1, resolved_at=now() WHERE request_id=$2",
                    rejected_by, request_id,
                )
            else:
                await conn.execute(
                    "UPDATE training_requests SET status='rejected', approved_by=$1 WHERE request_id=$2",
                    rejected_by, request_id,
                )
            return {"request_id": request_id, "status": "rejected"}

    async def update_point_status(self, point_id, new_status, approved_by=None, source_url=None) -> dict:
        async with self.pool.acquire() as conn:
            sets = ["status = $1"]
            params: list = [new_status]
            idx = 2
            if approved_by: sets.append(f"approved_by = ${idx}"); params.append(approved_by); idx += 1
            if source_url: sets.append(f"source_url = ${idx}"); params.append(source_url); idx += 1
            if new_status == "RESOLVED": sets.append("resolved_at = now()")
            params.append(point_id)
            await conn.execute(f"UPDATE development_points SET {', '.join(sets)} WHERE point_id = ${idx}", *params)
            return {"point_id": point_id, "status": new_status}


def _serialize(rows) -> list[dict]:
    result = []
    for row in rows:
        d = dict(row)
        for k, v in d.items():
            if isinstance(v, datetime): d[k] = v.isoformat()
        result.append(d)
    return result
