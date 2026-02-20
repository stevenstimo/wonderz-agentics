#!/usr/bin/env python3
"""Codex Web Interface - Backend server"""
import os
import sys
import json
import asyncio
import uuid
import hashlib
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(title="Codex Web Interface")

PROJECT_DIR = "/home/exedev/wonderz-agentics"
KEYS_FILE = "/home/exedev/.config/wonderz-keys.json"
BASHRC = os.path.expanduser("~/.bashrc")

# Store running tasks
running_tasks = {}

THREADS_FILE = "/home/exedev/.config/wonderz-threads.json"


def load_threads():
    if os.path.exists(THREADS_FILE):
        with open(THREADS_FILE, "r") as f:
            return json.load(f)
    return []


def save_threads(threads):
    os.makedirs(os.path.dirname(THREADS_FILE), exist_ok=True)
    with open(THREADS_FILE, "w") as f:
        json.dump(threads, f, indent=2)


def add_thread_message(thread_id, role, content, model=None):
    threads = load_threads()
    thread = None
    for t in threads:
        if t["id"] == thread_id:
            thread = t
            break
    if not thread:
        thread = {
            "id": thread_id,
            "title": content[:60] if role == "user" else "New thread",
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat(),
            "model": model or "gpt-5.2-codex",
            "messages": []
        }
        threads.insert(0, thread)
    thread["updated"] = datetime.now().isoformat()
    thread["messages"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    })
    # Keep max 50 threads
    threads = threads[:50]
    save_threads(threads)
    return thread


def get_openai_key():
    """Get OpenAI key from stored keys or environment."""
    keys = load_keys()
    for k in keys:
        if k["name"] == "OPENAI_API_KEY" and k.get("value"):
            return k["value"]
    return os.environ.get("OPENAI_API_KEY", "")


def get_anthropic_key():
    """Get Anthropic key from stored keys or environment."""
    keys = load_keys()
    for k in keys:
        if k["name"] == "ANTHROPIC_API_KEY" and k.get("value"):
            return k["value"]
    return os.environ.get("ANTHROPIC_API_KEY", "")


def load_keys():
    """Load keys from JSON file."""
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, "r") as f:
            return json.load(f)
    return []


def save_keys(keys):
    """Save keys to JSON file with restricted permissions."""
    os.makedirs(os.path.dirname(KEYS_FILE), exist_ok=True)
    with open(KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=2)
    os.chmod(KEYS_FILE, 0o600)


def mask_key(value):
    """Mask a key: show first 3 and last 4 chars."""
    if not value or len(value) < 10:
        return "***"
    return value[:3] + "..." + value[-4:]


def update_bashrc(name, value):
    """Update or add an export line in bashrc."""
    lines = []
    found = False
    if os.path.exists(BASHRC):
        with open(BASHRC, "r") as f:
            lines = f.readlines()
    
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"export {name}="):
            new_lines.append(f"export {name}={value}\n")
            found = True
        else:
            new_lines.append(line)
    
    if not found:
        new_lines.append(f"export {name}={value}\n")
    
    with open(BASHRC, "w") as f:
        f.writelines(new_lines)


def update_systemd_env(name, value):
    """Update environment variable in systemd service files."""
    import subprocess
    services = [
        "/etc/systemd/system/wonderz-backend.service",
        "/etc/systemd/system/wonderz-codex-web.service"
    ]
    for svc in services:
        if os.path.exists(svc):
            try:
                subprocess.run(
                    ["sudo", "sed", "-i",
                     f"s|Environment={name}=.*|Environment={name}={value}|",
                     svc],
                    capture_output=True, timeout=5
                )
            except:
                pass
    try:
        subprocess.run(["sudo", "systemctl", "daemon-reload"], capture_output=True, timeout=5)
    except:
        pass


# --- Upload endpoint ---

