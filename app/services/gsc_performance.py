"""
GSC performance per gepubliceerde job-URL.
Herbruikt OAuth/tokens via client_integrations (google_search_console) zoals seo_gsc_fetcher / dashboard.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
from datetime import date, timedelta
from typing import Any, Optional
from uuid import UUID

import asyncpg
import httpx

from app.services.dashboard import get_valid_access_token
from app.services.credential_resolver import resolve_integration_row

logger = logging.getLogger(__name__)

GSC_BASE_URL = "https://www.googleapis.com/webmasters/v3"


def _coerce_dict(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            v = json.loads(raw)
            return v if isinstance(v, dict) else {}
        except Exception:
            return {}
    return {}


def _client_slug_for_job(job_row: asyncpg.Record) -> Optional[str]:
    payload = _coerce_dict(job_row.get("payload"))
    ctx = _coerce_dict(job_row.get("context"))
    slug = payload.get("client_slug") or ctx.get("client_slug")
    return str(slug).strip() if slug else None


def _canonical_url(u: str) -> str:
    return (u or "").strip().rstrip("/")


async def _query_gsc_page_metrics(
    access_token: str,
    site_url: str,
    page_url: str,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    site_encoded = urllib.parse.quote(site_url, safe="")
    api_url = f"{GSC_BASE_URL}/sites/{site_encoded}/searchAnalytics/query"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    body: dict[str, Any] = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": ["page"],
        "dimensionFilterGroups": [
            {
                "filters": [
                    {
                        "dimension": "page",
                        "operator": "equals",
                        "expression": page_url,
                    }
                ]
            }
        ],
        "rowLimit": 25,
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        res = await client.post(api_url, headers=headers, json=body)
        if res.status_code != 200:
            logger.warning(
                "gsc_performance: API status=%s body=%s", res.status_code, (res.text or "")[:400]
            )
            return {"error": f"GSC API {res.status_code}", "rows": []}
        data = res.json()
    rows = data.get("rows") or []
    if not rows:
        # Probeer zonder filter: sommige property-URL's matchen beter op prefix
        body.pop("dimensionFilterGroups", None)
        body["dimensions"] = ["page"]
        body["rowLimit"] = 500
        async with httpx.AsyncClient(timeout=45.0) as client:
            res = await client.post(api_url, headers=headers, json=body)
            if res.status_code != 200:
                return {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": None, "rows": []}
            data = res.json()
        rows = data.get("rows") or []
        canon = _canonical_url(page_url)
        for row in rows:
            keys = row.get("keys") or []
            p = keys[0] if keys else ""
            if _canonical_url(str(p)) == canon or str(p).rstrip("/") == page_url.rstrip("/"):
                return {
                    "clicks": int(row.get("clicks", 0)),
                    "impressions": int(row.get("impressions", 0)),
                    "ctr": float(row.get("ctr", 0) or 0),
                    "position": float(row.get("position", 0) or 0) or None,
                    "rows": [row],
                }
        return {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": None, "rows": []}

    row = rows[0]
    return {
        "clicks": int(row.get("clicks", 0)),
        "impressions": int(row.get("impressions", 0)),
        "ctr": float(row.get("ctr", 0) or 0),
        "position": float(row.get("position", 0) or 0) or None,
        "rows": rows[:5],
    }


async def fetch_url_performance(
    pool: asyncpg.pool.Pool,
    job_id: str,
    days_back: int = 28,
) -> dict[str, Any]:
    """
    Haal GSC-metrics op voor jobs.published_url en sla één rij op in job_performance.
    """
    try:
        jid = UUID(job_id)
    except Exception:
        return {"error": "Ongeldige job_id"}

    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    async with pool.acquire() as conn:
        job = await conn.fetchrow(
            """
            SELECT id, user_id, published_url, context, payload
            FROM jobs
            WHERE id = $1
            """,
            jid,
        )
        if not job:
            return {"error": "Job niet gevonden"}
        pub = (job.get("published_url") or "").strip()
        if not pub:
            return {"error": "Job heeft geen published_url"}

        user_id = str(job["user_id"])
        client_slug = _client_slug_for_job(job)
        if not client_slug:
            return {"error": "Job heeft geen client_slug in context/payload; GSC koppeling onbekend"}

        row = await resolve_integration_row(
            conn,
            client_slug=client_slug,
            integration_type="google_search_console",
            user_id=user_id,
        )
        site_url: Optional[str] = None
        if row and row.get("extra_config"):
            extra = row["extra_config"]
            if isinstance(extra, dict) and extra.get("site_url"):
                site_url = str(extra["site_url"])
            elif isinstance(extra, str):
                try:
                    d = json.loads(extra)
                    if isinstance(d, dict) and d.get("site_url"):
                        site_url = str(d["site_url"])
                except Exception:
                    pass

        if not site_url:
            row2 = await conn.fetchrow(
                """
                SELECT config FROM client_platform_configs
                WHERE user_id = $1 AND client_slug = $2 AND platform = 'gsc'
                """,
                user_id,
                client_slug,
            )
            if row2 and row2.get("config"):
                cfg = row2["config"]
                if isinstance(cfg, dict) and cfg.get("site_url"):
                    site_url = str(cfg["site_url"])

        if not site_url:
            return {"error": "Geen GSC site_url voor deze client"}

        token = await get_valid_access_token(conn, user_id, client_slug, "google_search_console")
        if not token:
            return {"error": "Geen geldig GSC access token"}

        metrics = await _query_gsc_page_metrics(token, site_url, pub, start_date, end_date)
        if metrics.get("error"):
            return {"error": metrics["error"]}

        clicks = int(metrics.get("clicks", 0))
        impressions = int(metrics.get("impressions", 0))
        ctr = float(metrics.get("ctr", 0) or 0)
        position = metrics.get("position")

        raw = {
            "gsc": metrics,
            "site_url": site_url,
            "page": pub,
        }

        await conn.execute(
            """
            INSERT INTO job_performance
            (job_id, url, clicks, impressions, ctr, average_position,
             date_range_start, date_range_end, raw_data)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
            """,
            jid,
            pub,
            clicks,
            impressions,
            ctr,
            position,
            start_date,
            end_date,
            json.dumps(raw),
        )

    return {
        "job_id": job_id,
        "url": pub,
        "clicks": clicks,
        "impressions": impressions,
        "ctr": ctr,
        "average_position": position,
        "period_days": days_back,
    }


async def scan_job_performance(pool: asyncpg.pool.Pool) -> list[str]:
    """
    Jobs met published_at > 30 dagen en laatste job_performance-snapshot: lage GSC → agent_improvements.
    Retourneert job_id's waarvoor een nieuw punt is aangemaakt.
    """
    created: list[str] = []

    async with pool.acquire() as conn:
        has_jp = await conn.fetchval(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'job_performance'
            """
        )
        if not has_jp:
            return created

        has_pub = await conn.fetchval(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'jobs' AND column_name = 'published_url'
            """
        )
        if not has_pub:
            return created

        cols_ai = await conn.fetch(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'agent_improvements'
            """
        )
        ai_col_set = {r["column_name"] for r in cols_ai}
        if not ai_col_set:
            return created

        rows = await conn.fetch(
            """
            WITH latest AS (
                SELECT DISTINCT ON (job_id)
                    job_id,
                    measured_at,
                    clicks,
                    ctr,
                    average_position,
                    url
                FROM job_performance
                ORDER BY job_id, measured_at DESC
            )
            SELECT
                j.id AS job_id,
                j.published_url,
                j.published_at,
                jp.clicks,
                jp.ctr,
                jp.average_position,
                jp.measured_at,
                COALESCE(
                    (
                        SELECT agent_id FROM job_steps
                        WHERE job_id = j.id AND agent_id IS NOT NULL AND agent_id != ''
                        ORDER BY step_index DESC NULLS LAST
                        LIMIT 1
                    ),
                    'agent:copywriter'
                ) AS producer_agent_id
            FROM jobs j
            INNER JOIN latest jp ON jp.job_id = j.id
            WHERE j.published_url IS NOT NULL
              AND j.published_at IS NOT NULL
              AND j.published_at < now() - INTERVAL '30 days'
              AND (
                  jp.clicks = 0
                  OR jp.ctr < 0.01
                  OR (jp.average_position IS NOT NULL AND jp.average_position > 50)
              )
            """
        )

        for row in rows:
            job_uuid = str(row["job_id"])
            agent_id = row["producer_agent_id"] or "agent:copywriter"
            clicks = int(row["clicks"] or 0)
            ctr_f = float(row["ctr"] or 0)
            pos = row["average_position"]
            pos_f = float(pos) if pos is not None else None
            url_s = row["published_url"] or ""

            if clicks == 0:
                severity = "HIGH"
                reason = "zero_clicks"
                title = f"[GSC] Nul clicks na 30+ dagen ({url_s[:80]})"
            elif ctr_f < 0.01:
                severity = "MEDIUM"
                reason = "low_ctr"
                title = f"[GSC] CTR {round(ctr_f * 100, 2)}% onder 1% ({url_s[:60]})"
            elif pos_f is not None and pos_f > 50:
                severity = "LOW"
                reason = "weak_position"
                title = f"[GSC] Gem. positie {round(pos_f, 1)} (>50) ({url_s[:50]})"
            else:
                continue

            details_obj = {
                "gsc_job_id": job_uuid,
                "source": "gsc_performance",
                "reason": reason,
                "url": url_s,
                "clicks": clicks,
                "ctr": ctr_f,
                "position": pos_f,
                "measured_at": row["measured_at"].isoformat() if row.get("measured_at") else None,
            }
            details_json = json.dumps(details_obj)
            needle = f'%"gsc_job_id": "{job_uuid}"%'

            existing = await conn.fetchval(
                """
                SELECT id FROM agent_improvements
                WHERE status = 'OPEN'
                  AND details::text LIKE $1
                LIMIT 1
                """,
                needle,
            )
            if existing:
                continue

            agent_name = agent_id
            name_row = await conn.fetchrow(
                "SELECT name FROM hired_agents WHERE agent_id = $1 LIMIT 1",
                agent_id,
            )
            if name_row and name_row.get("name"):
                agent_name = name_row["name"]

            insert_cols = ["agent_id", "agent_name", "title", "details", "severity", "status"]
            insert_vals: list[Any] = [agent_id, agent_name, title, details_json, severity, "OPEN"]
            if "source" in ai_col_set:
                insert_cols.append("source")
                insert_vals.append("gsc_performance")

            ph = ", ".join(f"${i}" for i in range(1, len(insert_vals) + 1))
            await conn.execute(
                f"""
                INSERT INTO agent_improvements ({", ".join(insert_cols)})
                VALUES ({ph})
                """,
                *insert_vals,
            )
            created.append(job_uuid)
            logger.info("GSC HR: development point voor job %s (%s)", job_uuid, reason)

    return created
