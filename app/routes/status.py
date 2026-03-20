"""Status/health summary endpoint and platform status intelligence APIs."""
import asyncio
import hashlib
import json
import os
import subprocess
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import httpx
import asyncpg
from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.database import get_db
from app.middleware.auth import TokenPayload, require_super_admin

router = APIRouter(prefix="/api/status", tags=["status"])


async def _check_http(url: str, timeout: float = 3.0) -> dict:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            return {"status": "ok", "detail": f"HTTP {resp.status_code}", "ok": resp.status_code < 400}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:100], "ok": False}


async def _check_redis() -> dict:
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, socket_timeout=2)
        return {"status": "ok", "detail": r.ping() and "PONG", "ok": True}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:100], "ok": False}


async def _check_postgres() -> dict:
    try:
        import asyncpg
        dsn = os.getenv('DATABASE_URL', 'postgresql://wonderz:wonderz123@localhost:5432/wonderz')
        conn = await asyncpg.connect(dsn, timeout=3)
        await conn.fetchval('SELECT 1')
        await conn.close()
        return {"status": "ok", "detail": "Connected", "ok": True}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:100], "ok": False}


async def _check_celery() -> dict:
    try:
        from workers.celery_app import celery
        insp = celery.control.inspect(timeout=2)
        active = insp.active_queues()
        if active:
            workers = list(active.keys())
            return {"status": "ok", "detail": f"{len(workers)} worker(s): {', '.join(workers[:3])}", "ok": True}
        return {"status": "error", "detail": "No workers", "ok": False}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:100], "ok": False}


def _check_systemd(service: str) -> dict:
    try:
        r = subprocess.run(['systemctl', 'is-active', service], capture_output=True, text=True, timeout=3)
        state = r.stdout.strip()
        return {"status": state, "ok": state == "active"}
    except Exception:
        return {"status": "unknown", "ok": False}


async def _get_llm_keys() -> dict:
    anthropic = bool(os.getenv('ANTHROPIC_API_KEY', '').strip())
    openai = bool(os.getenv('OPENAI_API_KEY', '').strip())
    active = []
    if anthropic: active.append('Anthropic')
    if openai: active.append('OpenAI')
    # Also check stored keys
    try:
        import json
        keys_file = '/home/exedev/wonderz-agentics/codex-web/api_keys.json'
        if os.path.exists(keys_file):
            with open(keys_file) as f:
                stored = json.load(f)
            for k in stored:
                if k.get('value') and 'ANTHROPIC' in k.get('name', '').upper() and 'Anthropic' not in active:
                    active.append('Anthropic')
                if k.get('value') and 'OPENAI' in k.get('name', '').upper() and 'OpenAI' not in active:
                    active.append('OpenAI')
    except Exception:
        pass
    return {
        "status": "ok" if active else "warning",
        "detail": f"Active: {', '.join(active)}" if active else "No API keys configured",
        "ok": len(active) > 0
    }


