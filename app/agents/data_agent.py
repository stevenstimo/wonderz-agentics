"""
DataAgent — Worker for data-query jobs.
Does not perform content tasks. Fetches data and presents as table/list.
Part of the DIRECT_RESPONSE pipeline (no copy_agent, no reviewer_agent).
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DataAgent:
    """
    Worker agent for data_query jobs.
    Receives query_params from the CEO orchestrator.
    Returns a structured data result conforming to the output contract.
    """

    def __init__(self, db: Any, gsc_service: Any = None, analytics_service: Any = None):
        self.db = db
        self.gsc_service = gsc_service
        self.analytics_service = analytics_service

    async def execute(self, job_id: str, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry. Runs the data query from query_params.

        Args:
            job_id: Job ID for job_steps logging.
            query_params: datasource, client_slug, site_url, period_days, metric, top_k, raw_query.

        Returns:
            Output contract: gevonden, resultaat, volledigheid, volgende_actie.
        """
        datasource = query_params.get("datasource", "gsc")
        client_slug = query_params.get("client_slug")
        site_url = query_params.get("site_url")
        period_days = query_params.get("period_days", 28)
        metric = query_params.get("metric", ["clicks", "impressions"])
        top_k = query_params.get("top_k", 10)

        async with self.db.acquire() as conn:
            await self._log_step_start(conn, job_id, query_params)

        try:
            if datasource == "gsc":
                result = await self._query_gsc(
                    site_url=site_url,
                    period_days=period_days,
                    metric=metric,
                    top_k=top_k,
                )
            elif datasource == "client_knowledge":
                async with self.db.acquire() as conn:
                    result = await self._query_client_knowledge(conn, client_slug, query_params.get("raw_query", ""), top_k)
            else:
                result = self._unsupported_datasource(datasource)

            async with self.db.acquire() as conn:
                await self._log_step_done(conn, job_id)
            return result

        except Exception as e:
            logger.exception("DataAgent.execute failed for job %s: %s", job_id, e)
            async with self.db.acquire() as conn:
                await self._log_step_failed(conn, job_id, str(e))
            return self._error_result(str(e))

    async def _query_gsc(
        self,
        site_url: Optional[str],
        period_days: int,
        metric: List[str],
        top_k: int,
    ) -> Dict[str, Any]:
        """
        Fetch data from Google Search Console.
        Returns top_k pages sorted by clicks (desc).
        """
        if not self.gsc_service:
            return self._unavailable_result(
                "Google Search Console",
                "GSC service niet geconfigureerd. Controleer de OAuth-koppeling.",
            )

        if not site_url:
            return self._missing_param_result("site_url")

        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=period_days)

        try:
            rows = await self.gsc_service.get_top_pages(
                site_url=site_url,
                start_date=str(start_date),
                end_date=str(end_date),
                dimensions=["page"],
                metrics=metric,
                limit=top_k,
            )
        except Exception as e:
            return self._unavailable_result("Google Search Console", str(e))

        if not rows:
            return {
                "gevonden": f"GSC data voor {site_url} over de afgelopen {period_days} dagen",
                "resultaat": [],
                "volledigheid": "Geen data gevonden voor deze periode. Controleer of de GSC-koppeling actief is en of er traffic is in deze periode.",
                "volgende_actie": None,
            }

        return {
            "gevonden": (
                f"Top {len(rows)} pagina's uit Google Search Console "
                f"voor {site_url} — periode: {start_date} t/m {end_date} "
                f"({period_days} dagen)"
            ),
            "resultaat": rows,
            "volledigheid": self._check_completeness(rows, metric),
            "volgende_actie": f"Bekijk de volledige GSC data op Search Console voor {site_url}.",
        }

    async def _query_client_knowledge(
        self,
        conn: Any,
        client_slug: Optional[str],
        query: str,
        top_k: int,
    ) -> Dict[str, Any]:
        """
        Query the client knowledge base. Uses client_id from clients table (slug -> client_id).
        Schema: client_knowledge has client_id, chunk_text, source_url, page_title, added_at.
        """
        if not client_slug:
            return self._missing_param_result("client_slug")

        try:
            row = await conn.fetchrow(
                """
                SELECT client_id FROM clients
                WHERE LOWER(slug) = LOWER($1)
                LIMIT 1
                """,
                client_slug.strip(),
            )
        except Exception as e:
            return self._unavailable_result("Client Knowledge Base", str(e))

        if not row:
            return {
                "gevonden": f"Klant '{client_slug}' niet gevonden.",
                "resultaat": [],
                "volledigheid": f"Geen client met slug '{client_slug}'.",
                "volgende_actie": None,
            }

        client_id = row["client_id"]

        try:
            rows = await conn.fetch(
                """
                SELECT chunk_text, source_url, page_title, added_at
                FROM client_knowledge
                WHERE client_id = $1 AND is_active = true
                ORDER BY added_at DESC
                LIMIT $2
                """,
                client_id,
                top_k,
            )
        except Exception as e:
            return self._unavailable_result("Client Knowledge Base", str(e))

        if not rows:
            return {
                "gevonden": f"Client knowledge base voor klant '{client_slug}'",
                "resultaat": [],
                "volledigheid": f"Geen kennisdocumenten gevonden voor klant '{client_slug}'. Voeg bronnen toe via de Kennisbronnen tab.",
                "volgende_actie": None,
            }

        result_list = [
            {
                "chunk_text": r["chunk_text"],
                "source_url": r.get("source_url"),
                "page_title": r.get("page_title"),
                "added_at": r["added_at"].isoformat() if r.get("added_at") else None,
            }
            for r in rows
        ]
        return {
            "gevonden": f"Top {len(rows)} kennisfragmenten voor klant '{client_slug}'",
            "resultaat": result_list,
            "volledigheid": "Resultaten gesorteerd op toegevoegdatum (nieuwste eerst).",
            "volgende_actie": None,
        }

    def _check_completeness(self, rows: List[Dict], requested_metrics: List[str]) -> str:
        """Check whether requested metrics are present in the results."""
        if not rows:
            return "Geen data."
        sample = rows[0] if isinstance(rows[0], dict) else {}
        missing = [m for m in requested_metrics if m not in sample]
        if missing:
            return f"Let op: de volgende metrics ontbreken in de resultaten: {', '.join(missing)}."
        zero_values = [
            m for m in requested_metrics
            if all((row.get(m, 0) == 0 for row in rows if isinstance(row, dict)))
        ]
        if zero_values:
            return f"De volgende metrics zijn nul voor alle resultaten: {', '.join(zero_values)}. Controleer de GSC-koppeling of de gekozen periode."
        return "Alle gevraagde metrics aanwezig."

    def _missing_param_result(self, param: str) -> Dict[str, Any]:
        return {
            "gevonden": "Onvolledig verzoek",
            "resultaat": [],
            "volledigheid": f"Kritieke parameter ontbreekt: '{param}'. De CEO had dit moeten opvragen tijdens de intake.",
            "volgende_actie": "Herstart de job met de juiste parameters.",
        }

    def _unavailable_result(self, source: str, reason: str) -> Dict[str, Any]:
        return {
            "gevonden": f"Databron niet beschikbaar: {source}",
            "resultaat": [],
            "volledigheid": f"Kan geen data ophalen: {reason}",
            "volgende_actie": "Controleer de koppeling via Instellingen.",
        }

    def _unsupported_datasource(self, datasource: str) -> Dict[str, Any]:
        return {
            "gevonden": f"Onbekende databron: {datasource}",
            "resultaat": [],
            "volledigheid": f"Databron '{datasource}' wordt niet ondersteund. Ondersteunde bronnen: gsc, client_knowledge.",
            "volgende_actie": None,
        }

    def _error_result(self, error: str) -> Dict[str, Any]:
        return {
            "gevonden": "Fout tijdens ophalen data",
            "resultaat": [],
            "volledigheid": f"Technische fout: {error}",
            "volgende_actie": "Bekijk de backend logs voor details.",
        }

    async def _log_step_start(self, conn: Any, job_id: str, query_params: Dict[str, Any]) -> None:
        """Insert one job_steps row for data_retrieval. Columns aligned with migration 040 + 069 and _insert_plan_steps."""
        try:
            payload_json = json.dumps(query_params, default=_json_default)
            await conn.execute(
                """
                INSERT INTO job_steps (
                    job_id, step_index, step_name, agent_role, agent,
                    status, input_payload, created_at
                )
                VALUES ($1, 0, 'data_retrieval', 'data-analyst', 'agent:data-analyst', 'running', $2::jsonb, now())
                """,
                job_id,
                payload_json,
            )
        except Exception as e:
            logger.warning("Could not create job_step for job %s: %s", job_id, e)

    async def _log_step_done(self, conn: Any, job_id: str) -> None:
        """Mark the data_retrieval step completed. Identify by job_id + step_name + status running."""
        try:
            await conn.execute(
                """
                UPDATE job_steps
                SET status = 'completed', completed_at = now()
                WHERE job_id = $1 AND step_name = 'data_retrieval' AND status = 'running'
                """,
                job_id,
            )
        except Exception as e:
            logger.warning("Could not update job_step to completed for job %s: %s", job_id, e)

    async def _log_step_failed(self, conn: Any, job_id: str, error: str) -> None:
        """Mark the data_retrieval step failed and set error_log (migration 069)."""
        try:
            await conn.execute(
                """
                UPDATE job_steps
                SET status = 'failed', error_log = $2, completed_at = now()
                WHERE job_id = $1 AND step_name = 'data_retrieval' AND status = 'running'
                """,
                job_id,
                error,
            )
        except Exception as e:
            logger.warning("Could not mark job_step failed for job %s: %s", job_id, e)


def _json_default(obj: Any) -> Any:
    from datetime import date, datetime
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
