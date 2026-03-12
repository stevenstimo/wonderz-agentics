"""
Platform Spec V5 — Knowledge Graph. Herbruikbare kennis met traceability.
Sectie 8.2, 13. Geen Neo4j; graph_edges in Postgres.
"""
import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Edge types (platform spec sectie 8.2)
EDGE_TYPES = {
    "AGENT_EXECUTED": "Agent EXECUTED Task",
    "TASK_CITED": "Task CITED Artifact",
    "TASK_PRODUCED": "Task PRODUCED Fix",
    "FIX_CHANGED": "Fix CHANGED Artifact",
    "LESSON_DERIVED_FROM": "Lesson DERIVED_FROM Task",
    "LESSON_INTRODUCES": "Lesson INTRODUCES Pattern",
    "LESSON_REFERENCES": "Lesson REFERENCES Artifact",
    "PATTERN_APPLIES_TO": "Pattern APPLIES_TO Domain",
    "SAME_AS": "SAME_AS (complementary)",
    "FINDING_SUPPORTED_BY": "Finding SUPPORTED_BY Artifact",
    "CAUSE_SUPPORTED_BY": "Cause SUPPORTED_BY Artifact",
}

STOP_WORDS = {
    "de", "het", "een", "is", "dat", "van", "in",
    "en", "te", "op", "aan", "met", "voor", "er",
}

PATTERN_SUFFIXES = ("hook", "pattern", "service", "component", "module", "adapter", "guard")


