#!/bin/bash
export DATABASE_URL='postgresql://wonderz:wonderz123@localhost:5432/wonderz'
export RUN_MIGRATIONS=false
export PYTHONPATH='/home/exedev/wonderz-agentics'
cd /home/exedev/wonderz-agentics
source .venv/bin/activate
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8090
