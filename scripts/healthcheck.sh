#!/bin/bash
# Healthcheck script voor Claude agentic platform

set -e

cd "$(dirname "$0")/../.."

# Check Python venv
if [ ! -d ".venv" ]; then
  echo "[ERROR] Geen .venv gevonden. Maak een venv aan met: python -m venv .venv"
  exit 1
fi

source .venv/bin/activate

# Check uvicorn
if ! command -v uvicorn >/dev/null 2>&1; then
  echo "[INFO] Installeer uvicorn, fastapi, asyncpg..."
  pip install uvicorn fastapi asyncpg
fi

# Start backend op poort 8022
PORT=8022
if lsof -iTCP:$PORT -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  echo "[INFO] Backend draait al op poort $PORT."
else
  echo "[INFO] Start backend op poort $PORT..."
  nohup uvicorn web-ui.backend.api_main:app --reload --port $PORT > backend.log 2>&1 &
  sleep 2
fi

# Check backend health
if curl -s http://localhost:$PORT/api/crew | grep 'Product Manager' >/dev/null; then
  echo "[OK] Backend API werkt op poort $PORT."
else
  echo "[ERROR] Backend API niet bereikbaar op poort $PORT."
  exit 2
fi

# Check frontend
cd web-ui/frontend
if [ ! -f package.json ]; then
  echo "[ERROR] Geen package.json in frontend-map."
  exit 3
fi
npm install
npm run dev &
sleep 3

FRONT_PORT=3000
if curl -s http://localhost:$FRONT_PORT | grep '<div'; then
  echo "[OK] Frontend draait op poort $FRONT_PORT. Open http://localhost:$FRONT_PORT/ in je browser."
else
  echo "[ERROR] Frontend niet bereikbaar op poort $FRONT_PORT."
  exit 4
fi
