"""Status/health summary endpoint for the Dashboard."""
import os
import subprocess
import asyncio
import httpx
from fastapi import APIRouter

router = APIRouter(prefix='/api/status', tags=['status'])


async def _check_http(url: str, timeout: float = 3.0) -> dict:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            return {"status": "ok", "detail": f"HTTP {resp.status_code}", "ok": resp.status_code < 400}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:100], "ok": False}


async def _check_redis() -> dict:
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, socket_timeout=2)
        return {"status": "ok", "detail": r.ping() and "PONG", "ok": True}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:100], "ok": False}


async def _check_postgres() -> dict:
    try:
        import asyncpg
        dsn = os.getenv('DATABASE_URL', 'postgresql://wonderz:wonderz123@localhost:5432/wonderz')
        conn = await asyncpg.connect(dsn, timeout=3)
        await conn.fetchval('SELECT 1')
        await conn.close()
        return {"status": "ok", "detail": "Connected", "ok": True}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:100], "ok": False}


async def _check_celery() -> dict:
    try:
        from workers.celery_app import celery
        insp = celery.control.inspect(timeout=2)
        active = insp.active_queues()
        if active:
            workers = list(active.keys())
            return {"status": "ok", "detail": f"{len(workers)} worker(s): {', '.join(workers[:3])}", "ok": True}
        return {"status": "error", "detail": "No workers", "ok": False}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:100], "ok": False}


def _check_systemd(service: str) -> dict:
    try:
        r = subprocess.run(['systemctl', 'is-active', service], capture_output=True, text=True, timeout=3)
        state = r.stdout.strip()
        return {"status": state, "ok": state == "active"}
    except Exception:
        return {"status": "unknown", "ok": False}


async def _get_llm_keys() -> dict:
    anthropic = bool(os.getenv('ANTHROPIC_API_KEY', '').strip())
    openai = bool(os.getenv('OPENAI_API_KEY', '').strip())
    active = []
    if anthropic: active.append('Anthropic')
    if openai: active.append('OpenAI')
    # Also check stored keys
    try:
        import json
        keys_file = '/home/exedev/wonderz-agentics/codex-web/api_keys.json'
        if os.path.exists(keys_file):
            with open(keys_file) as f:
                stored = json.load(f)
            for k in stored:
                if k.get('value') and 'ANTHROPIC' in k.get('name', '').upper() and 'Anthropic' not in active:
                    active.append('Anthropic')
                if k.get('value') and 'OPENAI' in k.get('name', '').upper() and 'OpenAI' not in active:
                    active.append('OpenAI')
    except Exception:
        pass
    return {
        "status": "ok" if active else "warning",
        "detail": f"Active: {', '.join(active)}" if active else "No API keys configured",
        "ok": len(active) > 0
    }


@router.get('/summary')
async def status_summary():
    # Run all checks in parallel
    backend_check, frontend_check, pg_check, redis_check, celery_check, terminal_check, codex_check, llm_check = await asyncio.gather(
        _check_http('http://localhost:8090/api/agents'),
        _check_http('http://localhost:3000/'),
        _check_postgres(),
        _check_redis(),
        _check_celery(),
        _check_http('http://localhost:7681/'),
        _check_http('http://localhost:8080/'),
        _get_llm_keys(),
    )

    # Systemd services
    systemd = {}
    for svc in ['wonderz-backend', 'wonderz-worker', 'wonderz-frontend', 'redis-server', 'wonderz-terminal', 'wonderz-codex-web']:
        short = svc.replace('wonderz-', '')
        systemd[short] = _check_systemd(svc)

    health = {
        "checks": {
            "backend": {**backend_check, "label": "Backend API", "detail": "Running (this service)"},
            "frontend": {**frontend_check, "label": "Frontend"},
            "database": {**pg_check, "label": "PostgreSQL"},
            "redis": {**redis_check, "label": "Redis"},
            "celery_worker": {**celery_check, "label": "Celery Worker"},
            "terminal": {**terminal_check, "label": "Terminal (ttyd)"},
            "codex_web": {**codex_check, "label": "Codex Console"},
            "llm_providers": {**llm_check, "label": "LLM Providers"},
        }
    }

    all_ok = all(c.get('ok') for c in health['checks'].values())

    return {
        "health": health,
        "systemd": systemd,
        "settings": {
            "active_providers": [p for p in (['Anthropic'] if os.getenv('ANTHROPIC_API_KEY', '').strip() else []) + (['OpenAI'] if os.getenv('OPENAI_API_KEY', '').strip() else [])]
        },
        "all_ok": all_ok,
    }

@router.get("/api/health")
async def health_check():
    return {"status": "ok"}
