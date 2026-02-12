"""
FastAPI Backend for Multi-Agent Development System
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import asyncio
import json
import sys
import os
import io
import uuid
import logging
from datetime import datetime
from pathlib import Path
import zipfile

# Add parent directory to path to import agents
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import ProductOwnerAgent, DeveloperAgent, ReviewerAgent, DevOpsAgent
from config import ANTHROPIC_API_KEY

app = FastAPI(title="Multi-Agentic Crew API")

# CORS middleware
cors_origins_env = os.getenv("CORS_ORIGINS")
cors_origins = (
    [o.strip() for o in cors_origins_env.split(",") if o.strip()]
    if cors_origins_env
    else [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://wonderz-agentics-4b7x95qr3-stevenstimos-projects.vercel.app",
        "https://frontend-rho-one-99.vercel.app",
    ]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active WebSocket connections
active_connections: list[WebSocket] = []

# Logging configuration
logger = logging.getLogger("multi_agent_backend")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# Root folder where generated projects are stored
GENERATED_ROOT = Path(os.getcwd()) / "generated_projects"
GENERATED_ROOT.mkdir(parents=True, exist_ok=True)


class ProjectRequest(BaseModel):
    project_idea: str
    language: Optional[str] = None
    platform: str = "docker"
    max_review_iterations: int = 2


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass


manager = ConnectionManager()


def save_generated_files(project_name: str, code_files: Dict[str, str]) -> str:
    """Save generated files into a unique project folder under GENERATED_ROOT.

    Preserves relative paths from keys in `code_files`.
    Returns absolute path to created project folder.
    """
    safe_name = "".join(c if (c.isalnum() or c in (' ', '-', '_')) else '_' for c in (project_name or "project"))
    safe_name = safe_name.strip().replace(' ', '_')[:50]
    unique = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    project_folder = GENERATED_ROOT / f"{safe_name}-{unique}"
    project_folder.mkdir(parents=True, exist_ok=True)

    for filename, content in code_files.items():
        target = project_folder / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, 'w', encoding='utf-8') as f:
            f.write(content)

    return str(project_folder.resolve())


async def send_progress(websocket: WebSocket, stage: str, status: str, data: Any = None):
    """Send progress update to frontend"""
    message = {
        "type": "progress",
        "stage": stage,
        "status": status,
        "data": data,
        "timestamp": asyncio.get_event_loop().time()
    }
    await manager.send_message(message, websocket)


async def run_workflow(project_idea: str, language: Optional[str], platform: str, 
                       max_iterations: int, websocket: WebSocket):
    """Run the full multi-agent workflow with WebSocket updates"""
    
    try:
        # Initialize agents
        await send_progress(websocket, "initialization", "in_progress", 
                          {"message": "Initializing agents..."})
        
        product_owner = ProductOwnerAgent(ANTHROPIC_API_KEY)
        developer = DeveloperAgent(ANTHROPIC_API_KEY)
        reviewer = ReviewerAgent(ANTHROPIC_API_KEY)
        devops = DevOpsAgent(ANTHROPIC_API_KEY)
        
        await send_progress(websocket, "initialization", "completed", 
                          {"message": "All agents initialized"})
        
        results = {
            "project_idea": project_idea,
            "stages": {},
            "total_tokens": 0
        }
        
        # Stage 1: Product Owner
        await send_progress(websocket, "requirements", "in_progress",
                          {"message": "Analyzing requirements..."})
        
        # Run blocking call in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        po_result = await loop.run_in_executor(None, product_owner.analyze, project_idea)
        results["stages"]["requirements"] = {
            "output": po_result["requirements"],
            "tokens": po_result["input_tokens"] + po_result["output_tokens"]
        }
        results["total_tokens"] += po_result["input_tokens"] + po_result["output_tokens"]
        
        await send_progress(websocket, "requirements", "completed",
                          {"output": po_result["requirements"][:500] + "...",
                           "tokens": po_result["input_tokens"] + po_result["output_tokens"]})
        
        # Stage 2: Developer
        await send_progress(websocket, "development", "in_progress",
                          {"message": "Writing code..."})
        
        # Run in thread pool
        dev_result = await loop.run_in_executor(None, developer.develop, po_result["requirements"], language)
        # Persist generated code files to a uniquely named project folder
        project_folder = save_generated_files(project_idea or "project", dev_result.get("code_files", {}))
        project_id = Path(project_folder).name
        logger.info("Generated project %s saved to %s", project_id, project_folder)

        results["stages"]["development"] = {
            "output": dev_result["full_output"],
            "code_files": dev_result["code_files"],
            "tokens": dev_result["input_tokens"] + dev_result["output_tokens"]
        }
        results["total_tokens"] += dev_result["input_tokens"] + dev_result["output_tokens"]

        await send_progress(websocket, "development", "completed",
                          {"files": list(dev_result["code_files"].keys()),
                           "tokens": dev_result["input_tokens"] + dev_result["output_tokens"]})

        # Stage 3: Reviewer
        await send_progress(websocket, "review", "in_progress",
                          {"message": "Reviewing code..."})

        # Run in thread pool
        review_result = await loop.run_in_executor(None, reviewer.review, dev_result["full_output"], po_result["requirements"])
        results["stages"]["review"] = {
            "output": review_result["review"],
            "status": review_result["status"],
            "tokens": review_result["input_tokens"] + review_result["output_tokens"]
        }
        results["total_tokens"] += review_result["input_tokens"] + review_result["output_tokens"]

        await send_progress(websocket, "review", "completed",
                          {"status": review_result["status"],
                           "preview": review_result["review"][:500] + "...",
                           "tokens": review_result["input_tokens"] + review_result["output_tokens"]})

        # Stage 4: DevOps
        await send_progress(websocket, "devops", "in_progress",
                          {"message": "Creating deployment configuration..."})

        # Run in thread pool
        def _create_deployment():
            return devops.create_deployment(
                dev_result["full_output"],
                po_result["requirements"],
                platform
            )
        devops_result = await loop.run_in_executor(None, _create_deployment)
        results["stages"]["devops"] = {
            "output": devops_result["full_output"],
            "deployment_files": devops_result["deployment_files"],
            "tokens": devops_result["input_tokens"] + devops_result["output_tokens"]
        }
        results["total_tokens"] += devops_result["input_tokens"] + devops_result["output_tokens"]

        await send_progress(websocket, "devops", "completed",
                          {"files": list(devops_result["deployment_files"].keys()),
                           "tokens": devops_result["input_tokens"] + devops_result["output_tokens"]})

        # Save deployment files into the same project folder
        try:
            for fname, content in devops_result.get("deployment_files", {}).items():
                target = Path(project_folder) / fname
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, 'w', encoding='utf-8') as tf:
                    tf.write(content)
            logger.info("Saved %d deployment files into project %s", len(devops_result.get("deployment_files", {})), project_id)
        except Exception:
            logger.exception("Failed saving deployment files for project %s", project_folder)

        # Write metadata.json for the project
        try:
            metadata = {
                "project_id": project_id,
                "project_idea": project_idea,
                "language": language,
                "platform": platform,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "total_tokens": results["total_tokens"],
                "files": [f for f in list(dev_result.get("code_files", {}).keys())] + list(devops_result.get("deployment_files", {}).keys())
            }
            metadata_path = Path(project_folder) / "metadata.json"
            with open(metadata_path, "w", encoding='utf-8') as mf:
                json.dump(metadata, mf, indent=2)
            logger.info("Wrote metadata.json for project %s", project_id)
        except Exception:
            logger.exception("Failed to write metadata for project %s", project_folder)

        # Final summary
        await send_progress(websocket, "complete", "success",
                          {"total_tokens": results["total_tokens"],
                           "results": results})

        return results
        
    except Exception as e:
        await send_progress(websocket, "error", "failed",
                          {"error": str(e)})
        raise


@app.get("/")
async def root():
    return {
        "message": "Multi-Agent Development System API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "api_key_configured": bool(ANTHROPIC_API_KEY)
    }


@app.get("/api/crew")
async def get_crew():
    """Get all crew members (stub endpoint)"""
    return []


@app.post("/api/crew")
async def create_crew(crew_data: dict):
    """Create crew member (stub endpoint)"""
    return {"message": "Crew management not yet implemented", "status": "stub"}


@app.put("/api/crew/{crew_id}")
async def update_crew(crew_id: str, crew_data: dict):
    """Update crew member (stub endpoint)"""
    return {"message": "Crew management not yet implemented", "status": "stub"}


@app.delete("/api/crew/{crew_id}")
async def delete_crew(crew_id: str):
    """Delete crew member (stub endpoint)"""
    return {"message": "Crew member deleted (stub)", "status": "stub"}


@app.get("/api/tasks")
async def get_tasks():
    """Get all tasks (stub endpoint)"""
    return []


@app.get("/api/improvements")
async def get_improvements():
    """Get improvement suggestions (stub endpoint)"""
    return []


@app.get("/products/unified")
async def get_unified_products():
    """Get unified product catalog (stub endpoint)"""
    return []


@app.get("/api/ceo/approvals")
async def get_approvals():
    """Get approval requests (stub endpoint)"""
    return []


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time workflow updates"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Wait for project request
            data = await websocket.receive_json()
            
            if data.get("type") == "start_workflow":
                project_data = data.get("data", {})
                
                # Run workflow
                await run_workflow(
                    project_idea=project_data.get("project_idea", ""),
                    language=project_data.get("language"),
                    platform=project_data.get("platform", "docker"),
                    max_iterations=project_data.get("max_review_iterations", 2),
                    websocket=websocket
                )
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        await send_progress(websocket, "error", "failed", {"error": str(e)})
        manager.disconnect(websocket)


@app.post("/api/workflow/start")
async def start_workflow(request: ProjectRequest):
    """
    REST endpoint to start workflow (alternative to WebSocket)
    Note: This will not provide real-time updates
    """
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="API key not configured")
    
    try:
        # Initialize agents
        product_owner = ProductOwnerAgent(ANTHROPIC_API_KEY)
        developer = DeveloperAgent(ANTHROPIC_API_KEY)
        reviewer = ReviewerAgent(ANTHROPIC_API_KEY)
        devops = DevOpsAgent(ANTHROPIC_API_KEY)
        
        # Run workflow (synchronous version)
        po_result = product_owner.analyze(request.project_idea)
        dev_result = developer.develop(po_result["requirements"], request.language)
        review_result = reviewer.review(dev_result["full_output"], po_result["requirements"])
        devops_result = devops.create_deployment(
            dev_result["full_output"],
            po_result["requirements"],
            request.platform
        )
        
        total_tokens = (
            po_result["input_tokens"] + po_result["output_tokens"] +
            dev_result["input_tokens"] + dev_result["output_tokens"] +
            review_result["input_tokens"] + review_result["output_tokens"] +
            devops_result["input_tokens"] + devops_result["output_tokens"]
        )
        
        return {
            "status": "success",
            "total_tokens": total_tokens,
            "results": {
                "requirements": po_result["requirements"],
                "code_files": dev_result["code_files"],
                "review_status": review_result["status"],
                "deployment_files": devops_result["deployment_files"]
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects")
async def list_projects():
    """Return list of all generated projects with their metadata (if available)."""
    projects: List[Dict[str, Any]] = []
    try:
        for p in sorted(GENERATED_ROOT.iterdir()):
            if not p.is_dir():
                continue
            meta_file = p / "metadata.json"
            if meta_file.exists():
                try:
                    with open(meta_file, 'r', encoding='utf-8') as mf:
                        projects.append(json.load(mf))
                except Exception:
                    logger.exception("Failed reading metadata for %s", p.name)
                    projects.append({"project_id": p.name})
            else:
                projects.append({"project_id": p.name})
    except Exception:
        logger.exception("Failed listing projects")
        raise HTTPException(status_code=500, detail="Failed listing projects")

    return {"projects": projects}


@app.get("/api/projects/{project_id}")
async def get_project_metadata(project_id: str):
    project_dir = GENERATED_ROOT / project_id
    if not project_dir.exists() or not project_dir.is_dir():
        raise HTTPException(status_code=404, detail="Project not found")
    meta_file = project_dir / "metadata.json"
    if not meta_file.exists():
        raise HTTPException(status_code=404, detail="Metadata not found for project")
    try:
        with open(meta_file, 'r', encoding='utf-8') as mf:
            return json.load(mf)
    except Exception:
        logger.exception("Failed reading metadata for %s", project_id)
        raise HTTPException(status_code=500, detail="Failed reading metadata")


@app.get("/api/projects/{project_id}/download")
async def download_project(project_id: str):
    project_dir = GENERATED_ROOT / project_id
    if not project_dir.exists() or not project_dir.is_dir():
        raise HTTPException(status_code=404, detail="Project not found")

    buf = io.BytesIO()
    try:
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file in project_dir.rglob('*'):
                if file.is_file():
                    zf.write(file, arcname=str(file.relative_to(project_dir)))
        buf.seek(0)
        headers = {"Content-Disposition": f"attachment; filename={project_id}.zip"}
        return StreamingResponse(buf, media_type="application/zip", headers=headers)
    except Exception:
        logger.exception("Failed creating zip for project %s", project_id)
        raise HTTPException(status_code=500, detail="Failed creating zip archive")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
