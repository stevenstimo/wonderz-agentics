"""
Developer Bot debug API — beveiligd intern endpoint voor job logs, DB queries, agent steps.
Alleen voor intern gebruik met DEV_BOT_TOKEN.
"""

import json
import logging
import os
import re
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Depends

from app.database import get_db
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dev", tags=["dev"])
devbot_router = APIRouter(prefix="/api/devbot", tags=["devbot"])

DEV_TOKEN = os.getenv("DEV_BOT_TOKEN", "wonderz-dev-internal")


class DevQuery(BaseModel):
    query_type: str  # health | job | job_steps | agents | recent_errors | db_stats
    params: dict = {}
    token: str


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "hex"):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def verify_token(token: str) -> None:
    if token != DEV_TOKEN:
        raise HTTPException(status_code=403, detail="Unauthorized")


@router.post("/query")
async def dev_query(query: DevQuery, db=Depends(get_db)):
    verify_token(query.token)

    if query.query_type == "health":
        return await query_health(db)

    elif query.query_type == "job":
        job_id = query.params.get("job_id")
        job_number = query.params.get("job_number")
        return await query_job(db, job_id=job_id, job_number=job_number)

    elif query.query_type == "job_steps":
        job_id = query.params.get("job_id")
        job_number = query.params.get("job_number")
        return await query_job_steps(db, job_id=job_id, job_number=job_number)

    elif query.query_type == "agents":
        return await query_agents(db)

    elif query.query_type == "recent_errors":
        return await query_recent_errors(db)

    elif query.query_type == "db_stats":
        return await query_db_stats(db)

    else:
        raise HTTPException(
            status_code=400, detail=f"Unknown query_type: {query.query_type}"
        )


async def query_health(db) -> dict:
    async with db.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT NOW() as db_time, version() as pg_version"
        )
        jobs_running = await conn.fetchval(
            "SELECT COUNT(*) FROM jobs WHERE status = 'RUNNING'"
        )
        jobs_failed = await conn.fetchval(
            "SELECT COUNT(*) FROM jobs WHERE status = 'FAILED'"
        )
    pg_ver = result["pg_version"] or ""
    return {
        "status": "ok",
        "db_time": str(result["db_time"]),
        "pg_version": pg_ver[:50] if pg_ver else "",
        "jobs_running": jobs_running or 0,
        "jobs_failed_total": jobs_failed or 0,
    }


async def query_job(db, job_id: Optional[str] = None, job_number: Optional[int] = None) -> dict:
    async with db.acquire() as conn:
        if job_number is not None:
            job_num_int = int(job_number)
            row = await conn.fetchrow(
                """SELECT * FROM jobs
                   WHERE job_number_int = $1
                   ORDER BY created_at DESC LIMIT 1""",
                job_num_int,
            )
        elif job_id:
            row = await conn.fetchrow(
                "SELECT * FROM jobs WHERE id = $1", job_id
            )
        else:
            rows = await conn.fetch(
                """SELECT id, context, job_post, status, tokens_used, token_budget,
                          created_at, updated_at, job_number_int
                   FROM jobs ORDER BY created_at DESC LIMIT 5"""
            )
            out = []
            for r in rows:
                d = dict(r)
                jni = d.get("job_number_int")
                job_num = f"{jni:04d}" if jni is not None else "?"
                out.append({
                    "job_id": str(d.get("id", "")),
                    "job_number": job_num,
                    "title": (d.get("job_post") or "")[:80],
                    "status": d.get("status"),
                    "token_used_total": d.get("tokens_used"),
                    "token_budget": d.get("token_budget"),
                    "created_at": d.get("created_at"),
                })
            return {"recent_jobs": out}

    if not row:
        return {"error": "Job niet gevonden"}

    job = dict(row)
    job.pop("context", None)
    job.pop("job_post", None)
    if "id" in job:
        job["job_id"] = str(job.pop("id"))
    return {"job": job}


async def query_job_steps(
    db, job_id: Optional[str] = None, job_number: Optional[int] = None
) -> dict:
    async with db.acquire() as conn:
        if job_number is not None:
            job_num_int = int(job_number)
            job = await conn.fetchrow(
                """SELECT id FROM jobs
                   WHERE job_number_int = $1
                   ORDER BY created_at DESC LIMIT 1""",
                job_num_int,
            )
            if job:
                job_id = str(job["id"])

        if not job_id:
            return {"error": "Geen job_id of job_number opgegeven"}

        steps = await conn.fetch(
            """SELECT step_index, step_name, agent_role, status, tokens_used,
                      timing_ms, output, created_at, started_at, completed_at
               FROM job_steps WHERE job_id = $1 ORDER BY step_index, created_at""",
            job_id,
        )

    out = []
    for s in steps:
        d = dict(s)
        output = d.get("output") or {}
        if isinstance(output, str):
            try:
                output = json.loads(output) if output else {}
            except json.JSONDecodeError:
                output = {}
        error_log = output.get("error") if isinstance(output, dict) else None
        out.append({
            "step_name": d.get("step_name"),
            "step_index": d.get("step_index"),
            "status": d.get("status"),
            "agent_id": d.get("agent_role"),
            "token_usage": d.get("tokens_used"),
            "latency_ms": d.get("timing_ms"),
            "error_log": error_log,
            "started_at": d.get("started_at"),
            "completed_at": d.get("completed_at"),
        })
    return {"job_id": job_id, "steps": out}


async def query_agents(db) -> dict:
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """SELECT agent_id, name as agent_name, role, status
               FROM hired_agents ORDER BY role NULLS LAST, name NULLS LAST"""
        )
    return {"agents": [dict(r) for r in rows]}