UPLOAD_DIR = os.path.join(PROJECT_DIR, ".codex-uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Upload .md files and images. Saves to project dir so Codex can read them."""
    results = []
    for f in files:
        ext = Path(f.filename).suffix.lower()
        if ext not in (".md", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf"):
            results.append({"name": f.filename, "error": f"Unsupported file type: {ext}"})
            continue
        safe_name = f"{uuid.uuid4().hex[:8]}_{Path(f.filename).name}"
        dest = os.path.join(UPLOAD_DIR, safe_name)
        content = await f.read()
        with open(dest, "wb") as out:
            out.write(content)

        is_text = ext in (".md", ".txt")
        # Relative path from project root for Codex to access
        rel_path = os.path.relpath(dest, PROJECT_DIR)

        results.append({
            "name": f.filename,
            "path": dest,
            "rel_path": rel_path,
            "size": len(content),
            "type": f.content_type,
            "is_text": is_text,
        })
    return {"files": results}


# --- API Keys endpoints ---

class KeyCreate(BaseModel):
    name: str  # e.g. OPENAI_API_KEY
    label: str  # e.g. "Wonderz-Agentic"
    value: str


@app.get("/api/keys")
async def list_keys():
    """List all keys (masked)."""
    keys = load_keys()
    return [
        {
            "id": k["id"],
            "name": k["name"],
            "label": k.get("label", k["name"]),
            "masked": mask_key(k.get("value", "")),
            "created": k.get("created", ""),
            "status": "Active" if k.get("value") else "Empty",
        }
        for k in keys
    ]


@app.post("/api/keys")
async def create_key(req: KeyCreate):
    """Create or update a key."""
    keys = load_keys()
    
    # Check if key with this name exists
    existing = None
    for k in keys:
        if k["name"] == req.name:
            existing = k
            break
    
    if existing:
        existing["value"] = req.value
        existing["label"] = req.label
        existing["updated"] = datetime.now().isoformat()
    else:
        keys.append({
            "id": str(uuid.uuid4())[:8],
            "name": req.name,
            "label": req.label,
            "value": req.value,
            "created": datetime.now().strftime("%d %b %Y"),
            "updated": datetime.now().isoformat(),
        })
    
    save_keys(keys)
    
    # Also update bashrc and systemd
    update_bashrc(req.name, req.value)
    update_systemd_env(req.name, req.value)
    
    # Restart backend to pick up new keys
    import subprocess
    try:
        subprocess.run(["sudo", "systemctl", "restart", "wonderz-backend"], capture_output=True, timeout=10)
    except:
        pass
    
    return {"status": "saved", "masked": mask_key(req.value)}


@app.delete("/api/keys/{key_id}")
async def delete_key(key_id: str):
    """Delete a key."""
    keys = load_keys()
    key_to_delete = None
    for k in keys:
        if k["id"] == key_id:
            key_to_delete = k
            break
    
    if not key_to_delete:
        raise HTTPException(status_code=404, detail="Key not found")
    
    keys = [k for k in keys if k["id"] != key_id]
    save_keys(keys)
    
    return {"status": "deleted"}


# --- Thread endpoints ---

@app.get("/api/threads")
async def list_threads():
    threads = load_threads()
    return [
        {
            "id": t["id"],
            "title": t["title"],
            "created": t["created"],
            "updated": t["updated"],
            "model": t.get("model", ""),
            "message_count": len(t.get("messages", [])),
        }
        for t in threads
    ]


@app.get("/api/threads/{thread_id}")
async def get_thread(thread_id: str):
    threads = load_threads()
    for t in threads:
        if t["id"] == thread_id:
            return t
    raise HTTPException(status_code=404, detail="Thread not found")


@app.delete("/api/threads/{thread_id}")
async def delete_thread(thread_id: str):
    threads = load_threads()
    threads = [t for t in threads if t["id"] != thread_id]
    save_threads(threads)
    return {"status": "deleted"}


# --- Git status endpoint ---

@app.get("/api/git-status")
async def git_status():
    """Return pending changes and unpushed commits."""
    import subprocess
    try:
        # Uncommitted changes
        r_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_DIR, capture_output=True, text=True, timeout=5
        )
        changed_files = [l for l in r_status.stdout.strip().split("\n") if l.strip()]

        # Current branch
        r_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=PROJECT_DIR, capture_output=True, text=True, timeout=5
        )
        branch = r_branch.stdout.strip()

        # Unpushed commits
        r_unpushed = subprocess.run(
            ["git", "log", f"origin/{branch}..HEAD", "--oneline"],
            cwd=PROJECT_DIR, capture_output=True, text=True, timeout=5
        )
        unpushed = [l for l in r_unpushed.stdout.strip().split("\n") if l.strip()]

        return {
            "branch": branch,
            "changed_files": len(changed_files),
            "unpushed_commits": len(unpushed),
            "files": changed_files[:20],
            "commits": unpushed[:10],
        }
    except Exception as e:
        return {"branch": "unknown", "changed_files": 0, "unpushed_commits": 0, "error": str(e)}


# --- Deploy endpoint ---

class DeployRequest(BaseModel):
    message: str = "deploy from codex console"


@app.post("/api/deploy")
async def deploy(req: DeployRequest):
    """Git commit and push to GitHub."""
    import subprocess
    results = []
    try:
        r1 = subprocess.run(["git", "add", "-A"], cwd=PROJECT_DIR, capture_output=True, text=True, timeout=10)
        results.append(f"git add: {r1.returncode}")
        r2 = subprocess.run(["git", "commit", "-m", req.message], cwd=PROJECT_DIR, capture_output=True, text=True, timeout=10)
        results.append(f"git commit: {r2.stdout.strip() or r2.stderr.strip()}")
        r3 = subprocess.run(["git", "push", "origin", "main"], cwd=PROJECT_DIR, capture_output=True, text=True, timeout=30)
        results.append(f"git push: {r3.returncode} {r3.stderr.strip()}")
        return {"status": "ok", "details": results}
    except Exception as e:
        return {"status": "error", "details": str(e)}


# --- Static files ---

