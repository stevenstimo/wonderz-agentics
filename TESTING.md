# Testing & Local Run Instructions

This document explains how to run the unit test and start the dev services for the Multi-Agentic Crew MVP.

Prerequisites
- Python 3.10+ installed
- Redis (for Celery) and Postgres (for actual runtime) if you want to run full integration — unit tests do not require them

1) Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2) Install dependencies for tests

```bash
pip install -r requirements-dev.txt
```

3) Run the unit test (it uses mocked DB calls)

```bash
pytest -q tests/test_workflow.py
```

4) Run the API server (development)

```bash
# set DATABASE_URL and optionally APPROVAL_USER/APPROVAL_PASS for approve endpoint
export DATABASE_URL='postgresql://user:pass@localhost:5432/dbname'
export APPROVAL_USER='admin'
export APPROVAL_PASS='secret'
uvicorn app.main:app --reload --port 8000
```

5) Start Celery worker

```bash
export CELERY_BROKER_URL='redis://localhost:6379/0'
export CELERY_RESULT_BACKEND='redis://localhost:6379/0'
celery -A workers.celery_app.celery worker -Q jobs -l info
```

6) Create a job (example)

```bash
curl -X POST http://localhost:8000/api/jobs -H "Content-Type: application/json" -d '{"store_id":null,"job_type":"pdp_optimization","payload":{"context": {"product":{"title":"Fancy Hat"}}}}'
```

7) Approve a job that reached the approval gate

If a job is `AWAITING_APPROVAL`, call the approve endpoint using Basic Auth (user/pass from env):

```bash
# basic auth header example for user 'admin' and pass 'secret'
AUTH=$(echo -n "admin:secret" | base64)
curl -X POST "http://localhost:8000/api/jobs/<JOB_ID>/approve" -H "Authorization: Basic $AUTH"
```

Notes
- The unit test provided (`tests/test_workflow.py`) is self-contained and mocks DB operations — you don't need Redis/Postgres to run it.
- For production-like testing, provision a Postgres instance, create the SQL schema, and set `DATABASE_URL`.