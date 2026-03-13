"""
NEXUS pipeline integratietests — echte DB, gemockte LLM.
Setup/teardown gebruikt dedicated test jobs; geen afhankelijkheid van bestaande data.
"""

import json
import os
import uuid
from unittest.mock import AsyncMock, patch

import asyncpg
import pytest
import pytest_asyncio

from app.orchestration.handoff_context import HandoffContext
from app.orchestration.nexus_pipeline import NEXUSPipeline


@pytest_asyncio.fixture
async def db_pool():
    """
    Echte asyncpg pool voor integratietests, per-test (niet de globale app pool).
    Vermijdt event-loop issues: elke test krijgt een pool in zijn eigen loop.
    Skip als DB niet bereikbaar.
    """
    dsn = os.getenv("DATABASE_URL", "postgresql://wonderz:wonderz123@localhost:5432/wonderz")
    try:
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2, command_timeout=10)
    except Exception:
        pytest.skip("Database not available")
    yield pool
    await pool.close()


@pytest_asyncio.fixture
async def test_job(db_pool):
    """
    Maakt een test job aan en ruimt hem daarna op.
    CASCADE verwijdert bijbehorende job_steps bij DELETE jobs.

    assumption-based: jobs.user_id heeft in het huidige schema/migraties
    GEEN foreign key naar users(id) (geverifieerd: create_jobs_table + add_user_id
    voegen alleen index toe, geen REFERENCES). Daarom gebruiken we een willekeurige
    UUID voor user_id. Als er later wel een FK wordt toegevoegd, moet deze fixture
    worden aangepast: gebruik dan 00000000-0000-0000-0000-000000000001 als test-user
    en voeg INSERT INTO users (id, email) toe in setup met dezelfde teardown.
    """
    job_id = uuid.uuid4()
    user_id = uuid.uuid4()  # no FK to users; random UUID is valid
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO jobs (id, user_id, job_post, status, source_platform, context, token_budget, intake_source)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
            """,
            job_id,
            user_id,
            "Test job for NEXUS integration",
            "RUNNING",
            "browser",
            "{}",
            50000,
            "browser",
        )
    yield str(job_id)
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM jobs WHERE id = $1", job_id)


@pytest_asyncio.fixture
async def test_job_with_steps(db_pool):
    """Test job met 2 job_steps; teardown verwijdert job (CASCADE verwijdert steps)."""
    job_id = uuid.uuid4()
    user_id = uuid.uuid4()
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO jobs (id, user_id, job_post, status, source_platform, context, token_budget, intake_source)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
            """,
            job_id,
            user_id,
            "Test job with steps",
            "RUNNING",
            "browser",
            "{}",
            50000,
            "browser",
        )
        for idx, (step_name, agent_role) in enumerate([("step_a", "copywriter"), ("step_b", "reviewer")]):
            await conn.execute(
                """
                INSERT INTO job_steps (job_id, step_index, step_name, agent_role, status, input_payload)
                VALUES ($1, $2, $3, $4, 'pending', '{}'::jsonb)
                """,
                job_id,
                idx,
                step_name,
                agent_role,
            )
    yield str(job_id)
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM jobs WHERE id = $1", job_id)


@pytest.mark.asyncio
async def test_phase2_loads_job_steps_from_db(test_job_with_steps, db_pool):
    """phase_2_planning laadt execution_plan uit DB met correcte step_id's."""
    job_id = test_job_with_steps
    ctx = HandoffContext(job_id=job_id, user_id="u1", platform="web", token_budget=50000)
    pipeline = NEXUSPipeline()
    pipeline._pool = db_pool
    await pipeline.phase_2_planning(ctx)
    assert len(ctx.execution_plan) == 2
    step_ids = [s.get("step_id") for s in ctx.execution_plan]
    assert all(sid for sid in step_ids)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id FROM job_steps WHERE job_id = $1 ORDER BY step_index",
            uuid.UUID(job_id),
        )
    db_ids = [str(r["id"]) for r in rows]
    assert set(step_ids) == set(db_ids)