@router.get("/summary")
async def status_summary():
    # Run all checks in parallel
    backend_check, frontend_check, pg_check, redis_check, celery_check, terminal_check, codex_check, llm_check = await asyncio.gather(
        _check_http('http://localhost:8090/api/agents'),
        _check_http('http://localhost:3000/'),
        _check_postgres(),
        _check_redis(),
        _check_celery(),
        _check_http('http://localhost:7681/'),
        _check_http('http://localhost:8080/'),
        _get_llm_keys(),
    )

    # Systemd services
    systemd = {}
    for svc in ['wonderz-backend', 'wonderz-worker', 'wonderz-frontend', 'redis-server', 'wonderz-terminal', 'wonderz-codex-web']:
        short = svc.replace('wonderz-', '')
        systemd[short] = _check_systemd(svc)

    health = {
        "checks": {
            "backend": {**backend_check, "label": "Backend API", "detail": "Running (this service)"},
            "frontend": {**frontend_check, "label": "Frontend"},
            "database": {**pg_check, "label": "PostgreSQL"},
            "redis": {**redis_check, "label": "Redis"},
            "celery_worker": {**celery_check, "label": "Celery Worker"},
            "terminal": {**terminal_check, "label": "Terminal (ttyd)"},
            "codex_web": {**codex_check, "label": "Codex Console"},
            "llm_providers": {**llm_check, "label": "LLM Providers"},
        }
    }

    all_ok = all(c.get('ok') for c in health['checks'].values())
    backend_ok = health['checks']['backend'].get('ok', False)
    db_ok = health['checks']['database'].get('ok', False)
    health_status = "ok" if (backend_ok and db_ok) else ("degraded" if db_ok else "error")
    health["status"] = health_status

    active_providers = [p for p in (['Anthropic'] if os.getenv('ANTHROPIC_API_KEY', '').strip() else []) + (['OpenAI'] if os.getenv('OPENAI_API_KEY', '').strip() else [])]
    settings_ok = len(active_providers) > 0

    dave_ok = backend_ok
    dave_dev = {
        "ok": dave_ok,
        "status": "active" if dave_ok else "unknown",
        "specialization": "Full-stack Technical Consultant & Agentic Architecture Specialist" if dave_ok else "Geen data ontvangen",
    }

    recent_commits = []
    working_tree_top = []
    try:
        r = subprocess.run(
            ["git", "log", "-5", "--oneline"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        )
        if r.returncode == 0 and r.stdout:
            recent_commits = [line.strip() for line in r.stdout.strip().split("\n") if line.strip()]
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        )
        if r.returncode == 0 and r.stdout:
            working_tree_top = [line.strip() for line in r.stdout.strip().split("\n")[:8] if line.strip()]
    except Exception:
        pass

    return {
        "health": health,
        "systemd": systemd,
        "settings": {
            "ok": settings_ok,
            "active_providers": active_providers,
        },
        "dave_dev": dave_dev,
        "recent": {
            "recent_commits": recent_commits,
            "working_tree_top": working_tree_top,
        },
        "all_ok": all_ok,
    }

@router.get("/keys")
async def status_keys():
    """Zichtbaar op live URL: of API-keys geladen zijn (zonder de key te tonen). Fingerprint = eerste 8 tekens van sha256 om te verifiëren dat de juiste key geladen is."""
    anthropic_key = os.getenv('ANTHROPIC_API_KEY', '').strip()
    openai_key = os.getenv('OPENAI_API_KEY', '').strip()
    def _hash8(k):
        return hashlib.sha256(k.encode()).hexdigest()[:8] if k else ""
    return {
        "anthropic": {
            "loaded": bool(anthropic_key),
            "length": len(anthropic_key) if anthropic_key else 0,
            "fingerprint": _hash8(anthropic_key),
        },
        "openai": {
            "loaded": bool(openai_key),
            "length": len(openai_key) if openai_key else 0,
            "fingerprint": _hash8(openai_key),
        },
    }


@router.get("/api/health")
async def health_check():
    return {"status": "ok", "ok": True}


# --- Pipeline Metrics -------------------------------------------------------


async def _table_exists(conn: asyncpg.Connection, table_name: str) -> bool:
    return (
        await conn.fetchval(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = $1
            """,
            table_name,
        )
        is not None
    )


async def _column_exists(conn: asyncpg.Connection, table_name: str, column_name: str) -> bool:
    return (
        await conn.fetchval(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1 AND column_name = $2
            """,
            table_name,
            column_name,
        )
        is not None
    )


def _parse_int(value: Optional[int]) -> int:
    return int(value or 0)


def _parse_float(value: Optional[float]) -> float:
    return float(value) if value is not None else 0.0


