"""
Platform Spec V3 — Lessons lifecycle: propose, approve, contradictions, decay, usage.
Sectie 14.1.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

STOP_WORDS = {
    "de", "het", "een", "is", "dat", "van", "in",
    "en", "te", "op", "aan", "met", "voor", "er",
}


def _role_prefix(agent_id: str) -> str:
    if not agent_id or not isinstance(agent_id, str):
        return "GE"
    aid = agent_id.lower()
    if "frontend" in aid or "fe" in aid:
        return "FE"
    if "backend" in aid or "be" in aid:
        return "BE"
    if "copywriter" in aid or "copy" in aid:
        return "CP"
    if "seo" in aid:
        return "SE"
    return "GE"


def _next_lesson_id_prefix(role: str) -> str:
    now = datetime.now(timezone.utc)
    return f"{role}-{now.year}-{now.month:02d}"


def _extract_pattern_name(fix_text: str) -> Optional[str]:
    """
    Eenvoudige heuristiek: als fix_text een zin bevat die eindigt op
    'hook', 'pattern', 'service', 'component', 'module', 'adapter', of 'guard':
    return de eerste 5 woorden van die zin. Anders: return None.
    """
    if not fix_text or len(fix_text) < 10:
        return None
    suffixes = ("hook", "pattern", "service", "component", "module", "adapter", "guard")
    for sentence in re.split(r"[.!?\n]+", fix_text):
        sentence = sentence.strip()
        if not sentence:
            continue
        words = re.findall(r"\b\w+\b", sentence)
        for w in words:
            wl = w.lower()
            if any(wl == s or wl.endswith(s) for s in suffixes):
                return " ".join(words[:5]) if words else None
    return None


def _agent_domain(agent_id: str) -> str:
    """Afgeleid domein uit agent_id voor PATTERN_APPLIES_TO."""
    if not agent_id or not isinstance(agent_id, str):
        return "generic"
    aid = agent_id.lower()
    if "frontend" in aid or "fe" in aid:
        return "frontend"
    if "backend" in aid or "be" in aid:
        return "backend"
    if "copywriter" in aid or "copy" in aid:
        return "copy"
    if "seo" in aid:
        return "seo"
    return "generic"


class LessonsLifecycle:
    async def propose(
        self,
        pool,
        worker_output: dict,
        task_id: str,
        agent_id: str,
    ) -> str:
        """
        Maakt een nieuwe lesson aan met status 'pending'.
        lesson_id formaat: {ROLE}-{YYYY}-{MM}-{###}
        Roep daarna check_contradictions() aan.
        Return: lesson_id (str). Conflicts are logged; use check_contradictions(pool, lesson_id) for list.
        """
        role = _role_prefix(agent_id)
        prefix = _next_lesson_id_prefix(role)
        title = (worker_output.get("gevonden") or "")[:80]
        gevonden = worker_output.get("gevonden") or ""
        oorzaak = worker_output.get("oorzaak") or ""
        fix = worker_output.get("fix_voorstel") or ""
        impact = worker_output.get("volgende_actie") or ""

        async with pool.acquire() as conn:
            # Next sequence for this prefix
            last = await conn.fetchval(
                """
                SELECT lesson_id FROM lessons
                WHERE lesson_id LIKE $1 || '-%'
                ORDER BY lesson_id DESC LIMIT 1
                """,
                prefix,
            )
            num = 1
            if last:
                m = re.search(r"-(\d+)$", last)
                if m:
                    num = int(m.group(1)) + 1
            lesson_id = f"{prefix}-{num:03d}"

            # Insert: use status and optionally lesson_status
            await conn.execute(
                """
                INSERT INTO lessons (
                    lesson_id, agent_id, task_id, title, gevonden, oorzaak, fix, impact,
                    status, confidence_score, usage_count
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending', 0.0, 0)
                ON CONFLICT (lesson_id) DO NOTHING
                """,
                lesson_id,
                agent_id,
                task_id,
                title,
                gevonden,
                oorzaak,
                fix,
                impact,
            )
            # Set lesson_status if column exists (migration 058)
            try:
                await conn.execute(
                    "UPDATE lessons SET lesson_status = 'pending' WHERE lesson_id = $1",
                    lesson_id,
                )
            except Exception:
                pass

        conflicts = await self.check_contradictions(pool, lesson_id)
        if conflicts:
            logger.info("Lesson %s: %s contradiction(s) detected", lesson_id, len(conflicts))
        # V4: Event model — LESSON_PROPOSED (fire-and-forget)
        try:
            from app.services.event_emitter import EventEmitter, EventType
            emitter = EventEmitter()
            await emitter.emit(
                pool,
                EventType.LESSON_PROPOSED,
                agent_id=agent_id,
                lesson_id=lesson_id,
                payload={"title": title},
            )
        except Exception:
            pass
        return lesson_id  # callers can call check_contradictions again if they need conflicts

    async def approve(
        self,
        pool,
        lesson_id: str,
        confidence_score: float,
        talent_agent_id: str,
        confidence_breakdown: dict,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        worker_output: Optional[dict] = None,
    ) -> dict[str, Any]:
        """
        Verwerkt goedkeuring van een lesson.
        confidence_score >= 0.70 → active; anders → rejected (audittrail behouden).
        Optioneel task_id, agent_id, worker_output voor V5 Knowledge Graph integratie.
        """
        async with pool.acquire() as conn:
            if confidence_score >= 0.70:
                await conn.execute(
                    """
                    UPDATE lessons SET
                        status = 'active',
                        confidence_score = $1,
                        last_confirmed_at = now()
                    WHERE lesson_id = $2
                    """,
                    round(confidence_score, 2),
                    lesson_id,
                )
                try:
                    await conn.execute(
                        "UPDATE lessons SET lesson_status = 'active' WHERE lesson_id = $1",
                        lesson_id,
                    )
                except Exception:
                    pass
                # V4: Event model — LESSON_APPROVED (fire-and-forget)
                try:
                    from app.services.event_emitter import EventEmitter, EventType
                    emitter = EventEmitter()
                    await emitter.emit(
                        pool,
                        EventType.LESSON_APPROVED,
                        agent_id=talent_agent_id,
                        lesson_id=lesson_id,
                        confidence_score=confidence_score,
                        payload={"lesson_status": "active"},
                    )
                except Exception:
                    pass
                # V5: Knowledge Graph — edges + detect_same_as + optional pattern
                if task_id and agent_id:
                    try:
                        from app.services.knowledge_graph import KnowledgeGraph
                        graph = KnowledgeGraph()
                        await graph.add_edge(
                            pool,
                            from_id=lesson_id,
                            to_id=task_id,
                            edge_type="LESSON_DERIVED_FROM",
                        )
                        await graph.add_edge(
                            pool,
                            from_id=agent_id,
                            to_id=task_id,
                            edge_type="AGENT_EXECUTED",
                        )
                        await graph.detect_same_as(pool, lesson_id)
                        worker_output = worker_output or {}
                        fix_text = worker_output.get("fix_voorstel") or ""
                        if len(fix_text) > 10:
                            pattern_name = _extract_pattern_name(fix_text)
                            if pattern_name:
                                await graph.register_pattern(
                                    pool,
                                    lesson_id=lesson_id,
                                    pattern_name=pattern_name,
                                    applies_to_domain=_agent_domain(agent_id),
                                )
                    except Exception as _kg_err:
                        logger.warning("Knowledge Graph integration failed: %s", _kg_err)
                return {
                    "approved": True,
                    "lesson_id": lesson_id,
                    "lesson_status": "active",
                }
            else:
                await conn.execute(
                    "UPDATE lessons SET status = 'rejected' WHERE lesson_id = $1",
                    lesson_id,
                )
                try:
                    await conn.execute(
                        "UPDATE lessons SET lesson_status = 'rejected' WHERE lesson_id = $1",
                        lesson_id,
                    )
                except Exception:
                    pass
                # V4: Event model — LESSON_REJECTED (fire-and-forget)
                try:
                    from app.services.event_emitter import EventEmitter, EventType
                    emitter = EventEmitter()
                    await emitter.emit(
                        pool,
                        EventType.LESSON_REJECTED,
                        agent_id=talent_agent_id,
                        lesson_id=lesson_id,
                        confidence_score=confidence_score,
                        payload={"reason": "confidence_score < 0.70"},
                    )
                except Exception:
                    pass
                return {
                    "approved": False,
                    "lesson_id": lesson_id,
                    "lesson_status": "rejected",
                    "reason": "confidence_score < 0.70",
                }

    def _tokenize(self, text: str) -> set[str]:
        if not text:
            return set()
        words = set(re.findall(r"\b\w{2,}\b", text.lower()))
        return words - STOP_WORDS

    async def check_contradictions(
        self,
        pool,
        new_lesson_id: str,
    ) -> list[dict[str, Any]]:
        """
        Zoekt bestaande active lessons die conflicteren met de nieuwe lesson.
        Conflict: 3+ overlappende woorden in title, OF 2+ kernwoorden in gevonden.
        """
        result: list[dict[str, Any]] = []
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT title, gevonden, agent_id FROM lessons WHERE lesson_id = $1",
                new_lesson_id,
            )
            if not row:
                return result
            new_title = (row["title"] or "") or ""
            new_gevonden = (row["gevonden"] or "") or ""
            agent_id = row["agent_id"]
            new_title_words = self._tokenize(new_title)
            new_gevonden_words = self._tokenize(new_gevonden)

            # Active lessons same agent (same domain)
            status_col = "lesson_status"
            try:
                await conn.fetchval(
                    "SELECT 1 FROM information_schema.columns WHERE table_name = 'lessons' AND column_name = 'lesson_status'"
                )
            except Exception:
                status_col = "status"

            rows = await conn.fetch(
                f"""
                SELECT lesson_id, title, gevonden FROM lessons
                WHERE agent_id = $1 AND lesson_id != $2
                  AND (COALESCE(lesson_status, status) = 'active')
                """,
                agent_id,
                new_lesson_id,
            )
            for r in rows:
                existing_title = (r["title"] or "") or ""
                existing_gevonden = (r["gevonden"] or "") or ""
                exist_title_words = self._tokenize(existing_title)
                exist_gevonden_words = self._tokenize(existing_gevonden)
                title_overlap = len(new_title_words & exist_title_words) >= 3
                gevonden_overlap = len(new_gevonden_words & exist_gevonden_words) >= 2
                if title_overlap or gevonden_overlap:
                    overlap_score = (
                        len(new_title_words & exist_title_words) / max(1, len(new_title_words))
                        if new_title_words else 0
                    )
                    conflict_id = await conn.fetchval(
                        """
                        INSERT INTO lesson_conflicts (lesson_a, lesson_b)
                        VALUES ($1, $2)
                        RETURNING conflict_id
                        """,
                        r["lesson_id"],
                        new_lesson_id,
                    )
                    result.append({
                        "conflict_id": conflict_id,
                        "existing_lesson_id": r["lesson_id"],
                        "existing_title": existing_title[:80],
                        "overlap_score": round(overlap_score, 2),
                    })
        return result

    async def decay_check(self, pool) -> dict[str, int]:
        """
        Lesson decay (platform spec 14.1).
        active, usage_count >= 5, last_confirmed_at < 30 days → confidence - 0.05; if < 0.70 → stale.
        """
        decayed = 0
        stale = 0
        async with pool.acquire() as conn:
            status_col = "lesson_status"
            try:
                has_ls = await conn.fetchval(
                    "SELECT 1 FROM information_schema.columns WHERE table_name = 'lessons' AND column_name = 'lesson_status'"
                )
                if not has_ls:
                    status_col = "status"
            except Exception:
                status_col = "status"

            candidates = await conn.fetch(
                f"""
                SELECT lesson_id, confidence_score FROM lessons
                WHERE (COALESCE(lesson_status, status)) = 'active'
                  AND COALESCE(usage_count, 0) >= 5
                  AND (last_confirmed_at IS NULL OR last_confirmed_at < now() - INTERVAL '30 days')
                """
            )
            for row in candidates:
                lid = row["lesson_id"]
                old_score = float(row["confidence_score"] or 0)
                new_score = max(0.0, round(old_score - 0.05, 2))
                await conn.execute(
                    """
                    UPDATE lessons SET confidence_score = $1
                    WHERE lesson_id = $2
                    """,
                    new_score,
                    lid,
                )
                decayed += 1
                logger.info("[DECAY] %s: %s → %s", lid, old_score, new_score)
                if new_score < 0.70:
                    await conn.execute(
                        f"UPDATE lessons SET {status_col} = 'stale', status = 'stale' WHERE lesson_id = $1",
                        lid,
                    )
                    stale += 1
        return {"decayed": decayed, "stale": stale}

    async def increment_usage(self, pool, lesson_id: str) -> None:
        """Roep aan elke keer dat een lesson wordt opgehaald door retrieve_for_agent()."""
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE lessons SET usage_count = COALESCE(usage_count, 0) + 1 WHERE lesson_id = $1",
                lesson_id,
            )