@pytest.mark.asyncio
async def test_execute_step_writes_output_to_db(test_job, db_pool):
    """_execute_step schrijft status, output, timing_ms en tokens_used naar job_steps."""
    job_id = test_job
    step_id = uuid.uuid4()
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO job_steps (id, job_id, step_index, step_name, agent_role, status, input_payload)
            VALUES ($1, $2, 0, 'copywriter', 'copywriter', 'pending', '{}'::jsonb)
            """,
            step_id,
            uuid.UUID(job_id),
        )
    step = {
        "step_id": str(step_id),
        "step_index": 0,
        "step_name": "copywriter",
        "agent_role": "copywriter",
        "agent_id": None,
        "input_payload": {},
        "status": "pending",
    }
    ctx = HandoffContext(job_id=job_id, user_id="u1", platform="web", token_budget=50000)
    ctx.strategic_brief = {"objective": "Write a test article", "platform": "web"}
    ctx.execution_plan = [step]
    pipeline = NEXUSPipeline()
    pipeline._pool = db_pool
    mock_output = {"status": "completed", "content": "Test content", "agent_role": "copywriter"}
    with patch("app.services.job_pipeline._run_step_agent_with_timeout", new_callable=AsyncMock) as m:
        m.return_value = (mock_output, 100)
        await pipeline._execute_step(ctx, step)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT status, output, timing_ms, tokens_used FROM job_steps WHERE id = $1", step_id)
    assert row is not None
    assert row["status"] == "completed"
    out = row["output"]
    if isinstance(out, str):
        out = json.loads(out)
    assert out.get("content") == "Test content"
    assert row["timing_ms"] >= 0
    assert row["tokens_used"] >= 0


@pytest.mark.asyncio
async def test_phase6_sets_job_ready(test_job, db_pool):
    """phase_6_approval_gate zet jobs.status op JOB_READY en schrijft final_content in context."""
    job_id = test_job
    ctx = HandoffContext(job_id=job_id, user_id="u1", platform="web", token_budget=50000)
    ctx.execution_plan = [{"step_name": "copywriter", "step_index": 0}]
    ctx.step_outputs["copywriter"] = "Final article content"
    pipeline = NEXUSPipeline()
    pipeline._pool = db_pool
    await pipeline.phase_6_approval_gate(ctx)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT status, context FROM jobs WHERE id = $1", uuid.UUID(job_id))
    assert row is not None
    assert row["status"] == "JOB_READY"
    ctx_json = row["context"]
    if isinstance(ctx_json, str):
        ctx_json = json.loads(ctx_json)
    assert "final_content" in ctx_json


@pytest.mark.asyncio
async def test_full_pipeline_completes_without_error(test_job, db_pool):
    """Volledige pipeline.run() eindigt in JOB_READY of FAILED (smoke, LLM gemockt)."""
    job_id = test_job
    step_id = uuid.uuid4()
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO job_steps (id, job_id, step_index, step_name, agent_role, status, input_payload)
            VALUES ($1, $2, 0, 'copywriter', 'copywriter', 'pending', '{}'::jsonb)
            """,
            step_id,
            uuid.UUID(job_id),
        )
    with patch("app.services.job_pipeline._run_step_agent_with_timeout", new_callable=AsyncMock) as m:
        m.return_value = ({"status": "completed", "content": "Done", "agent_role": "copywriter"}, 50)
        pipeline = NEXUSPipeline()
        ctx = await pipeline.run(
            job_id,
            "u1",
            "browser",
            "Test post",
            50000,
            pool=db_pool,
        )
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT status FROM jobs WHERE id = $1", uuid.UUID(job_id))
    assert row is not None
    assert row["status"] in ("JOB_READY", "FAILED")