@app.get("/")
async def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/settings")
async def settings_page():
    return FileResponse(Path(__file__).parent / "static" / "settings.html")


@app.get("/api-docs")
async def api_docs_page():
    return FileResponse(Path(__file__).parent / "static" / "api.html")


@app.get("/api/proxy-openapi")
async def proxy_openapi():
    """Proxy the backend OpenAPI spec to avoid CORS issues."""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8090/openapi.json", timeout=5)
            return r.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# --- WebSocket for Codex ---

@app.websocket("/ws/codex")
async def codex_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            prompt = data.get("prompt", "")
            model = data.get("model", "gpt-5.2-codex")

            if not prompt:
                await websocket.send_json({"type": "error", "data": "Geen prompt opgegeven"})
                continue

            thread_id = data.get("thread_id") or str(uuid.uuid4())[:12]
            task_id = str(uuid.uuid4())[:8]
            
            # Save user message to thread
            add_thread_message(thread_id, "user", prompt, model)
            
            await websocket.send_json({"type": "start", "task_id": task_id, "thread_id": thread_id, "prompt": prompt})

            report_instruction = """\n\n---\nIMPORTANT: When you are done, ALWAYS end with a structured report in Dutch. Use this exact markdown format:

[1-2 zinnen samenvatting van wat je hebt gedaan.]

**Wat ik vond**

1. [Eerste bevinding met `code` inline waar nodig]
2. [Tweede bevinding]
   - [Sub-detail]
   - [Sub-detail met `code_referentie`]
3. [Derde bevinding]

**Wat ik heb aangepast**

1. [Eerste aanpassing]:
   - `bestandsnaam.py` [wat je deed]
   - [Detail met `code` referenties]
2. [Tweede aanpassing]:
   - `bestandsnaam.jsx` [wat je deed]

**Commit + push**

- Commit: `hash`
- Branch: `branch-naam`
- Gepusht naar GitHub.

**Resultaat**

- [Wat werkt nu]
- [Verificatie]

[Optioneel: suggestie voor vervolgactie]

---FILES_CHANGED---
[lijst van gewijzigde bestanden, één per regel, format: bestandsnaam +regels -regels]

Rules:
- Write in Dutch
- Use inline `code` for file names, variables, URLs, commands
- Use numbered lists with sub-bullets for detail
- Be specific: mention exact file names, line changes, commit hashes
- The FILES_CHANGED section must list every file you modified with +/- line counts"""

            full_prompt = prompt + report_instruction

            cmd = [
                "codex", "exec",
                "--full-auto",
                "-m", model,
                "-C", PROJECT_DIR,
                "--json",
                full_prompt
            ]

            env = os.environ.copy()
            env["OPENAI_API_KEY"] = get_openai_key()

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=PROJECT_DIR
                )
                running_tasks[task_id] = process
                collected_output = []  # Collect agent text for thread history

                async def read_stream(stream, stream_type):
                    text_buffer = []  # Buffer non-JSON lines
                    buffer_timer = None

                    async def flush_buffer():
                        if text_buffer:
                            combined = "\n".join(text_buffer)
                            text_buffer.clear()
                            await websocket.send_json({"type": "output", "task_id": task_id, "stream": stream_type, "data": combined})

                    while True:
                        line = await stream.readline()
                        if not line:
                            await flush_buffer()
                            break
                        text = line.decode("utf-8", errors="replace").rstrip()
                        if not text:
                            text_buffer.append("")  # Preserve blank lines
                            continue
                        try:
                            event = json.loads(text)
                            # Flush any buffered text before sending event
                            await flush_buffer()
                            await websocket.send_json({"type": "event", "task_id": task_id, "data": event})
                            # Collect agent message text for thread history
                            if event.get("type") == "item.completed" and event.get("item", {}).get("text"):
                                collected_output.append(event["item"]["text"])
                            elif event.get("type") == "message" and event.get("message", {}).get("role") == "assistant":
                                for b in event.get("message", {}).get("content", []):
                                    if b.get("type") == "text" and b.get("text"):
                                        collected_output.append(b["text"])
                        except json.JSONDecodeError:
                            text_buffer.append(text)

                await asyncio.gather(
                    read_stream(process.stdout, "stdout"),
                    read_stream(process.stderr, "stderr")
                )

                return_code = await process.wait()
                running_tasks.pop(task_id, None)
                
                # Save full assistant response to thread
                response_text = "\n\n".join(collected_output) if collected_output else f"Task completed (code: {return_code})"
                add_thread_message(thread_id, "assistant", response_text, model)
                
                await websocket.send_json({"type": "done", "task_id": task_id, "thread_id": thread_id, "return_code": return_code})

            except Exception as e:
                running_tasks.pop(task_id, None)
                await websocket.send_json({"type": "error", "task_id": task_id, "data": str(e)})

    except WebSocketDisconnect:
        for tid, proc in list(running_tasks.items()):
            try:
                proc.kill()
            except:
                pass
        running_tasks.clear()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
