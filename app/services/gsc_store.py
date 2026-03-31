"""
GSC Data Store Service
Centrale service voor het opslaan en ophalen van GSC data.

Principe:
- Schrijven: upsert per dag per pagina per query
- Lezen: altijd uit de store, nooit direct van de API
- Sync tracking: bijhouden welke dagen al zijn gesynchroniseerd
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


async def get_synced_dates(
    db: asyncpg.Connection,
    client_slug: str,
    start_date: date,
    end_date: date,
) -> set[date]:
    """Geeft alle al gesynchroniseerde datums terug voor een client in een periode."""
    rows = await db.fetch(
        """
        SELECT sync_date FROM gsc_sync_log
        WHERE client_slug = $1
          AND sync_date BETWEEN $2 AND $3
          AND status = 'completed'
        """,
        client_slug,
        start_date,
        end_date,
    )
    return {row["sync_date"] for row in rows}


async def get_missing_dates(
    db: asyncpg.Connection,
    client_slug: str,
    start_date: date,
    end_date: date,
) -> list[date]:
    """Geeft lijst van datums die nog niet gesynchroniseerd zijn."""
    synced = await get_synced_dates(db, client_slug, start_date, end_date)
    all_dates: list[date] = []
    current = start_date
    while current <= end_date:
        if current not in synced:
            all_dates.append(current)
        current += timedelta(days=1)
    return all_dates


async def upsert_gsc_rows(
    db: asyncpg.Connection,
    client_slug: str,
    sync_date: date,
    rows: list[dict[str, Any]],
    site_url: str,
) -> dict[str, int]:
    """
    Upsert GSC data voor één dag.
    rows: lijst van dicts met keys: page, query, clicks, impressions, ctr, position
    """
    inserted = 0
    updated = 0

    if rows:
        for row in rows:
            page = str(row.get("page") or "").strip()
            if not page:
                continue
            query = row.get("query")
            if isinstance(query, str):
                query = query.strip() or None
            result = await db.execute(
                """
                INSERT INTO gsc_data_store
                  (client_slug, date, page, query, clicks, impressions, ctr, position, site_url)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (client_slug, date, page, COALESCE(query, ''))
                DO UPDATE SET
                  clicks = EXCLUDED.clicks,
                  impressions = EXCLUDED.impressions,
                  ctr = EXCLUDED.ctr,
                  position = EXCLUDED.position,
                  fetched_at = now()
                """,
                client_slug,
                sync_date,
                page,
                query,
                int(row.get("clicks", 0) or 0),
                int(row.get("impressions", 0) or 0),
                row.get("ctr"),
                row.get("position"),
                site_url,
            )
            if result == "INSERT 0 1":
                inserted += 1
            else:
                updated += 1

    await db.execute(
        """
        INSERT INTO gsc_sync_log (client_slug, sync_date, rows_inserted, rows_updated, status)
        VALUES ($1, $2, $3, $4, 'completed')
        ON CONFLICT (client_slug, sync_date)
        DO UPDATE SET
          rows_inserted = EXCLUDED.rows_inserted,
          rows_updated = EXCLUDED.rows_updated,
          status = 'completed',
          error_message = NULL,
          synced_at = now()
        """,
        client_slug,
        sync_date,
        inserted,
        updated,
    )

    return {"inserted": inserted, "updated": updated}


async def log_sync_failed(
    db: asyncpg.Connection,
    client_slug: str,
    sync_date: date,
    error: str,
) -> None:
    """Logt een mislukte sync."""
    await db.execute(
        """
        INSERT INTO gsc_sync_log (client_slug, sync_date, status, error_message)
        VALUES ($1, $2, 'failed', $3)
        ON CONFLICT (client_slug, sync_date)
        DO UPDATE SET status = 'failed', error_message = EXCLUDED.error_message, synced_at = now()
        """,
        client_slug,
        sync_date,
        error,
    )


async def query_gsc_store(
    db: asyncpg.Connection,
    client_slug: str,
    start_date: date,
    end_date: date,
    group_by: str = "page",
) -> list[dict[str, Any]]:
    """
    Haalt geaggregeerde GSC data op uit de store voor een periode.
    group_by="page": aggregeer per pagina (voor blog-overzichten)
    group_by="query": aggregeer per zoekterm
    """
    if group_by == "page":
        rows = await db.fetch(
            """
            SELECT
              page,
              SUM(clicks) AS clicks,
              SUM(impressions) AS impressions,
              ROUND(AVG(ctr)::numeric, 4) AS avg_ctr,
              ROUND(AVG(position)::numeric, 1) AS avg_position,
              MIN(date) AS first_seen,
              MAX(date) AS last_seen,
              COUNT(DISTINCT date) AS days_with_data
            FROM gsc_data_store
            WHERE client_slug = $1
              AND date BETWEEN $2 AND $3
            GROUP BY page
            ORDER BY clicks DESC
            """,
            client_slug,
            start_date,
            end_date,
        )
    else:
        rows = await db.fetch(
            """
            SELECT
              query,
              SUM(clicks) AS clicks,
              SUM(impressions) AS impressions,
              ROUND(AVG(ctr)::numeric, 4) AS avg_ctr,
              ROUND(AVG(position)::numeric, 1) AS avg_position
            FROM gsc_data_store
            WHERE client_slug = $1
              AND date BETWEEN $2 AND $3
              AND query IS NOT NULL
            GROUP BY query
            ORDER BY clicks DESC
            """,
            client_slug,
            start_date,
            end_date,
        )

    return [dict(row) for row in rows]


async def get_store_coverage(
    db: asyncpg.Connection,
    client_slug: str,
) -> dict[str, Any]:
    """Geeft een overzicht van welke data beschikbaar is in de store."""
    row = await db.fetchrow(
        """
        SELECT
          MIN(date) AS earliest_date,
          MAX(date) AS latest_date,
          COUNT(DISTINCT date) AS total_days,
          COUNT(*) AS total_rows
        FROM gsc_data_store
        WHERE client_slug = $1
        """,
        client_slug,
    )
    return dict(row) if row else {}
