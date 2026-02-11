"""
FastAPI Backend for Multi-Agent Development System
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import asyncio
import json
import sys
import os

# Add parent directory to path to import agents
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import ProductOwnerAgent, DeveloperAgent, ReviewerAgent, DevOpsAgent
from config import ANTHROPIC_API_KEY

app = FastAPI(title="Multi-Agent Dev System API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active WebSocket connections
active_connections: list[WebSocket] = []


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
        
        po_result = product_owner.analyze(project_idea)
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
        
        dev_result = developer.develop(po_result["requirements"], language)
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
        
        review_result = reviewer.review(dev_result["full_output"], po_result["requirements"])
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
        
        devops_result = devops.create_deployment(
            dev_result["full_output"],
            po_result["requirements"],
            platform
        )
        results["stages"]["devops"] = {
            "output": devops_result["full_output"],
            "deployment_files": devops_result["deployment_files"],
            "tokens": devops_result["input_tokens"] + devops_result["output_tokens"]
        }
        results["total_tokens"] += devops_result["input_tokens"] + devops_result["output_tokens"]
        
        await send_progress(websocket, "devops", "completed",
                          {"files": list(devops_result["deployment_files"].keys()),
                           "tokens": devops_result["input_tokens"] + devops_result["output_tokens"]})
        
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