@router.get(
    "/pipeline-metrics",
    dependencies=[Depends(require_super_admin)],
)
async def pipeline_metrics(
    days: int = Query(7, ge=1, le=90),
    _: TokenPayload = Depends(require_super_admin),
    pool: asyncpg.pool.Pool = Depends(get_db),
) -> Dict[str, Any]:
    """Pipeline health metrics for NEXUS pipeline and agents (super_admin only)."""
    async with pool.acquire() as conn:
        if not await _table_exists(conn, "jobs"):
            # Empty structure when jobs table does not exist yet
            return {
                "summary": {
                    "total_jobs": 0,
                    "success_rate": 0.0,
                    "avg_duration_seconds": 0,
                    "failed_today": 0,
                },
                "nexus_phases": [],
                "agent_performance": [],
                "daily_trend": [],
                "recent_jobs": [],
                "errors": [],
            }

        # Summary
        summary_row = await conn.fetchrow(
            """
            SELECT
              COUNT(*) AS total_jobs,
              COUNT(*) FILTER (WHERE status = 'COMPLETED') * 100.0 / NULLIF(COUNT(*), 0) AS success_rate,
              AVG(EXTRACT(EPOCH FROM (completed_at - created_at)))
                  FILTER (WHERE status = 'COMPLETED' AND completed_at IS NOT NULL) AS avg_duration_seconds,
              COUNT(*) FILTER (WHERE status = 'FAILED' AND created_at > now() - INTERVAL '1 day') AS failed_today
            FROM jobs
            WHERE created_at > now() - ($1::int || ' days')::interval
            """,
            days,
        )
        summary = {
            "total_jobs": _parse_int(summary_row["total_jobs"]) if summary_row else 0,
            "success_rate": _parse_float(summary_row["success_rate"]) if summary_row else 0.0,
            "avg_duration_seconds": _parse_int(summary_row["avg_duration_seconds"])
            if summary_row and summary_row["avg_duration_seconds"] is not None
            else 0,
            "failed_today": _parse_int(summary_row["failed_today"]) if summary_row else 0,
        }

        # NEXUS phase timings (fallback: step_name as phase)
        nexus_phases: List[Dict[str, Any]] = []
        if await _table_exists(conn, "job_steps") and await _column_exists(conn, "job_steps", "timing_ms"):
            nexus_rows = await conn.fetch(
                """
                SELECT
                  COALESCE(step_name, 'unknown') AS phase_name,
                  AVG(timing_ms) AS avg_timing_ms,
                  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY timing_ms) AS p95_timing_ms,
                  COUNT(*) FILTER (WHERE status = 'failed') * 100.0 / NULLIF(COUNT(*), 0) AS failure_rate,
                  COUNT(*) AS total_executions
                FROM job_steps
                WHERE created_at > now() - ($1::int || ' days')::interval
                  AND timing_ms IS NOT NULL
                GROUP BY COALESCE(step_name, 'unknown')
                ORDER BY phase_name
                """,
                days,
            )
            for r in nexus_rows:
                nexus_phases.append(
                    {
                        "phase": r["phase_name"],
                        "avg_timing_ms": _parse_int(r["avg_timing_ms"]),
                        "p95_timing_ms": _parse_int(r["p95_timing_ms"]),
                        "failure_rate": _parse_float(r["failure_rate"]),
                        "total_executions": _parse_int(r["total_executions"]),
                    }
                )

        # Agent performance (agent_role used as agent_id fallback)
        agent_performance: List[Dict[str, Any]] = []
        if await _table_exists(conn, "job_steps") and await _column_exists(conn, "job_steps", "agent_role"):
            agent_rows = await conn.fetch(
                """
                SELECT
                  agent_role AS agent_id,
                  AVG(timing_ms) AS avg_timing_ms,
                  COUNT(*) AS total_executions,
                  COUNT(*) FILTER (WHERE status = 'failed') * 100.0 / NULLIF(COUNT(*), 0) AS failure_rate
                FROM job_steps
                WHERE created_at > now() - ($1::int || ' days')::interval
                  AND agent_role IS NOT NULL
                GROUP BY agent_role
                ORDER BY avg_timing_ms DESC
                LIMIT 20
                """,
                days,
            )
            for r in agent_rows:
                avg_ms = _parse_int(r["avg_timing_ms"])
                agent_performance.append(
                    {
                        "agent_id": r["agent_id"],
                        "avg_timing_ms": avg_ms,
                        "total_executions": _parse_int(r["total_executions"]),
                        "failure_rate": _parse_float(r["failure_rate"]),
                        "is_bottleneck": avg_ms > 60000,
                    }
                )

        # Daily trend
        daily_trend: List[Dict[str, Any]] = []
        trend_rows = await conn.fetch(
            """
            SELECT
              DATE(created_at) AS date,
              COUNT(*) AS total,
              COUNT(*) FILTER (WHERE status = 'COMPLETED') AS completed,
              COUNT(*) FILTER (WHERE status = 'FAILED') AS failed
            FROM jobs
            WHERE created_at > now() - ($1::int || ' days')::interval
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at)
            """,
            days,
        )
        for r in trend_rows:
            d: date = r["date"]
            daily_trend.append(
                {
                    "date": d.isoformat(),
                    "total": _parse_int(r["total"]),
                    "completed": _parse_int(r["completed"]),
                    "failed": _parse_int(r["failed"]),
                }
            )

        # Recent jobs (last 10)
        recent_jobs: List[Dict[str, Any]] = []
        recent_rows = await conn.fetch(
            """
            SELECT
              id,
              job_post,
              status,
              created_at,
              completed_at,
              NULL::text AS company_id
            FROM jobs
            ORDER BY created_at DESC
            LIMIT 10
            """
        )
        for r in recent_rows:
            created = r["created_at"]
            completed = r["completed_at"]
            duration_seconds: Optional[int] = None
            if created and completed:
                duration_seconds = int((completed - created).total_seconds())
            recent_jobs.append(
                {
                    "id": str(r["id"]),
                    "title": (r["job_post"] or "")[:160],
                    "status": r["status"],
                    "created_at": created.isoformat() if created else "",
                    "duration_seconds": duration_seconds,
                    "company_id": r["company_id"] or "",
                }
            )

        # Errors from system_events
        errors: List[Dict[str, Any]] = []
        if await _table_exists(conn, "system_events"):
            error_rows = await conn.fetch(
                """
                SELECT
                  event_type,
                  agent_id,
                  COUNT(*) AS count,
                  MAX(created_at) AS last_seen
                FROM system_events
                WHERE created_at > now() - ($1::int || ' days')::interval
                  AND severity IN ('error', 'critical')
                GROUP BY event_type, agent_id
                ORDER BY count DESC
                LIMIT 50
                """,
                days,
            )
            for r in error_rows:
                last_seen = r["last_seen"]
                errors.append(
                    {
                        "event_type": r["event_type"],
                        "agent_id": r["agent_id"],
                        "count": _parse_int(r["count"]),
                        "last_seen": last_seen.isoformat() if last_seen else "",
                    }
                )

    return {
        "summary": summary,
        "nexus_phases": nexus_phases,
        "agent_performance": agent_performance,
        "daily_trend": daily_trend,
        "recent_jobs": recent_jobs,
        "errors": errors,
    }


