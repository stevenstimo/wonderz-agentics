"""
Platform Spec V7 — Governance Monitoring.
Rubber-stamp detectie, agent suspension, breach logging.
"""
import logging
from typing import Any

from app.services.event_emitter import EventEmitter, EventType

logger = logging.getLogger("uvicorn.error")


class GovernanceMonitor:
    APPROVAL_RATE_THRESHOLD = 0.85
    EVIDENCE_RATE_THRESHOLD = 0.70
    MIN_REVIEWS_FOR_CHECK = 5

    async def check_talent_integrity(self, pool) -> dict[str, int]:
        """
        Hoofdfunctie. Leest talent_governance_metrics view.
        Per rij met breach: log, suspend, block tasks, insert breach, emit event.
        Return: breaches_found, agents_suspended, tasks_blocked.
        """
        breaches_found = 0
        agents_suspended = 0
        tasks_blocked = 0
        emitter = EventEmitter()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT talent_agent_id, approval_rate, evidence_verification_rate,
                       monitoring_status, total_reviews
                FROM talent_governance_metrics
                WHERE total_reviews >= $1
                """,
                self.MIN_REVIEWS_FOR_CHECK,
            )

            for row in rows:
                talent_agent_id = row["talent_agent_id"]
                approval_rate = float(row["approval_rate"] or 0)
                evidence_verification_rate = float(row["evidence_verification_rate"] or 0)
                monitoring_status = row["monitoring_status"] or "NORMAL"
                domain: str | None = None

                breach_type: str | None = None
                if monitoring_status == "HIGH_RISK_RUBBER_STAMP":
                    breach_type = "HIGH_RISK_RUBBER_STAMP"
                if evidence_verification_rate < self.EVIDENCE_RATE_THRESHOLD:
                    breach_type = "LOW_EVIDENCE_VERIFICATION"

                if not breach_type:
                    continue

                breaches_found += 1
                domain = await self._get_agent_domain(pool, talent_agent_id)

                logger.critical(
                    "GOVERNANCE BREACH: %s | domain=%s | approval_rate=%.2f | evidence_verification_rate=%.2f",
                    talent_agent_id,
                    domain or "",
                    approval_rate,
                    evidence_verification_rate,
                )

                suspended = await self._suspend_agent(
                    pool, talent_agent_id,
                    reason=f"{breach_type} approval={approval_rate:.2f} evidence={evidence_verification_rate:.2f}",
                )
                if suspended:
                    agents_suspended += 1

                blocked = await self._block_domain_tasks(pool, domain or talent_agent_id or "")
                tasks_blocked += blocked

                action_taken = "suspended" if suspended else "notified"
                await conn.execute(
                    """
                    INSERT INTO governance_breaches (
                        talent_agent_id, domain, approval_rate,
                        evidence_verification_rate, breach_type, action_taken
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    talent_agent_id,
                    domain,
                    approval_rate,
                    evidence_verification_rate,
                    breach_type,
                    action_taken,
                )

                await emitter.emit(
                    pool,
                    EventType.GOVERNANCE_BREACH_DETECTED,
                    agent_id=talent_agent_id,
                    payload={
                        "breach_type": breach_type,
                        "approval_rate": approval_rate,
                        "evidence_verification_rate": evidence_verification_rate,
                        "action_taken": action_taken,
                    },
                )

        return {
            "breaches_found": breaches_found,
            "agents_suspended": agents_suspended,
            "tasks_blocked": tasks_blocked,
        }

    async def _get_agent_domain(self, pool, agent_id: str) -> str | None:
        """Resolve domain (specialization) for agent from agents or hired_agents."""
        async with pool.acquire() as conn:
            for table in ("agents", "hired_agents"):
                try:
                    row = await conn.fetchrow(
                        "SELECT specialization FROM " + table + " WHERE agent_id = $1",
                        agent_id,
                    )
                    if row and row.get("specialization"):
                        return str(row["specialization"])
                except Exception:
                    continue
        return None

    async def _suspend_agent(
        self,
        pool,
        agent_id: str,
        reason: str,
    ) -> bool:
        """
        Zet is_suspended=true. Probeert tabel 'agents' eerst, dan 'hired_agents'.
        Return True als agent gesuspendeerd, False als al gesuspendeerd of niet gevonden.
        """
        async with pool.acquire() as conn:
            for table in ("agents", "hired_agents"):
                try:
                    result = await conn.execute(
                        """
                        UPDATE """ + table + """ SET
                          is_suspended = true,
                          suspended_at = now(),
                          suspension_reason = $1
                        WHERE agent_id = $2
                          AND (is_suspended = false OR is_suspended IS NULL)
                        """,
                        reason,
                        agent_id,
                    )
                    if result and "UPDATE 1" in result:
                        return True
                except Exception as e:
                    logger.debug("GovernanceMonitor: %s update failed for %s: %s", table, agent_id, e)
                    continue
        return False

    async def _block_domain_tasks(self, pool, domain: str) -> int:
        """
        Blokkeer alle open tasks van agents in dit domein.
        Gebruikt agents of hired_agents.specialization ILIKE domain.
        Return: aantal geblokkeerde tasks. 0 als tasks tabel ontbreekt.
        """
        if not domain:
            return 0
        async with pool.acquire() as conn:
            try:
                exists = await conn.fetchval(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'tasks'
                    """
                )
                if not exists:
                    return 0
            except Exception:
                return 0
            try:
                for agent_table in ("agents", "hired_agents"):
                    try:
                        result = await conn.execute(
                            """
                            UPDATE tasks SET status = 'blocked'
                            WHERE status = 'open'
                              AND agent_id IN (
                                SELECT agent_id FROM """ + agent_table + """
                                WHERE specialization ILIKE $1
                              )
                            """,
                            "%" + domain + "%",
                        )
                        if result and result.startswith("UPDATE "):
                            parts = result.split()
                            if len(parts) == 2 and parts[1].isdigit():
                                return int(parts[1])
                            return 0
                        return 0
                    except Exception:
                        continue
            except Exception as e:
                logger.warning("_block_domain_tasks failed: %s", e)
        return 0

    async def release_suspension(
        self,
        pool,
        agent_id: str,
        approved_by: str,
    ) -> bool:
        """
        Handmatige vrijgave. Vereist approved_by.
        Probeert agents dan hired_agents.
        """
        async with pool.acquire() as conn:
            for table in ("agents", "hired_agents"):
                try:
                    has_reason = await conn.fetchval(
                        "SELECT suspension_reason FROM " + table + " WHERE agent_id = $1 AND is_suspended = true",
                        agent_id,
                    )
                    if has_reason is None:
                        continue
                    suffix = f" | released_by={approved_by}"
                    new_reason = (has_reason or "") + suffix
                    result = await conn.execute(
                        """
                        UPDATE """ + table + """ SET
                          is_suspended = false,
                          suspension_reason = $1
                        WHERE agent_id = $2
                          AND is_suspended = true
                        """,
                        new_reason,
                        agent_id,
                    )
                    if result and "UPDATE 1" in result:
                        return True
                except Exception as e:
                    logger.debug("release_suspension %s failed: %s", table, e)
                    continue
        return False

    async def get_suspended_agents(self, pool) -> list[dict[str, Any]]:
        """Lijst van gesuspendeerde agents (agents + hired_agents, deduplicated by agent_id)."""
        async with pool.acquire() as conn:
            out: list[dict[str, Any]] = []
            seen: set[str] = set()
            for table in ("agents", "hired_agents"):
                try:
                    rows = await conn.fetch(
                        """
                        SELECT agent_id, specialization, suspended_at, suspension_reason
                        FROM """ + table + """
                        WHERE is_suspended = true
                        ORDER BY suspended_at DESC
                        """
                    )
                    for r in rows:
                        aid = r.get("agent_id")
                        if aid and aid not in seen:
                            seen.add(aid)
                            out.append({
                                "agent_id": aid,
                                "specialization": r.get("specialization"),
                                "suspended_at": r["suspended_at"].isoformat() if r.get("suspended_at") else None,
                                "suspension_reason": str(r["suspension_reason"]) if r.get("suspension_reason") is not None else None,
                            })
                except Exception:
                    continue
            return out

    async def get_breach_history(
        self,
        pool,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Recente governance_breaches."""
        async with pool.acquire() as conn:
            try:
                rows = await conn.fetch(
                    """
                    SELECT breach_id, talent_agent_id, domain, approval_rate,
                           evidence_verification_rate, breach_type, action_taken, created_at
                    FROM governance_breaches
                    ORDER BY created_at DESC
                    LIMIT $1
                    """,
                    limit,
                )
            except Exception:
                return []
            return [
                {
                    "breach_id": str(r["breach_id"]),
                    "talent_agent_id": r.get("talent_agent_id"),
                    "domain": r.get("domain"),
                    "approval_rate": float(r["approval_rate"]) if r.get("approval_rate") is not None else None,
                    "evidence_verification_rate": float(r["evidence_verification_rate"]) if r.get("evidence_verification_rate") is not None else None,
                    "breach_type": r.get("breach_type"),
                    "action_taken": r.get("action_taken"),
                    "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
                }
                for r in rows
            ]
