import asyncio
import pytest

from app.orchestration.manager import OperationsManager, SharedContext


@pytest.mark.asyncio
async def test_review_retry_and_approval_flow():
    calls = {"write_job_step": [], "append_artifact": [], "update_job_status": []}

    async def fake_connect():
        return object()

    async def fake_write_job_step(conn, job_id, step_name, agent, status, log=None):
        calls["write_job_step"].append((job_id, step_name, agent, status, log))

    async def fake_append_artifact(conn, job_id, name, artifact_type, content=None, content_text=None, storage_path=None):
        calls["append_artifact"].append((job_id, name, artifact_type, content_text))

    async def fake_update_job_status(conn, job_id, status):
        calls["update_job_status"].append((job_id, status))

    # Agent runner that returns: copy -> draft; reviewer returns NEEDS_CHANGES first, then APPROVED
    reviewer_calls = {"count": 0}

    async def agent_runner(agent_name: str, payload: dict):
        if agent_name == "copy_agent":
            return {"summary": "draft", "data": {"draft_text": "short draft text"}}
        if agent_name == "reviewer_agent":
            reviewer_calls["count"] += 1
            if reviewer_calls["count"] == 1:
                return {"summary": "too short", "status": "NEEDS_CHANGES"}
            return {"summary": "ok", "status": "APPROVED"}
        return {"summary": "noop"}

    mgr = OperationsManager(agent_runner)
    # Monkeypatch DB methods
    mgr._connect = fake_connect
    mgr.write_job_step = fake_write_job_step
    mgr.append_artifact = fake_append_artifact
    mgr.update_job_status = fake_update_job_status

    # Run workflow
    await mgr.run_workflow("job-1", "store-1", {"context": {"product": {"title": "Hat"}}}, max_steps=10)

    # Assertions: there should be multiple write_job_step calls, including retries
    assert any(s[1] == "copy_agent" for s in calls["write_job_step"])  # copy ran
    assert any(s[1] == "reviewer_agent" for s in calls["write_job_step"])  # review ran
    # reviewer should have been called twice (one NEEDS_CHANGES then APPROVED)
    assert reviewer_calls["count"] == 2
    # Job status was set to running then completed
    statuses = [s[1] for s in calls["update_job_status"]]
    assert "running" in statuses
    assert "completed" in statuses
