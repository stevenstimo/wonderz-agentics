"""Stale Detection Service — marks documents stale based on review interval or source changes.

Trigger A: review_interval_days exceeded (all doc_types except skill_spec)
Trigger B: related_docs updated after skill_spec.last_reviewed
"""

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

REVIEW_INTERVAL_DEFAULTS: dict[str, int] = {
    "policy": 90,
    "playbook": 180,
    "sop": 180,
    "template": 365,
    "framework": 180,
    "case_study": 365,
    "research": 365,
    "client_context": 180,
}


class StaleDetectionService:

    async def run(self, pool) -> dict[str, Any]:
        interval_result = await self.check_review_intervals(pool)
        skill_result = await self.check_skill_specs(pool)

        marked = interval_result["marked"] + skill_result["marked"]
        already = interval_result["already_stale"] + skill_result["already_stale"]

        logger.info(
            "Stale detection completed: marked_stale=%d, already_stale=%d",
            marked,
            already,
        )
        return {"marked_stale": marked, "already_stale": already}

    async def check_review_intervals(self, pool) -> dict[str, int]:
        """Trigger A: mark approved docs as stale when review interval exceeded."""
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                UPDATE knowledge_documents
                SET status = 'stale', updated_at = now()
                WHERE status = 'approved'
                  AND doc_type != 'skill_spec'
                  AND last_reviewed IS NOT NULL
                  AND (last_reviewed + INTERVAL '1 day' * COALESCE(review_interval_days, 180)) < now()
                RETURNING document_id, title, doc_type, review_interval_days, last_reviewed
                """
            )

            already_stale = await conn.fetchval(
                """
                SELECT COUNT(*) FROM knowledge_documents
                WHERE status = 'stale' AND doc_type != 'skill_spec'
                """
            )

        for r in rows:
            logger.info(
                "[STALE] %s (%s) — reden: review interval verstreken (%d dagen)",
                r["title"],
                r["document_id"],
                r["review_interval_days"] or 180,
            )

        return {"marked": len(rows), "already_stale": (already_stale or 0) - len(rows)}

    async def check_skill_specs(self, pool) -> dict[str, int]:
        """Trigger B: mark skill_spec as stale when a related_doc was updated after last_reviewed."""
        marked = 0
        async with pool.acquire() as conn:
            specs = await conn.fetch(
                """
                SELECT document_id, title, related_docs, last_reviewed
                FROM knowledge_documents
                WHERE status = 'approved'
                  AND doc_type = 'skill_spec'
                  AND related_docs IS NOT NULL
                  AND array_length(related_docs, 1) > 0
                """
            )

            already_stale = await conn.fetchval(
                "SELECT COUNT(*) FROM knowledge_documents WHERE status = 'stale' AND doc_type = 'skill_spec'"
            )

            for spec in specs:
                last_rev = spec["last_reviewed"]
                if not last_rev:
                    continue

                related_ids = spec["related_docs"] or []
                if not related_ids:
                    continue

                changed = await conn.fetch(
                    """
                    SELECT document_id, title, updated_at
                    FROM knowledge_documents
                    WHERE document_id = ANY($1::uuid[])
                      AND updated_at > $2
                    """,
                    related_ids,
                    last_rev,
                )

                if changed:
                    await conn.execute(
                        "UPDATE knowledge_documents SET status = 'stale', updated_at = now() WHERE document_id = $1",
                        spec["document_id"],
                    )
                    trigger_titles = ", ".join(r["title"] or str(r["document_id"]) for r in changed)
                    logger.info(
                        "[STALE] %s (%s) — reden: brondocument gewijzigd (%s)",
                        spec["title"],
                        spec["document_id"],
                        trigger_titles,
                    )
                    marked += 1

        return {"marked": marked, "already_stale": already_stale or 0}
