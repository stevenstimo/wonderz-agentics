"""
CFO Service — Token Cost Monitoring
Geen pipeline-impact. Alleen observeren, berekenen en rapporteren.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

# Prijslijst per model (USD per miljoen tokens, maart 2026)
MODEL_PRICING = {
    "claude-sonnet": {
        "input": 3.00,
        "output": 15.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
    },
    "claude-haiku": {
        "input": 0.80,
        "output": 4.00,
        "cache_write": 1.00,
        "cache_read": 0.08,
    },
}

# EUR/USD wisselkoers (handmatig bijwerken indien nodig)
USD_TO_EUR = 0.92


def _get_pricing(model: str) -> dict:
    """Match model string naar prijslijst. Fallback naar sonnet."""
    model_lower = model.lower()
    if "haiku" in model_lower:
        return MODEL_PRICING["claude-haiku"]
    return MODEL_PRICING["claude-sonnet"]


def calculate_cost_usd(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """Bereken kosten in USD op basis van token aantallen en model."""
    pricing = _get_pricing(model)
    cost = (
        (input_tokens * pricing["input"] / 1_000_000)
        + (output_tokens * pricing["output"] / 1_000_000)
        + (cache_write_tokens * pricing["cache_write"] / 1_000_000)
        + (cache_read_tokens * pricing["cache_read"] / 1_000_000)
    )
    return round(cost, 6)


def anthropic_usage_record(model: str, response: Any) -> Optional[Dict[str, Any]]:
    """Bouw een usage-dict uit een Anthropic messages response (sync SDK)."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return {
        "model": model,
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        "cache_write_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
    }


async def log_token_usage(
    conn: asyncpg.Connection,
    job_id: str,
    step_name: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
    agent_id: Optional[str] = None,
    job_step_id: Optional[str] = None,
) -> None:
    """
    Log token gebruik na elke LLM-aanroep.
    Aanroepen vanuit elke plek waar de Anthropic API wordt gebruikt.
    """
    cost_usd = calculate_cost_usd(
        model, input_tokens, output_tokens, cache_write_tokens, cache_read_tokens
    )
    try:
        await conn.execute(
            """
            INSERT INTO token_usage_log
                (job_id, job_step_id, agent_id, step_name, model,
                 input_tokens, output_tokens, cache_write_tokens, cache_read_tokens, cost_usd)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            job_id,
            job_step_id,
            agent_id,
            step_name,
            model,
            input_tokens,
            output_tokens,
            cache_write_tokens,
            cache_read_tokens,
            cost_usd,
        )
    except Exception as e:
        logger.warning("[CFO] token_usage_log insert failed (non-blocking): %s", e)


async def log_token_usage_records(
    conn: asyncpg.Connection,
    job_id: str,
    step_name: str,
    records: List[Dict[str, Any]],
    agent_id: Optional[str] = None,
    job_step_id: Optional[str] = None,
) -> None:
    """Log meerdere Anthropic usage records (bijv. retry in copywriter)."""
    for rec in records or []:
        if not rec:
            continue
        await log_token_usage(
            conn,
            job_id,
            step_name,
            rec.get("model") or "unknown",
            input_tokens=int(rec.get("input_tokens") or 0),
            output_tokens=int(rec.get("output_tokens") or 0),
            cache_write_tokens=int(rec.get("cache_write_tokens") or 0),
            cache_read_tokens=int(rec.get("cache_read_tokens") or 0),
            agent_id=agent_id,
            job_step_id=job_step_id,
        )


def _num(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _row_dict(r: asyncpg.Record) -> Dict[str, Any]:
    d = dict(r)
    out: Dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif hasattr(v, "isoformat"):
            out[k] = v.isoformat() if v is not None else None
        else:
            out[k] = v
    return out


async def get_cfo_dashboard(
    conn: asyncpg.Connection,
    period_days: int = 30,
) -> dict:
    """
    Aggregeer token- en kostenoverzicht voor het CFO dashboard.
    """
    totals = await conn.fetchrow(
        """
        SELECT
            COUNT(DISTINCT job_id) AS total_jobs,
            SUM(input_tokens + output_tokens) AS total_tokens,
            SUM(cost_usd) AS total_cost_usd,
            SUM(cost_usd) * $2::double precision AS total_cost_eur
        FROM token_usage_log
        WHERE recorded_at >= now() - ($1 * interval '1 day')
        """,
        period_days,
        USD_TO_EUR,
    )

    per_agent = await conn.fetch(
        """
        SELECT
            agent_id,
            SUM(input_tokens + output_tokens) AS tokens,
            SUM(cost_usd) AS cost_usd,
            SUM(cost_usd) * $2::double precision AS cost_eur,
            COUNT(DISTINCT job_id) AS jobs
        FROM token_usage_log
        WHERE recorded_at >= now() - ($1 * interval '1 day')
          AND agent_id IS NOT NULL
        GROUP BY agent_id
        ORDER BY SUM(cost_usd) DESC NULLS LAST
        LIMIT 10
        """,
        period_days,
        USD_TO_EUR,
    )

    per_model = await conn.fetch(
        """
        SELECT
            model,
            SUM(input_tokens + output_tokens) AS tokens,
            SUM(cost_usd) AS cost_usd,
            SUM(cost_usd) * $2::double precision AS cost_eur
        FROM token_usage_log
        WHERE recorded_at >= now() - ($1 * interval '1 day')
        GROUP BY model
        ORDER BY SUM(cost_usd) DESC NULLS LAST
        """,
        period_days,
        USD_TO_EUR,
    )

    expensive_jobs = await conn.fetch(
        """
        SELECT
            job_id,
            SUM(input_tokens + output_tokens) AS tokens,
            SUM(cost_usd) AS cost_usd,
            SUM(cost_usd) * $2::double precision AS cost_eur
        FROM token_usage_log
        WHERE recorded_at >= now() - ($1 * interval '1 day')
        GROUP BY job_id
        ORDER BY SUM(cost_usd) DESC NULLS LAST
        LIMIT 5
        """,
        period_days,
        USD_TO_EUR,
    )

    daily_trend = await conn.fetch(
        """
        SELECT
            (recorded_at AT TIME ZONE 'UTC')::date AS dag,
            SUM(input_tokens + output_tokens) AS tokens,
            SUM(cost_usd) AS cost_usd
        FROM token_usage_log
        WHERE recorded_at >= now() - interval '14 days'
        GROUP BY (recorded_at AT TIME ZONE 'UTC')::date
        ORDER BY dag DESC
        """,
    )

    totals_d = _row_dict(totals) if totals else {}
    if totals_d:
        for k in ("total_jobs", "total_tokens"):
            if totals_d.get(k) is not None:
                totals_d[k] = int(totals_d[k])
        for k in ("total_cost_usd", "total_cost_eur"):
            totals_d[k] = _num(totals_d.get(k))

    return {
        "period_days": period_days,
        "totals": totals_d,
        "per_agent": [_row_dict(r) for r in per_agent],
        "per_model": [_row_dict(r) for r in per_model],
        "expensive_jobs": [_row_dict(r) for r in expensive_jobs],
        "daily_trend": [_row_dict(r) for r in daily_trend],
        "usd_to_eur": USD_TO_EUR,
    }
