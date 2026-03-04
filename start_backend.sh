#!/bin/bash
cd /home/exedev/wonderz-agentics
source .venv/bin/activate
export DATABASE_URL="postgresql://wonderz:wonderz123@localhost:5432/wonderz"
pkill -f uvicorn 2>/dev/null; sleep 1
uvicorn app.main:app --host 0.0.0.0 --port 8090 &
echo "✅ Backend gestart"