async def query_recent_errors(db) -> dict:
    async with db.acquire() as conn:
        try:
            rows = await conn.fetch(
                """SELECT j.id as job_id, j.context, j.job_number_int, js.step_index, js.step_name,
                          js.output, js.created_at
                   FROM job_steps js
                   JOIN jobs j ON js.job_id = j.id
                   WHERE js.output IS NOT NULL
                     AND js.output::text LIKE '%error%'
                   ORDER BY js.created_at DESC NULLS LAST
                   LIMIT 20"""
            )
        except Exception:
            return {"recent_errors": [], "note": "Query failed - schema may differ"}

    out = []
    for r in rows:
        jni = r.get("job_number_int")
        job_num = f"{jni:04d}" if jni is not None else "?"
        output = r.get("output") or {}
        if isinstance(output, str):
            try:
                output = json.loads(output) if output else {}
            except json.JSONDecodeError:
                output = {}
        err = output.get("error", str(output)[:500]) if output else ""
        out.append({
            "job_number": job_num,
            "job_id": str(r.get("job_id", "")),
            "step_name": r.get("step_name"),
            "error_log": err,
            "started_at": r.get("created_at"),
        })
    return {"recent_errors": out}


async def query_db_stats(db) -> dict:
    tables = [
        "jobs",
        "job_steps",
        "hired_agents",
        "agent_skills",
        "agent_knowledge",
        "development_points",
        "agent_inbox",
    ]
    stats = {}
    async with db.acquire() as conn:
        for table in tables:
            try:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                stats[table] = count
            except Exception:
                stats[table] = "tabel niet gevonden"
    return {"table_counts": stats}


# --- Developer Bot chat (uses dev query + AI) ---

class DevbotAskRequest(BaseModel):
    prompt: str


DEV_BOT_SYSTEM_PROMPT = """Je bent de Developer Bot van Wonderz. Je hebt directe toegang tot de database via interne API calls.

Beschikbare queries die je kunt uitvoeren (de backend voert deze al voor je uit op basis van de vraag):
- health: algemene systeemstatus
- job (job_number: 137): details van een specifieke job
- job_steps (job_number: 137): alle stappen van een job inclusief errors
- agents: lijst van alle agents en hun status
- recent_errors: laatste 20 errors uit job_steps
- db_stats: aantal records per tabel

Wanneer iemand vraagt naar een job, error of systeemstatus: de ruwe data wordt je gegeven. Toon de data beknopt en geef dan je analyse. Antwoord in dezelfde taal als de gebruiker."""


def _parse_prompt_for_queries(prompt: str) -> list[tuple[str, dict]]:
    """Parse user prompt and return list of (query_type, params) to run."""
    queries = []
    prompt_lower = prompt.strip().lower()

    # Job number: #137, job 137, job #0137
    job_match = re.search(r"#?(\d{1,6})\b", prompt)
    if job_match:
        job_num = int(job_match.group(1))
        if "step" in prompt_lower or "stap" in prompt_lower or "error" in prompt_lower:
            queries.append(("job_steps", {"job_number": job_num}))
        queries.append(("job", {"job_number": job_num}))

    # Health / status
    if any(kw in prompt_lower for kw in ("health", "status", "systeem", "hoe gaat het")):
        queries.append(("health", {}))

    # Errors
    if any(kw in prompt_lower for kw in ("error", "fout", "recent_errors", "laatste errors")):
        queries.append(("recent_errors", {}))

    # Agents
    if any(kw in prompt_lower for kw in ("agent", "agents", "hired")):
        queries.append(("agents", {}))

    # DB stats
    if any(kw in prompt_lower for kw in ("db_stats", "tabel", "count", "aantal records")):
        queries.append(("db_stats", {}))

    # If nothing matched but we have a job number, we already added job
    if not queries and job_match:
        queries.append(("job", {"job_number": int(job_match.group(1))}))

    # Default: health + recent jobs
    if not queries:
        queries = [("health", {}), ("job", {})]

    return queries


@devbot_router.post("/ask")
async def devbot_ask(req: DevbotAskRequest, db=Depends(get_db)):
    """Developer Bot: runs relevant dev queries and answers with AI."""
    prompt = (req.prompt or "").strip()
    if not prompt:
        return {"answer": "Stel een vraag over jobs, errors, agents of systeemstatus."}

    queries_to_run = _parse_prompt_for_queries(prompt)
    context_parts = []

    for qtype, params in queries_to_run:
        try:
            if qtype == "health":
                data = await query_health(db)
            elif qtype == "job":
                data = await query_job(db, **params)
            elif qtype == "job_steps":
                data = await query_job_steps(db, **params)
            elif qtype == "agents":
                data = await query_agents(db)
            elif qtype == "recent_errors":
                data = await query_recent_errors(db)
            elif qtype == "db_stats":
                data = await query_db_stats(db)
            else:
                continue
            context_parts.append(f"=== {qtype} ===\n{json.dumps(data, default=_json_default, indent=2)}")
        except Exception as e:
            logger.exception("devbot query %s failed", qtype)
            context_parts.append(f"=== {qtype} (error) ===\n{str(e)}")

    db_context = "\n\n".join(context_parts)
    user_content = f"{prompt}\n\n--- Database context ---\n{db_context}"

    try:
        from anthropic import Anthropic
        client = Anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=DEV_BOT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        text = response.content[0].text if response.content else ""
    except Exception as e:
        logger.exception("Claude API failed in devbot_ask")
        return {
            "answer": f"Kon geen AI-antwoord genereren: {e}. Hier is de ruwe data:\n\n{db_context[:2000]}"
        }

    return {"answer": text}
