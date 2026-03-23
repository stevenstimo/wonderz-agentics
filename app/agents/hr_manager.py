"""
app/agents/hr_manager.py
HR Manager Agent — Crew Intelligent
Spec: Product Spec v1.1, Sectie 6
P8: A/B validation + Cross-agent learning
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Any
import asyncpg

logger = logging.getLogger(__name__)


def _json_array(ids: list) -> str:
    return json.dumps(ids)


def _agent_improvement_to_legacy(row: dict) -> dict:
    """Map agent_improvements row to legacy keys for API compatibility."""
    out = {
        "point_id": str(row.get("id", "")),
        "issue_description": row.get("title") or "",
        "root_cause": row.get("summary"),
        "frequency": 1,
        "impact": (row.get("severity") or "low").lower(),
        "status": (row.get("status") or "OPEN").upper(),
        "source_url": row.get("source_url") or row.get("source"),
        "created_at": row.get("created_at"),
    }
    if out.get("created_at") and hasattr(out["created_at"], "isoformat"):
        out["created_at"] = out["created_at"].isoformat()
    return out


async def _generate_improvement_id(conn: asyncpg.Connection) -> str:
    """Generate a new UUID for agent_improvements.id (table uses id uuid primary key)."""
    import uuid
    return str(uuid.uuid4())


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

    async def _maybe_trigger_resource_discovery(
        self,
        conn: asyncpg.Connection,
        point_id: str,
        agent_id: str,
        agent_role: str,
        pattern_description: str,
        impact: str,
    ) -> None:
        """Trigger discovery only for high/critical impact, never blocking point creation."""
        impact_norm = (impact or "").strip().lower()
        if impact_norm not in {"high", "critical"}:
            return
        try:
            from app.services.hr_resource_discovery import HRResourceDiscovery

            discovery = HRResourceDiscovery()
            await discovery.discover_for_development_point(
                conn=conn,
                development_point_id=point_id,
                agent_id=agent_id,
                agent_role=agent_role or "",
                pattern_description=pattern_description or "",
                impact=impact_norm,
            )
        except Exception as exc:
            logger.warning(
                "[HRManager] resource discovery failed for point=%s agent=%s impact=%s: %s",
                point_id,
                agent_id,
                impact_norm,
                exc,
            )

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
            ai_cols = await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='agent_improvements'"
            )
            col_set = {r["column_name"] for r in ai_cols}
            has_source = "source_url" in col_set or "source" in col_set
            for row in retry_data:
                existing = await conn.fetchrow(
                    """
                    SELECT id FROM agent_improvements
                    WHERE agent_id = $1 AND status = 'OPEN'
                      AND lower(trim(title)) = lower(trim($2))
                    LIMIT 1
                    """,
                    row["agent_id"], row["retry_reason"],
                )
                if existing:
                    await conn.execute(
                        "UPDATE agent_improvements SET updated_at = now() WHERE id = $1",
                        existing["id"],
                    )
                    results.append({"action": "incremented", "point_id": str(existing["id"]),
                                    "agent_id": row["agent_id"], "new_frequency": row["freq"]})
                else:
                    severity = "HIGH" if row["freq"] >= 10 else "MEDIUM" if row["freq"] >= 5 else "LOW"
                    agent_name = row["agent_id"]
                    agent_role = ""
                    name_row = await conn.fetchrow(
                        "SELECT name, role FROM hired_agents WHERE agent_id = $1",
                        row["agent_id"],
                    )
                    if name_row and name_row.get("name"):
                        agent_name = name_row["name"]
                    if name_row and name_row.get("role"):
                        agent_role = name_row["role"]
                    ev = json.dumps([f"Job {row['first_job']}, {row['freq']}x gezien in {since_days} dagen"])
                    insert_sql = """
                        INSERT INTO agent_improvements (agent_id, agent_name, title, details, severity, status)
                        VALUES ($1, $2, $3, $4, $5, 'OPEN')
                        RETURNING id
                    """
                    rid = await conn.fetchrow(
                        insert_sql,
                        row["agent_id"], agent_name, row["retry_reason"], ev, severity,
                    )
                    point_id = str(rid["id"])
                    results.append({"action": "created", "point_id": point_id,
                                    "agent_id": row["agent_id"], "issue": row["retry_reason"],
                                    "frequency": row["freq"], "impact": severity})
                    await self._maybe_trigger_resource_discovery(
                        conn=conn,
                        point_id=point_id,
                        agent_id=row["agent_id"],
                        agent_role=agent_role,
                        pattern_description=row["retry_reason"],
                        impact=severity,
                    )
            return results

    async def scan_job_performance(self) -> list[str]:
        """Lage GSC-performance (job_performance) → agent_improvements; zie gsc_performance."""
        from app.services.gsc_performance import scan_job_performance as scan_gsc_performance

        return await scan_gsc_performance(self.pool)

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
                    SELECT id FROM agent_improvements
                    WHERE agent_id = $1 AND status = 'OPEN'
                      AND lower(title) LIKE '%direct chat%'
                    LIMIT 1
                    """,
                    row["agent_id"],
                )
                if not existing:
                    agent_name = row["agent_id"]
                    rrow = await conn.fetchrow("SELECT name FROM hired_agents WHERE agent_id = $1", row["agent_id"])
                    if rrow and rrow.get("name"):
                        agent_name = rrow["name"]
                    desc = "Agent antwoordt herhaaldelijk met 'ik weet het niet' in Direct Chat"
                    sample = json.dumps([(row["sample"] or "")[:200]])
                    rid = await conn.fetchrow(
                        """INSERT INTO agent_improvements (agent_id, agent_name, title, details, severity, status)
                        VALUES ($1, $2, $3, $4, 'MEDIUM', 'OPEN')
                        RETURNING id""",
                        row["agent_id"], agent_name, desc, sample,
                    )
                    point_id = str(rid["id"])
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
                open_points_rows = await conn.fetch(
                    """
                    SELECT id, title, summary, severity, status, source_url, created_at
                    FROM agent_improvements WHERE agent_id = $1 AND status = 'OPEN'
                    ORDER BY CASE severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, created_at DESC
                    """, aid,
                )
                open_points = [_agent_improvement_to_legacy(dict(r)) for r in open_points_rows]
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
            cols = await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='agent_improvements'"
            )
            col_set = {r["column_name"] for r in cols}
            sets = ["status = $1", "updated_at = now()"]
            params: list = [new_status]
            idx = 2
            if source_url and ("source_url" in col_set or "source" in col_set):
                col = "source_url" if "source_url" in col_set else "source"
                sets.append(f"{col} = ${idx}")
                params.append(source_url)
                idx += 1
            params.append(point_id)
            await conn.execute(
                f"UPDATE agent_improvements SET {', '.join(sets)} WHERE id::text = ${idx}",
                *params,
            )
            return {"point_id": point_id, "status": new_status}

    async def run_ab_validation(self, pool: asyncpg.pool.Pool) -> dict[str, int]:
        """
        A/B validatie: voor alle IN_TRAINING development points,
        vergelijk retry frequency na training met baseline.
        resolved / improving / ineffective.
        """
        resolved = improving = ineffective = 0
        async with pool.acquire() as conn:
            # Check ceo_notifications exists
            has_notifications = await conn.fetchval(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'ceo_notifications'"
            )
            points = await conn.fetch(
                """
                SELECT id, agent_id, title, COALESCE(updated_at, created_at) AS since_at
                FROM agent_improvements
                WHERE status = 'IN_TRAINING'
                """
            )
            for dp in points:
                point_id = str(dp["id"])
                agent_id = dp["agent_id"]
                issue = (dp["title"] or "").strip()
                baseline_freq = 1
                since_at = dp["since_at"]

                if not issue:
                    continue

                new_freq_row = await conn.fetchrow(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM job_steps
                    WHERE agent_id = $1
                      AND retry_reason IS NOT NULL AND retry_reason != ''
                      AND retry_reason ILIKE $2
                      AND started_at > $3
                    """,
                    agent_id,
                    f"%{issue[:200]}%",
                    since_at,
                )
                new_freq = int(new_freq_row["cnt"] or 0)

                if new_freq == 0:
                    await conn.execute(
                        "UPDATE agent_improvements SET status = 'RESOLVED', updated_at = now() WHERE id = $1 OR id::text = $1",
                        point_id,
                    )
                    resolved += 1
                    logger.info("[AB] %s: RESOLVED — geen retries na training", agent_id)
                elif new_freq < baseline_freq:
                    improving += 1
                    logger.info("[AB] %s: verbetering (%s → %s), training loopt nog", agent_id, baseline_freq, new_freq)
                else:
                    await conn.execute(
                        "UPDATE agent_improvements SET status = 'OPEN', updated_at = now() WHERE id = $1 OR id::text = $1",
                        point_id,
                    )
                    ineffective += 1
                    if has_notifications:
                        msg = f"Training voor {agent_id} heeft geen effect op: {issue[:200]}"
                        await conn.execute(
                            """
                            INSERT INTO ceo_notifications (type, message, related_id)
                            VALUES ('training_ineffective', $1, $2)
                            """,
                            msg,
                            point_id,
                        )
                    logger.info("[AB] %s: geen effect, teruggestuurd naar OPEN", agent_id)

        return {"resolved": resolved, "improving": improving, "ineffective": ineffective}

    async def detect_cross_training_opportunities(self, pool: asyncpg.pool.Pool) -> int:
        """
        Zoekt lessons die relevant zijn voor meerdere agents.
        Maakt cross_training_proposals aan. Return: aantal nieuwe voorstellen.
        """
        async with pool.acquire() as conn:
            has_lessons = await conn.fetchval(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'lessons'"
            )
            has_proposals = await conn.fetchval(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'cross_training_proposals'"
            )
            if not has_lessons or not has_proposals:
                return 0

            lessons = await conn.fetch(
                """
                SELECT lesson_id, title, fix, agent_id
                FROM lessons
                WHERE status = 'active' AND confidence_score >= 0.70
                """
            )
            agents = await conn.fetch(
                "SELECT agent_id, role, goal FROM hired_agents WHERE is_active = true"
            )
            agent_by_id = {a["agent_id"]: dict(a) for a in agents}
            # Build simple keyword set per agent from role + goal
            def keywords(a: dict) -> set:
                r = (a.get("role") or "").lower()
                g = (a.get("goal") or "").lower()
                return set((r + " " + g).split())

            created = 0
            for lesson in lessons:
                lesson_id = lesson["lesson_id"]
                source_agent_id = lesson["agent_id"]
                title = (lesson["title"] or "") + " " + (lesson["fix"] or "")
                title_lower = title.lower()
                words = set(title_lower.split())

                targets = []
                for aid, a in agent_by_id.items():
                    if aid == source_agent_id:
                        continue
                    kw = keywords(a)
                    if not kw:
                        continue
                    if words & kw:
                        targets.append(aid)

                if len(targets) < 2:
                    continue
                targets = sorted(targets)

                # Dedupe: same lesson + same target set
                existing = await conn.fetchrow(
                    """
                    SELECT 1 FROM cross_training_proposals
                    WHERE lesson_id = $1 AND status = 'pending' AND target_agent_ids = $2::jsonb
                    """,
                    lesson_id,
                    _json_array(targets),
                )
                if existing:
                    continue

                await conn.execute(
                    """
                    INSERT INTO cross_training_proposals
                    (lesson_id, source_agent_id, target_agent_ids, reason, status)
                    VALUES ($1, $2, $3::jsonb, $4, 'pending')
                    """,
                    lesson_id,
                    source_agent_id,
                    _json_array(targets),
                    f"Lesson relevant voor {len(targets)} andere agents",
                )
                created += 1
            return created


def _serialize(rows) -> list[dict]:
    result = []
    for row in rows:
        d = dict(row)
        for k, v in d.items():
            if isinstance(v, datetime): d[k] = v.isoformat()
        result.append(d)
    return result
