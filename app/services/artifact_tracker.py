"""
Platform Spec V6 — Artifact tracking. Evidence uit worker_output persistent opslaan.
Sectie 10. artifact_id formaat: artifact:{type}:{locator}.
"""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _sanitize_locator(locator: str) -> str:
    """Normaliseer locator voor artifact_id (geen lege of te lange waarden)."""
    if not locator or not isinstance(locator, str):
        return "unknown"
    return locator.strip()[:500]


class ArtifactTracker:
    """Track artifacts en citations; koppel tasks aan geciteerde artifacts."""

    def build_artifact_id(self, artifact_type: str, locator: str) -> str:
        """
        artifact_id formaat (platform spec sectie 10):
        artifact:{artifact_type}:{locator}
        Voorbeeld: artifact:repo:apps/web/checkout/Page.tsx
        """
        at = (artifact_type or "unknown").strip().lower().replace(" ", "_")
        loc = _sanitize_locator(locator)
        return f"artifact:{at}:{loc}"

    async def upsert_artifact(
        self,
        pool,
        artifact_type: str,
        locator: str,
        file_path: Optional[str] = None,
        git_commit: Optional[str] = None,
        line_start: Optional[int] = None,
        line_end: Optional[int] = None,
        symbol_name: Optional[str] = None,
    ) -> Optional[str]:
        """
        INSERT or UPDATE artifact. Return: artifact_id.
        Bij bestaande artifact_id: update git_commit, is_stale=false.
        """
        try:
            artifact_id = self.build_artifact_id(artifact_type, locator)
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO artifacts (
                        artifact_id, artifact_type, locator,
                        file_path, git_commit, line_start, line_end, symbol_name,
                        is_stale
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, false)
                    ON CONFLICT (artifact_id) DO UPDATE SET
                        git_commit = COALESCE(EXCLUDED.git_commit, artifacts.git_commit),
                        is_stale = false,
                        file_path = COALESCE(EXCLUDED.file_path, artifacts.file_path),
                        line_start = COALESCE(EXCLUDED.line_start, artifacts.line_start),
                        line_end = COALESCE(EXCLUDED.line_end, artifacts.line_end),
                        symbol_name = COALESCE(EXCLUDED.symbol_name, artifacts.symbol_name)
                    """,
                    artifact_id,
                    (artifact_type or "unknown").strip(),
                    _sanitize_locator(locator),
                    file_path,
                    git_commit,
                    line_start,
                    line_end,
                    symbol_name,
                )
            return artifact_id
        except Exception as e:
            logger.warning("ArtifactTracker upsert_artifact failed: %s", e)
            return None

    async def save_citations(
        self,
        pool,
        task_id: str,
        job_id: str,
        evidence_list: list[dict],
    ) -> list[str]:
        """
        Sla evidence items op als citations.
        Per item: upsert_artifact, dan INSERT citation.
        Return: lijst van citation_ids. Defensief: lege list → []; nooit blokkeren.
        """
        citation_ids: list[str] = []
        if not evidence_list:
            return citation_ids
        try:
            async with pool.acquire() as conn:
                for e in evidence_list:
                    if not isinstance(e, dict):
                        continue
                    artifact_type = e.get("artifact_type") or e.get("type") or "repo_file"
                    locator = e.get("file_path") or e.get("source_id") or e.get("locator") or ""
                    if not locator:
                        continue
                    aid = await self.upsert_artifact(
                        pool,
                        artifact_type=artifact_type,
                        locator=locator,
                        file_path=e.get("file_path"),
                        git_commit=e.get("git_commit"),
                        line_start=e.get("line_start"),
                        line_end=e.get("line_end"),
                        symbol_name=e.get("symbol_name"),
                    )
                    if not aid:
                        continue
                    row = await conn.fetchrow(
                        """
                        INSERT INTO citations (
                            task_id, job_id, artifact_id,
                            file_path, line_start, line_end, git_commit,
                            symbol_name, excerpt_summary
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        RETURNING citation_id
                        """,
                        task_id,
                        job_id,
                        aid,
                        e.get("file_path"),
                        e.get("line_start"),
                        e.get("line_end"),
                        e.get("git_commit"),
                        e.get("symbol_name"),
                        e.get("excerpt_summary") or e.get("summary"),
                    )
                    if row and row.get("citation_id"):
                        citation_ids.append(str(row["citation_id"]))
        except Exception as e:
            logger.warning("ArtifactTracker save_citations failed: %s", e)
        return citation_ids

    async def add_task_cited_edges(
        self,
        pool,
        graph,
        task_id: str,
        artifact_ids: list[str],
    ) -> None:
        """Voeg TASK_CITED edges toe: from_id=task_id, to_id=artifact_id."""
        if not artifact_ids:
            return
        try:
            from app.services.knowledge_graph import KnowledgeGraph
            kg = graph if isinstance(graph, KnowledgeGraph) else KnowledgeGraph()
            for aid in artifact_ids:
                if aid:
                    await kg.add_edge(
                        pool,
                        from_id=task_id,
                        to_id=aid,
                        edge_type="TASK_CITED",
                    )
        except Exception as e:
            logger.warning("ArtifactTracker add_task_cited_edges failed: %s", e)