# --- Storage & Costs --------------------------------------------------------


@router.get(
    "/storage-costs",
    dependencies=[Depends(require_super_admin)],
)
async def storage_costs(
    days: int = Query(30, ge=1, le=365),
    _: TokenPayload = Depends(require_super_admin),
    pool: asyncpg.pool.Pool = Depends(get_db),
) -> Dict[str, Any]:
    """Storage footprint, embeddings en token-kosten (super_admin only)."""
    async with pool.acquire() as conn:
        table_sizes: List[Dict[str, Any]] = []
        size_rows = await conn.fetch(
            """
            SELECT
              relname AS table_name,
              n_live_tup AS row_count,
              pg_total_relation_size(relid) / 1024.0 / 1024.0 AS size_mb
            FROM pg_stat_user_tables
            WHERE relname = ANY($1::text[])
            ORDER BY pg_total_relation_size(relid) DESC
            """,
            [
                "jobs",
                "job_steps",
                "agent_knowledge",
                "direct_chat_messages",
                "direct_chats",
                "development_points",
                "system_events",
                "clients",
                "client_datasources",
                "client_knowledge",
                "knowledge_documents",
                "knowledge_chunks",
            ],
        )
        for r in size_rows:
            table_sizes.append(
                {
                    "table_name": r["table_name"],
                    "row_count": _parse_int(r["row_count"]),
                    "size_mb": round(_parse_float(r["size_mb"]), 2),
                }
            )

        # Embedding stats: client_knowledge + clients (per client)
        embedding_total_chunks = 0
        embedding_total_size_mb = 0.0
        embedding_per_client: List[Dict[str, Any]] = []

        if await _table_exists(conn, "client_knowledge"):
            row = await conn.fetchrow(
                "SELECT COUNT(*) AS chunk_count FROM client_knowledge WHERE is_active = true"
            )
            embedding_total_chunks = _parse_int(row["chunk_count"]) if row else 0
            size_row = await conn.fetchrow(
                """
                SELECT pg_total_relation_size('client_knowledge') / 1024.0 / 1024.0 AS size_mb
                """
            )
            embedding_total_size_mb = round(
                _parse_float(size_row["size_mb"]) if size_row else 0.0, 2
            )

            if await _table_exists(conn, "clients"):
                per_client_rows = await conn.fetch(
                    """
                    SELECT
                      ck.client_id,
                      c.client_name AS company_name,
                      COUNT(*) AS chunk_count,
                      COUNT(DISTINCT ck.datasource_id) AS source_count
                    FROM client_knowledge ck
                    LEFT JOIN clients c ON c.client_id = ck.client_id
                    WHERE ck.is_active = true
                    GROUP BY ck.client_id, c.client_name
                    ORDER BY chunk_count DESC
                    """
                )
                for r in per_client_rows:
                    embedding_per_client.append(
                        {
                            "company_id": r["client_id"],
                            "company_name": r["company_name"] or "",
                            "chunk_count": _parse_int(r["chunk_count"]),
                            "source_count": _parse_int(r["source_count"]),
                        }
                    )

        embedding_stats = {
            "total_chunks": embedding_total_chunks,
            "total_size_mb": embedding_total_size_mb,
            "per_client": embedding_per_client,
        }

        # Token costs: jobs + job_steps tokens_used, plus direct chat token_usage
        token_costs: Dict[str, Any] = {
            "data_available": False,
            "total_tokens": None,
            "estimated_cost_usd": None,
            "per_client": [],
            "daily_trend": [],
        }

        tokens_available = await _table_exists(conn, "job_steps") and await _column_exists(
            conn, "job_steps", "tokens_used"
        )
        if tokens_available:
            since = date.today() - timedelta(days=days)
            total_row = await conn.fetchrow(
                """
                SELECT
                  COALESCE(SUM(tokens_used), 0) AS step_tokens
                FROM job_steps
                WHERE created_at >= $1::date
                """,
                since,
            )
            step_tokens = _parse_int(total_row["step_tokens"]) if total_row else 0

            # Direct chat token usage
            dc_tokens = 0
            if await _table_exists(conn, "direct_chat_messages") and await _column_exists(
                conn, "direct_chat_messages", "token_usage"
            ):
                dc_row = await conn.fetchrow(
                    """
                    SELECT COALESCE(SUM(token_usage), 0) AS tokens
                    FROM direct_chat_messages
                    WHERE created_at >= $1::date
                    """,
                    since,
                )
                dc_tokens = _parse_int(dc_row["tokens"]) if dc_row else 0

            total_tokens = step_tokens + dc_tokens
            # Pricing: $9 per 1M tokens (gemiddeld)
            estimated_cost_usd = round((total_tokens / 1_000_000.0) * 9.0, 4)

            # Daily trend
            daily_trend: List[Dict[str, Any]] = []
            dc_msg_has_token_usage = await _column_exists(
                conn, "direct_chat_messages", "token_usage"
            )
            if dc_msg_has_token_usage:
                trend_rows = await conn.fetch(
                    """
                    WITH step_tokens AS (
                      SELECT
                        DATE(created_at) AS day,
                        COALESCE(SUM(tokens_used), 0) AS tokens
                      FROM job_steps
                      WHERE created_at >= $1::date
                      GROUP BY DATE(created_at)
                    ),
                    chat_tokens AS (
                      SELECT
                        DATE(created_at) AS day,
                        COALESCE(SUM(token_usage), 0) AS tokens
                      FROM direct_chat_messages
                      WHERE created_at >= $1::date
                      GROUP BY DATE(created_at)
                    )
                    SELECT
                      d.day,
                      COALESCE(s.tokens, 0) + COALESCE(c.tokens, 0) AS tokens
                    FROM generate_series($1::date, $2::date, interval '1 day') AS d(day)
                    LEFT JOIN step_tokens s ON s.day = d.day
                    LEFT JOIN chat_tokens c ON c.day = d.day
                    ORDER BY d.day
                    """,
                    since,
                    date.today(),
                )
            else:
                trend_rows = await conn.fetch(
                    """
                    WITH step_tokens AS (
                      SELECT
                        DATE(created_at) AS day,
                        COALESCE(SUM(tokens_used), 0) AS tokens
                      FROM job_steps
                      WHERE created_at >= $1::date
                      GROUP BY DATE(created_at)
                    )
                    SELECT
                      d.day,
                      COALESCE(s.tokens, 0) AS tokens
                    FROM generate_series($1::date, $2::date, interval '1 day') AS d(day)
                    LEFT JOIN step_tokens s ON s.day = d.day
                    ORDER BY d.day
                    """,
                    since,
                    date.today(),
                )
            for r in trend_rows:
                d = r["day"]
                tks = _parse_int(r["tokens"])
                daily_trend.append(
                    {
                        "date": d.isoformat(),
                        "tokens": tks,
                        "estimated_cost_usd": round((tks / 1_000_000.0) * 9.0, 4),
                    }
                )

            token_costs = {
                "data_available": True,
                "total_tokens": total_tokens,
                "estimated_cost_usd": estimated_cost_usd,
                "per_client": [],  # No reliable client mapping on jobs; platform-wide only
                "daily_trend": daily_trend,
            }

        # Direct chat stats
        total_messages = 0
        period_messages = 0
        if await _table_exists(conn, "direct_chat_messages"):
            row = await conn.fetchrow("SELECT COUNT(*) AS c FROM direct_chat_messages")
            total_messages = _parse_int(row["c"]) if row else 0
            row = await conn.fetchrow(
                """
                SELECT COUNT(*) AS c
                FROM direct_chat_messages
                WHERE created_at >= now() - ($1::int || ' days')::interval
                """,
                days,
            )
            period_messages = _parse_int(row["c"]) if row else 0

    return {
        "table_sizes": table_sizes,
        "embedding_stats": embedding_stats,
        "token_costs": token_costs,
        "direct_chat_stats": {
            "total_messages": total_messages,
            "period_messages": period_messages,
        },
    }


