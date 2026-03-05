#!/usr/bin/env bash
# Start backend for LIVE access (exe.dev): https://wonderz-agentic.exe.xyz:8090
# Runs in background with nohup so it stays up when you disconnect.
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
set -a
[ -f .env.vm ] && source .env.vm
set +a
export DATABASE_URL="${DATABASE_URL:-postgresql://wonderz:wonderz123@localhost:5432/wonderz}"

# Zichtbaar maken of de API-key geladen is (zonder de key te tonen)
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ANTHROPIC_API_KEY: geladen (${#ANTHROPIC_API_KEY} tekens)"
else
  echo "WAARSCHUWING: ANTHROPIC_API_KEY niet gezet in .env.vm - API-calls zullen falen"
fi

PORT=8090
# Stop ALL uvicorn backends so only this one (with .env.vm) runs
echo "Stopping any existing backend..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "uvicorn.*8090" 2>/dev/null || true
sleep 2
# Ensure port is free
for i in 1 2 3; do
  (echo >/dev/tcp/127.0.0.1/$PORT) 2>/dev/null && { pkill -9 -f "uvicorn" 2>/dev/null; sleep 1; } || break
done

LOG="$PWD/backend_live.log"
nohup uvicorn app.main:app --host 0.0.0.0 --port "$PORT" >> "$LOG" 2>&1 &
echo $! > "$PWD/.backend_live.pid"
sleep 1
if kill -0 $(cat "$PWD/.backend_live.pid") 2>/dev/null; then
  echo "✅ Backend gestart (PID $(cat "$PWD/.backend_live.pid"))"
  echo ""
  echo "Live URL:  https://wonderz-agentic.exe.xyz:8090"
  echo "Health:    https://wonderz-agentic.exe.xyz:8090/api/health"
  echo "API docs:  https://wonderz-agentic.exe.xyz:8090/docs"
  echo "Log:       tail -f $LOG"
else
  echo "❌ Start mislukt; zie $LOG"
  exit 1
fi
