#!/usr/bin/env bash
# Start backend with live config (.env.vm: database + API keys) for direct testing.
# Usage: ./scripts/start_backend_live.sh   or   PORT=8091 ./scripts/start_backend_live.sh
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
set -a
[ -f .env.vm ] && source .env.vm
set +a
export DATABASE_URL="${DATABASE_URL:-postgresql://wonderz:wonderz123@localhost:5432/wonderz}"
PORT="${PORT:-8090}"
# If port in use, try next
while (echo >/dev/tcp/127.0.0.1/$PORT) 2>/dev/null; do
  echo "Port $PORT in use, trying $((PORT+1))..."
  PORT=$((PORT+1))
  [ "$PORT" -gt 8100 ] && { echo "No free port 8090-8100"; exit 1; }
done
echo "Starting backend on port $PORT (live config from .env.vm)"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
