# Debug instrumentation: write NDJSON to session log (no secrets).
import os
import json
import hashlib
import time
from pathlib import Path

# Project root (parent of app/); fallback to absolute if needed
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LOG_PATH = str(_PROJECT_ROOT / "debug-5f342c.log")
_SESSION = "5f342c"


def _key_fingerprint(key: str) -> dict:
    if not key:
        return {"key_len": 0, "key_hash8": ""}
    h = hashlib.sha256(key.encode()).hexdigest()[:8]
    return {"key_len": len(key), "key_hash8": h}


def log_anthropic_key(location: str, message: str, hypothesis_id: str, run_id: str = "run1"):
    key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    data = _key_fingerprint(key)
    entry = {
        "sessionId": _SESSION,
        "id": f"log_{int(time.time()*1000)}",
        "timestamp": int(time.time() * 1000),
        "location": location,
        "message": message,
        "data": data,
        "runId": run_id,
        "hypothesisId": hypothesis_id,
    }
    try:
        os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
        with open(_LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        import sys
        print(f"[debug_log] write failed: {e}", file=sys.stderr)
