import os
import sys
import asyncio
import json

# Ensure repo root on path so we can import app package
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from workers.celery_app import celery

@celery.task(bind=True)
def run_job(self, job_id: str, store_id: str = None, payload: dict = None):
    """Celery task entrypoint to run a workflow for a job id."""
    payload = payload or {}
    # create an async agent runner that imports agent modules from agents/<name> and calls their 'run' coroutine
    async def real_agent_runner(agent_name: str, input_payload: dict):
        try:
            mod = __import__(f"agents.{agent_name}", fromlist=["run"])  # e.g. agents.copy_agent
            run_fn = getattr(mod, "run")

            # Build ToolsProxy according to permissions
            try:
                from agents.agent_permissions import AGENT_ALLOWED_TOOLS
                allowed = AGENT_ALLOWED_TOOLS.get(agent_name, [])
            except Exception:
                allowed = []

            from agents.tools_proxy import ToolsProxy
            tools = ToolsProxy(allowed)

            payload_with_tools = {"job_id": job_id, "store_id": store_id, "context": input_payload.get("context", {}), "tools": tools, **(input_payload or {})}

            if asyncio.iscoroutinefunction(run_fn):
                return await run_fn(payload_with_tools)
            else:
                # sync callable
                return run_fn(payload_with_tools)
        except ModuleNotFoundError:
            # fallback: return a stub response
            return {"summary": f"agent module not found: {agent_name}"}

    manager = OperationsManager(real_agent_runner)

    # OperationsManager.run_workflow is async; run it in event loop
    try:
        asyncio.run(manager.run_workflow(job_id, store_id, payload))
    except Exception as e:
        # Best-effort logging
        print(f"Error running job {job_id}: {e}")
        raise