# --- Edge Intelligence ------------------------------------------------------


async def collect_diagnostics(days: int, pool: asyncpg.pool.Pool) -> Dict[str, Any]:
    """Verzamel diagnostische data voor Edge Intelligence analyse."""
    async with pool.acquire() as conn:
        diagnostics: Dict[str, Any] = {}

        # Top 5 failed jobs
        failed_jobs: List[Dict[str, Any]] = []
        if await _table_exists(conn, "jobs"):
            rows = await conn.fetch(
                """
                SELECT
                  j.id,
                  j.job_post,
                  j.status,
                  j.created_at,
                  j.completed_at
                FROM jobs j
                WHERE j.created_at > now() - ($1::int || ' days')::interval
                  AND j.status = 'FAILED'
                ORDER BY j.created_at DESC
                LIMIT 5
                """,
                days,
            )
            for r in rows:
                failed_jobs.append(
                    {
                        "id": str(r["id"]),
                        "title": (r["job_post"] or "")[:160],
                        "status": r["status"],
                        "created_at": r["created_at"].isoformat() if r["created_at"] else "",
                        "completed_at": r["completed_at"].isoformat()
                        if r["completed_at"]
                        else "",
                    }
                )
        diagnostics["failed_jobs"] = failed_jobs

        # Bottleneck agents (avg_timing_ms > 60000)
        bottleneck_agents: List[Dict[str, Any]] = []
        if await _table_exists(conn, "job_steps") and await _column_exists(
            conn, "job_steps", "timing_ms"
        ):
            rows = await conn.fetch(
                """
                SELECT
                  agent_role AS agent_id,
                  AVG(timing_ms) AS avg_timing_ms,
                  COUNT(*) AS executions
                FROM job_steps
                WHERE created_at > now() - ($1::int || ' days')::interval
                  AND agent_role IS NOT NULL
                GROUP BY agent_role
                HAVING AVG(timing_ms) > 60000
                ORDER BY avg_timing_ms DESC
                LIMIT 10
                """,
                days,
            )
            for r in rows:
                bottleneck_agents.append(
                    {
                        "agent_id": r["agent_id"],
                        "avg_timing_ms": _parse_int(r["avg_timing_ms"]),
                        "executions": _parse_int(r["executions"]),
                    }
                )
        diagnostics["bottleneck_agents"] = bottleneck_agents

        # Failure rate per pseudo NEXUS phase (step_name)
        phase_failures: List[Dict[str, Any]] = []
        if await _table_exists(conn, "job_steps"):
            rows = await conn.fetch(
                """
                SELECT
                  COALESCE(step_name, 'unknown') AS phase,
                  COUNT(*) AS total,
                  COUNT(*) FILTER (WHERE status = 'failed') AS failed
                FROM job_steps
                WHERE created_at > now() - ($1::int || ' days')::interval
                GROUP BY COALESCE(step_name, 'unknown')
                ORDER BY failed DESC
                """,
                days,
            )
            for r in rows:
                total = _parse_int(r["total"])
                failed = _parse_int(r["failed"])
                failure_rate = (failed * 100.0 / total) if total else 0.0
                phase_failures.append(
                    {
                        "phase": r["phase"],
                        "total": total,
                        "failed": failed,
                        "failure_rate": round(failure_rate, 2),
                    }
                )
        diagnostics["phase_failures"] = phase_failures

        # Clients zonder embeddings (Knowledge Hub leeg)
        clients_without_embeddings: List[Dict[str, Any]] = []
        if await _table_exists(conn, "clients") and await _table_exists(
            conn, "client_knowledge"
        ):
            rows = await conn.fetch(
                """
                SELECT
                  c.client_id,
                  c.client_name
                FROM clients c
                LEFT JOIN (
                  SELECT DISTINCT client_id
                  FROM client_knowledge
                  WHERE is_active = true
                ) ck ON ck.client_id = c.client_id
                WHERE ck.client_id IS NULL
                LIMIT 20
                """
            )
            for r in rows:
                clients_without_embeddings.append(
                    {
                        "company_id": r["client_id"],
                        "company_name": r["client_name"] or "",
                    }
                )
        diagnostics["clients_without_embeddings"] = clients_without_embeddings

        # System events (error/critical)
        system_events: List[Dict[str, Any]] = []
        if await _table_exists(conn, "system_events"):
            rows = await conn.fetch(
                """
                SELECT
                  event_type,
                  severity,
                  agent_id,
                  COUNT(*) AS count,
                  MAX(created_at) AS last_seen
                FROM system_events
                WHERE created_at > now() - ($1::int || ' days')::interval
                  AND severity IN ('error', 'critical')
                GROUP BY event_type, severity, agent_id
                ORDER BY count DESC
                LIMIT 50
                """,
                days,
            )
            for r in rows:
                system_events.append(
                    {
                        "event_type": r["event_type"],
                        "severity": r["severity"],
                        "agent_id": r["agent_id"],
                        "count": _parse_int(r["count"]),
                        "last_seen": r["last_seen"].isoformat() if r["last_seen"] else "",
                    }
                )
        diagnostics["system_events"] = system_events

    return diagnostics


