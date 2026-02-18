"""Codex Web Interface — lightweight wrapper around the codex CLI."""
import asyncio
import json
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Codex Web")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WORK_DIR = os.getenv("CODEX_WORK_DIR", "/home/exedev/wonderz-agentics")


class CodexRequest(BaseModel):
    prompt: str
    model: str = "o4-mini"
    approval_mode: str = "suggest"  # suggest | auto-edit | full-auto


# Store running sessions
_sessions: dict[str, dict] = {}

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Codex Console</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: 'SF Mono','Fira Code',monospace; background:#0d1117; color:#c9d1d9; height:100vh; display:flex; flex-direction:column; }
  .header { padding:16px 24px; background:#161b22; border-bottom:1px solid #30363d; display:flex; align-items:center; gap:16px; }
  .header h1 { font-size:18px; color:#58a6ff; }
  .header select, .header input { background:#0d1117; color:#c9d1d9; border:1px solid #30363d; border-radius:6px; padding:6px 12px; font-size:13px; }
  .header select:focus, .header input:focus { outline:none; border-color:#58a6ff; }
  .output { flex:1; overflow-y:auto; padding:16px 24px; font-size:13px; line-height:1.6; white-space:pre-wrap; word-break:break-word; }
  .output .system { color:#8b949e; }
  .output .user { color:#58a6ff; }
  .output .codex { color:#7ee787; }
  .output .error { color:#f85149; }
  .output .separator { border-top:1px solid #30363d; margin:12px 0; }
  .input-area { padding:16px 24px; background:#161b22; border-top:1px solid #30363d; display:flex; gap:12px; }
  .input-area textarea { flex:1; background:#0d1117; color:#c9d1d9; border:1px solid #30363d; border-radius:8px; padding:12px; font-family:inherit; font-size:14px; resize:none; min-height:60px; }
  .input-area textarea:focus { outline:none; border-color:#58a6ff; }
  .input-area button { background:#238636; color:#fff; border:none; border-radius:8px; padding:12px 24px; font-size:14px; font-weight:600; cursor:pointer; align-self:flex-end; }
  .input-area button:hover { background:#2ea043; }
  .input-area button:disabled { opacity:0.5; cursor:not-allowed; }
  .status { font-size:12px; padding:4px 10px; border-radius:12px; }
  .status.connected { background:#238636; color:#fff; }
  .status.disconnected { background:#f85149; color:#fff; }
  .status.running { background:#d29922; color:#fff; }
</style>
</head>
<body>
<div class="header">
  <h1>\u2728 Codex Console</h1>
  <select id="model">
    <option value="o4-mini">o4-mini</option>
    <option value="gpt-4.1">gpt-4.1</option>
    <option value="o3">o3</option>
    <option value="gpt-4.1-mini">gpt-4.1-mini</option>
  </select>
  <select id="mode">
    <option value="suggest">Suggest</option>
    <option value="auto-edit">Auto-edit</option>
    <option value="full-auto">Full-auto</option>
  </select>
  <span id="status" class="status disconnected">Disconnected</span>
</div>
<div class="output" id="output"></div>
<div class="input-area">
  <textarea id="prompt" placeholder="Ask Codex anything... (Enter to send, Shift+Enter for newline)" rows="2"></textarea>
  <button id="send" onclick="sendPrompt()">Run</button>
</div>
<script>
const output = document.getElementById('output');
const promptEl = document.getElementById('prompt');
const sendBtn = document.getElementById('send');
const statusEl = document.getElementById('status');
let ws = null;
let running = false;

function setStatus(s) {
  statusEl.className = 'status ' + s;
  statusEl.textContent = s.charAt(0).toUpperCase() + s.slice(1);
}

function append(cls, text) {
  const div = document.createElement('div');
  div.className = cls;
  div.textContent = text;
  output.appendChild(div);
  output.scrollTop = output.scrollHeight;
}

function addSeparator() {
  const div = document.createElement('div');
  div.className = 'separator';
  output.appendChild(div);
}

function connect() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws/codex`);
  ws.onopen = () => setStatus('connected');
  ws.onclose = () => { setStatus('disconnected'); setTimeout(connect, 3000); };
  ws.onerror = () => setStatus('disconnected');
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'output') {
      append('codex', msg.text);
    } else if (msg.type === 'done') {
      append('system', `\u2713 Done (exit code: ${msg.exit_code})`);
      addSeparator();
      running = false;
      sendBtn.disabled = false;
      promptEl.focus();
    } else if (msg.type === 'error') {
      append('error', msg.text);
      running = false;
      sendBtn.disabled = false;
    } else if (msg.type === 'started') {
      setStatus('running');
    }
  };
}

function sendPrompt() {
  const text = promptEl.value.trim();
  if (!text || !ws || running) return;
  running = true;
  sendBtn.disabled = true;
  addSeparator();
  append('user', '> ' + text);
  ws.send(JSON.stringify({
    prompt: text,
    model: document.getElementById('model').value,
    approval_mode: document.getElementById('mode').value,
  }));
  promptEl.value = '';
}

promptEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendPrompt(); }
});

connect();
append('system', 'Codex Console ready. Type a prompt and press Run.');
append('system', 'Working directory: ' + '""" + WORK_DIR + """' + '');
</script>
</body>
</html>
"""


@app.get("/")
async def index():
    return HTMLResponse(HTML)


@app.websocket("/ws/codex")
async def codex_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            prompt = msg.get("prompt", "").strip()
            model = msg.get("model", "o4-mini")
            approval_mode = msg.get("approval_mode", "suggest")

            if not prompt:
                await websocket.send_json({"type": "error", "text": "Empty prompt"})
                continue

            await websocket.send_json({"type": "started"})

            # Run codex CLI as subprocess
            cmd = [
                "codex",
                "--model", model,
                "--approval-mode", approval_mode,
                "--quiet",
                prompt,
            ]

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=WORK_DIR,
                    env={**os.environ, "TERM": "dumb", "NO_COLOR": "1"},
                )

                # Stream output line by line
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    text = line.decode("utf-8", errors="replace").rstrip()
                    if text:
                        await websocket.send_json({"type": "output", "text": text})

                exit_code = await proc.wait()
                await websocket.send_json({"type": "done", "exit_code": exit_code})

            except Exception as e:
                await websocket.send_json({"type": "error", "text": str(e)})

    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7682)
