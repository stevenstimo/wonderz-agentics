from typing import Any, Dict


class DeploymentService:
    def __init__(self, tool_bridge: Any, dry_run: bool = True):
        self.tool_bridge = tool_bridge
        self.dry_run = dry_run

    async def deploy_job(self, conn: Any, job_id: str) -> Dict[str, Any]:
        """Deploy job artifacts. Returns a minimal summary for now."""
        mode = "dry_run" if self.dry_run else "live"
        return {
            "job_id": job_id,
            "mode": mode,
            "status": "queued" if self.dry_run else "deployed",
        }