def build_intelligence_prompt(diagnostic_data: Dict[str, Any], days: int) -> str:
    """Bouw de natuurlijke-taal prompt voor Claude op basis van diagnostische data."""
    failed_jobs = diagnostic_data.get("failed_jobs") or []
    bottleneck_agents = diagnostic_data.get("bottleneck_agents") or []
    phase_failures = diagnostic_data.get("phase_failures") or []
    system_events = diagnostic_data.get("system_events") or []
    clients_without_embeddings = diagnostic_data.get("clients_without_embeddings") or []

    lines: List[str] = []
    lines.append(f"Platform diagnostische data — afgelopen {days} dagen:")
    lines.append("")

    # Jobs summary
    total_jobs = len(failed_jobs)
    lines.append("JOBS (sample gefaalde jobs):")
    if not failed_jobs:
        lines.append("- Geen gefaalde jobs in de sample.")
    else:
        for j in failed_jobs:
            lines.append(
                f"- Job {j['id']} — status={j['status']}, created_at={j['created_at']}, completed_at={j['completed_at']}"
            )
    lines.append("")

    # Bottleneck agents
    lines.append("BOTTLENECK AGENTS (avg_timing_ms > 60000):")
    if not bottleneck_agents:
        lines.append("- Geen bottleneck agents gedetecteerd.")
    else:
        for a in bottleneck_agents:
            lines.append(
                f"- {a['agent_id']}: avg {a['avg_timing_ms']}ms, {a['executions']} executions"
            )
    lines.append("")

    # Phase failures
    lines.append("NEXUS FASE FAILURES (op basis van step_name):")
    if not phase_failures:
        lines.append("- Geen phase failure data beschikbaar.")
    else:
        for p in phase_failures:
            lines.append(
                f"- {p['phase']}: {p['failure_rate']}% failure rate ({p['failed']}/{p['total']} failures)"
            )
    lines.append("")

    # System events
    lines.append("SYSTEM EVENTS (errors/critical):")
    if not system_events:
        lines.append("- Geen system events met severity error/critical.")
    else:
        for e in system_events:
            lines.append(
                f"- {e['event_type']} (severity={e['severity']}): {e['count']}x — laatste: {e['last_seen']} (agent={e['agent_id']})"
            )
    lines.append("")

    # Clients zonder embeddings
    lines.append("CLIENTS ZONDER EMBEDDINGS (lege Knowledge Hub):")
    if not clients_without_embeddings:
        lines.append("- Geen clients zonder embeddings gedetecteerd.")
    else:
        for c in clients_without_embeddings:
            lines.append(f"- {c['company_id']}: 0 chunks (naam={c['company_name']})")
    lines.append("")

    # Belangrijke notitie over clients
    lines.append(
        "NOTITIE: Client-koppeling op jobs niet beschikbaar. Analyse is op platform-niveau (jobs en agents), niet per client."
    )
    lines.append("")
    lines.append("Analyseer deze data en genereer een platform health rapport.")

    return "\n".join(lines)


