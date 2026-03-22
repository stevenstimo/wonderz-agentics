"""
Eval API: suites, cases, runs, seed (admin).
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db
from app.middleware.auth import (
    TokenPayload,
    get_current_user,
    require_admin_or_super_admin,
)

router = APIRouter(prefix="/api/evals", tags=["evals"])


def _row_to_json(row: Any) -> dict[str, Any]:
    d = dict(row)
    for k, v in list(d.items()):
        if hasattr(v, "hex"):  # UUID
            d[k] = str(v)
    return d


@router.get("/suites", dependencies=[Depends(get_current_user)])
async def list_suites(pool=Depends(get_db)):
    """Lijst van alle eval suites."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, suite_type, description, is_active, created_at
            FROM eval_suites
            ORDER BY name
            """
        )
    return {"suites": [_row_to_json(r) for r in rows]}


@router.get("/suites/{name}/cases", dependencies=[Depends(get_current_user)])
async def list_cases_for_suite(name: str, pool=Depends(get_db)):
    """Cases per suite (op suite-naam, bijv. regression / capability)."""
    async with pool.acquire() as conn:
        suite = await conn.fetchrow(
            "SELECT * FROM eval_suites WHERE name = $1",
            name,
        )
        if not suite:
            raise HTTPException(status_code=404, detail=f"Suite '{name}' niet gevonden")
        rows = await conn.fetch(
            """
            SELECT id, suite_id, name, job_type, input_payload, expected_checks, is_active, created_at, updated_at
            FROM eval_cases
            WHERE suite_id = $1
            ORDER BY created_at
            """,
            suite["id"],
        )
    out = []
    for r in rows:
        d = _row_to_json(r)
        for key in ("input_payload", "expected_checks"):
            if isinstance(d.get(key), str):
                try:
                    d[key] = json.loads(d[key])
                except Exception:
                    pass
        out.append(d)
    return {"suite": name, "cases": out}


@router.post("/run/{suite_name}", dependencies=[Depends(get_current_user)])
async def start_eval_run(
    suite_name: str,
    current_user: TokenPayload = Depends(get_current_user),
    pool=Depends(get_db),
):
    """Start een eval run voor de opgegeven suite."""
    from app.services.eval_runner import run_eval_suite

    triggered = current_user.user_id or "manual"
    return await run_eval_suite(pool, suite_name, triggered_by=triggered)


@router.get("/runs", dependencies=[Depends(get_current_user)])
async def list_runs(
    pool=Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    """Recente eval runs."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT r.id, r.suite_id, r.triggered_by, r.started_at, r.finished_at,
                   r.total_cases, r.passed_cases, r.failed_cases, r.pass_rate, r.status, r.summary,
                   s.name AS suite_name
            FROM eval_runs r
            LEFT JOIN eval_suites s ON s.id = r.suite_id
            ORDER BY r.started_at DESC
            LIMIT $1
            """,
            limit,
        )
    return {"runs": [_row_to_json(r) for r in rows]}


@router.get("/runs/{run_id}", dependencies=[Depends(get_current_user)])
async def get_run_detail(run_id: str, pool=Depends(get_db)):
    """Detail van één run inclusief resultaten."""
    try:
        rid = uuid.UUID(run_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Ongeldige run_id")

    async with pool.acquire() as conn:
        run = await conn.fetchrow(
            """
            SELECT r.*, s.name AS suite_name
            FROM eval_runs r
            LEFT JOIN eval_suites s ON s.id = r.suite_id
            WHERE r.id = $1
            """,
            rid,
        )
        if not run:
            raise HTTPException(status_code=404, detail="Run niet gevonden")
        results = await conn.fetch(
            """
            SELECT er.*, ec.name AS case_name
            FROM eval_results er
            LEFT JOIN eval_cases ec ON ec.id = er.case_id
            WHERE er.run_id = $1
            ORDER BY er.created_at
            """,
            rid,
        )

    run_d = _row_to_json(run)
    res_list = []
    for r in results:
        d = _row_to_json(r)
        for key in ("checks_passed", "checks_failed"):
            if isinstance(d.get(key), str):
                try:
                    d[key] = json.loads(d[key])
                except Exception:
                    pass
        res_list.append(d)

    return {"run": run_d, "results": res_list}


@router.post("/seed", dependencies=[Depends(require_admin_or_super_admin)])
async def seed_evals(pool=Depends(get_db)):
    """Seed initiële suites en cases (admin of super_admin)."""
    from app.services.eval_seed import seed_eval_cases

    async with pool.acquire() as conn:
        stats = await seed_eval_cases(conn)
    return {"ok": True, **stats}
