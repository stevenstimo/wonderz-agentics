# Local PostgreSQL setup instructions

## 1. Start the local database

    docker compose -f docker-compose.local-postgres.yml up -d

- This will start a PostgreSQL 15 database on port 5432 with user `postgres` and password `postgres`.
- Data is persisted in a Docker volume (`pgdata`).

## 2. Configure your backend

- Copy `.env.local.example` to `.env.local`:

      cp .env.local.example .env.local

- Adjust `DATABASE_URL` if needed (default works for the provided compose file):

      DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres

- Make sure your backend loads this `.env.local` file (or set the variable in your shell).

## 3. Run migrations (if needed)

- If your backend uses Alembic or similar, run migrations to set up the schema.

## 4. Start your backend (example):

    source .venv/bin/activate
    export $(cat .env.local | grep -v '^#' | xargs)
    uvicorn web-ui.backend.api_main:app --reload --port 8000

## 5. Connect your frontend

- Use the backend API URL as needed (e.g., `VITE_API_URL=http://localhost:8000`).

---

**Tip:**
- To stop the database: `docker compose -f docker-compose.local-postgres.yml down`
- To remove all data: `docker volume rm claude_pgdata` (be careful!)