@router.post(
    "/edge-intelligence",
    dependencies=[Depends(require_super_admin)],
)
async def edge_intelligence(
    body: Dict[str, Any] = Body(default={"days": 7}),
    _: TokenPayload = Depends(require_super_admin),
    pool: asyncpg.pool.Pool = Depends(get_db),
) -> Dict[str, Any]:
    """AI-gedreven Edge Intelligence analyse (super_admin only)."""
    days = int(body.get("days") or 7)
    if days < 1:
        days = 1
    if days > 90:
        days = 90

    diagnostics = await collect_diagnostics(days, pool)
    prompt = build_intelligence_prompt(diagnostics, days)

    api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        # Geen key: graceful fallback
        return {
            "health_score": None,
            "error": "Intelligence engine tijdelijk niet beschikbaar (geen ANTHROPIC_API_KEY)",
            "problems": [],
            "root_causes": [],
            "architecture_scores": None,
            "fix_suggestions": [],
        }

    try:
        from anthropic import Anthropic

        client = Anthropic()
    except Exception as e:  # pragma: no cover - defensive
        return {
            "health_score": None,
            "error": f"Intelligence engine init mislukt: {e}",
            "problems": [],
            "root_causes": [],
            "architecture_scores": None,
            "fix_suggestions": [],
        }

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            system=(
                "Je bent een platform intelligence expert voor het Wonderz multi-agent platform.\n"
                "Analyseer de diagnostische data en geef een JSON response met exact deze structuur:\n"
                "{\n"
                '  "health_score": 0-100,\n'
                '  "problems": [\n'
                "    {\n"
                '      "type": "string",\n'
                '      "severity": "info|warning|critical",\n'
                '      "description": "string",\n'
                '      "affected_components": ["string"],\n'
                '      "metric": "string"\n'
                "    }\n"
                "  ],\n"
                '  "root_causes": [\n'
                "    {\n"
                '      "problem_type": "string",\n'
                '      "analysis": "string",\n'
                '      "evidence": "string",\n'
                '      "confidence": 0.0-1.0\n'
                "    }\n"
                "  ],\n"
                '  "architecture_scores": {\n'
                '    "nexus_pipeline": 0-100,\n'
                '    "agent_reliability": 0-100,\n'
                '    "knowledge_coverage": 0-100,\n'
                '    "cost_efficiency": 0-100\n'
                "  },\n"
                '  "fix_suggestions": [\n'
                "    {\n"
                '      "priority": "easy_win|medium|strategic",\n'
                '      "title": "string",\n'
                '      "description": "string",\n'
                '      "implementation": "string",\n'
                '      "estimated_impact": "string"\n'
                "    }\n"
                "  ]\n"
                "}\n"
                "Geef ALLEEN de JSON terug, geen uitleg eromheen."
            ),
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception:
        # Geen 500: altijd graceful fallback
        return {
            "health_score": None,
            "error": "Intelligence engine tijdelijk niet beschikbaar",
            "problems": [],
            "root_causes": [],
            "architecture_scores": None,
            "fix_suggestions": [],
        }