class KnowledgeGraph:
    """Knowledge Graph service: edges, pattern trace, detect_same_as, register_pattern."""

    async def add_edge(
        self,
        pool,
        from_id: str,
        to_id: str,
        edge_type: str,
        attrs: dict | None = None,
    ) -> Optional[str]:
        """
        Voegt een edge toe aan graph_edges.
        Deduplicatie: zelfde from_id + to_id + edge_type → update attrs, return bestaande edge_id.
        Defensief: try/except, log warning, return None bij fout.
        """
        try:
            attrs = attrs or {}
            attrs_json = json.dumps(attrs, default=lambda o: getattr(o, "isoformat", lambda: str(o))())
            async with pool.acquire() as conn:
                existing = await conn.fetchrow(
                    """
                    SELECT edge_id FROM graph_edges
                    WHERE from_id = $1 AND to_id = $2 AND edge_type = $3
                    """,
                    from_id,
                    to_id,
                    edge_type,
                )
                if existing:
                    await conn.execute(
                        """
                        UPDATE graph_edges SET attrs = $1::jsonb
                        WHERE from_id = $2 AND to_id = $3 AND edge_type = $4
                        """,
                        attrs_json,
                        from_id,
                        to_id,
                        edge_type,
                    )
                    return str(existing["edge_id"])
                row = await conn.fetchrow(
                    """
                    INSERT INTO graph_edges (from_id, to_id, edge_type, attrs)
                    VALUES ($1, $2, $3, $4::jsonb)
                    RETURNING edge_id
                    """,
                    from_id,
                    to_id,
                    edge_type,
                    attrs_json,
                )
                return str(row["edge_id"]) if row and row.get("edge_id") else None
        except Exception as e:
            logger.warning("KnowledgeGraph add_edge failed: %s", e)
            return None

    async def get_edges_from(
        self,
        pool,
        from_id: str,
        edge_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Geeft alle edges terug vanuit een node, optioneel gefilterd op edge_type."""
        try:
            async with pool.acquire() as conn:
                if edge_type:
                    rows = await conn.fetch(
                        """
                        SELECT edge_id, from_id, to_id, edge_type, attrs, created_at
                        FROM graph_edges WHERE from_id = $1 AND edge_type = $2
                        ORDER BY created_at ASC
                        """,
                        from_id,
                        edge_type,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT edge_id, from_id, to_id, edge_type, attrs, created_at
                        FROM graph_edges WHERE from_id = $1
                        ORDER BY created_at ASC
                        """,
                        from_id,
                    )
                return [_edge_row_to_dict(r) for r in rows]
        except Exception as e:
            logger.warning("KnowledgeGraph get_edges_from failed: %s", e)
            return []

    async def get_edges_to(
        self,
        pool,
        to_id: str,
        edge_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Geeft alle edges terug naar een node."""
        try:
            async with pool.acquire() as conn:
                if edge_type:
                    rows = await conn.fetch(
                        """
                        SELECT edge_id, from_id, to_id, edge_type, attrs, created_at
                        FROM graph_edges WHERE to_id = $1 AND edge_type = $2
                        ORDER BY created_at ASC
                        """,
                        to_id,
                        edge_type,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT edge_id, from_id, to_id, edge_type, attrs, created_at
                        FROM graph_edges WHERE to_id = $1
                        ORDER BY created_at ASC
                        """,
                        to_id,
                    )
                return [_edge_row_to_dict(r) for r in rows]
        except Exception as e:
            logger.warning("KnowledgeGraph get_edges_to failed: %s", e)
            return []

    async def get_pattern_trace(
        self,
        pool,
        pattern_id: str,
    ) -> list[dict[str, Any]]:
        """
        Pattern traceability (platform spec sectie 20.2).
        Welke lessons introduceren dit pattern, via welke tasks, door welke agents?
        """
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                      p.pattern_id,
                      p.name AS pattern_name,
                      l.lesson_id,
                      l.confidence_score,
                      l.agent_id,
                      ge_task.to_id AS task_id,
                      ge_agent.from_id AS agent_id_executed
                    FROM patterns p
                    JOIN graph_edges ge_intro
                      ON ge_intro.to_id = p.pattern_id
                      AND ge_intro.edge_type = 'LESSON_INTRODUCES'
                    JOIN lessons l
                      ON l.lesson_id = ge_intro.from_id
                    LEFT JOIN graph_edges ge_task
                      ON ge_task.from_id = l.lesson_id
                      AND ge_task.edge_type = 'LESSON_DERIVED_FROM'
                    LEFT JOIN graph_edges ge_agent
                      ON ge_agent.to_id = ge_task.to_id
                      AND ge_agent.edge_type = 'AGENT_EXECUTED'
                    WHERE p.pattern_id = $1
                    ORDER BY l.confidence_score DESC
                    """,
                    pattern_id,
                )
                return [
                    {
                        "lesson_id": r["lesson_id"],
                        "confidence_score": float(r["confidence_score"]) if r.get("confidence_score") is not None else 0.0,
                        "agent_id": r["agent_id"],
                        "task_id": r["task_id"],
                        "agent_id_executed": r["agent_id_executed"],
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.warning("KnowledgeGraph get_pattern_trace failed: %s", e)
            return []

    def _tokenize(self, text: str) -> set[str]:
        if not text:
            return set()
        words = set(re.findall(r"\b\w{2,}\b", text.lower()))
        return words - STOP_WORDS

    async def detect_same_as(
        self,
        pool,
        lesson_id: str,
    ) -> list[str]:
        """
        Na goedkeuring: check complementaire lessons (zelfde agent, 3+ overlappende titel-woorden).
        Geen bestaand conflict in lesson_conflicts. Maak SAME_AS edge aan.
        Return: lijst van lesson_ids waarmee SAME_AS edge aangemaakt is.
        """
        result: list[str] = []
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT agent_id, title, gevonden FROM lessons WHERE lesson_id = $1",
                    lesson_id,
                )
                if not row:
                    return result
                agent_id = row["agent_id"]
                title = (row["title"] or "") or ""
                title_words = self._tokenize(title)

                status_col = "lesson_status"
                try:
                    has_ls = await conn.fetchval(
                        "SELECT 1 FROM information_schema.columns WHERE table_name = 'lessons' AND column_name = 'lesson_status'"
                    )
                    if not has_ls:
                        status_col = "status"
                except Exception:
                    status_col = "status"

                others = await conn.fetch(
                    f"""
                    SELECT lesson_id, title FROM lessons
                    WHERE agent_id = $1 AND lesson_id != $2
                      AND (COALESCE(lesson_status, status) = 'active')
                    """,
                    agent_id,
                    lesson_id,
                )
                for r in others:
                    other_id = r["lesson_id"]
                    other_title = (r["title"] or "") or ""
                    other_words = self._tokenize(other_title)
                    if len(title_words & other_words) < 3:
                        continue
                    conflict_exists = await conn.fetchval(
                        """
                        SELECT 1 FROM lesson_conflicts
                        WHERE (lesson_a = $1 AND lesson_b = $2)
                           OR (lesson_a = $2 AND lesson_b = $1)
                        """,
                        lesson_id,
                        other_id,
                    )
                    if conflict_exists:
                        continue
                    edge_id = await self.add_edge(
                        pool, lesson_id, other_id, "SAME_AS", {}
                    )
                    if edge_id:
                        result.append(other_id)
        except Exception as e:
            logger.warning("KnowledgeGraph detect_same_as failed: %s", e)
        return result

    async def register_pattern(
        self,
        pool,
        lesson_id: str,
        pattern_name: str,
        pattern_type: str = "pattern",
        description: str | None = None,
        tags: list[str] | None = None,
        applies_to_domain: str | None = None,
    ) -> str:
        """
        Registreert een nieuw pattern: pattern_id = pattern:{name_lower_underscore}.
        Upsert patterns, add LESSON_INTRODUCES + optioneel PATTERN_APPLIES_TO, emit PATTERN_REGISTERED.
        Return: pattern_id.
        """
        pattern_id = "pattern:" + pattern_name.lower().replace(" ", "_")
        tags = tags or []
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO patterns (pattern_id, name, pattern_type, description, tags)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (pattern_id) DO UPDATE SET
                      name = EXCLUDED.name,
                      pattern_type = EXCLUDED.pattern_type,
                      description = COALESCE(EXCLUDED.description, patterns.description),
                      tags = COALESCE(EXCLUDED.tags, patterns.tags)
                    """,
                    pattern_id,
                    pattern_name,
                    pattern_type,
                    description,
                    tags,
                )
            await self.add_edge(
                pool, lesson_id, pattern_id, "LESSON_INTRODUCES", {}
            )
            if applies_to_domain:
                await self.add_edge(
                    pool, pattern_id, applies_to_domain, "PATTERN_APPLIES_TO", {}
                )
            try:
                from app.services.event_emitter import EventEmitter, EventType
                emitter = EventEmitter()
                await emitter.emit(
                    pool,
                    EventType.PATTERN_REGISTERED,
                    lesson_id=lesson_id,
                    payload={"pattern_id": pattern_id, "pattern_name": pattern_name},
                )
            except Exception:
                pass
            return pattern_id
        except Exception as e:
            logger.warning("KnowledgeGraph register_pattern failed: %s", e)
            return pattern_id  # still return id on partial failure


def _edge_row_to_dict(r) -> dict[str, Any]:
    created = r.get("created_at")
    return {
        "edge_id": str(r["edge_id"]) if r.get("edge_id") else None,
        "from_id": r.get("from_id"),
        "to_id": r.get("to_id"),
        "edge_type": r.get("edge_type"),
        "attrs": dict(r["attrs"]) if r.get("attrs") is not None else {},
        "created_at": created.isoformat() if created else None,
    }
