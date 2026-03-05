"""Status/health summary endpoint for the Dashboard."""
import os
import hashlib
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
    backend_ok = health['checks']['backend'].get('ok', False)
    db_ok = health['checks']['database'].get('ok', False)
    health_status = "ok" if (backend_ok and db_ok) else ("degraded" if db_ok else "error")
    health["status"] = health_status

    active_providers = [p for p in (['Anthropic'] if os.getenv('ANTHROPIC_API_KEY', '').strip() else []) + (['OpenAI'] if os.getenv('OPENAI_API_KEY', '').strip() else [])]
    settings_ok = len(active_providers) > 0

    dave_ok = backend_ok
    dave_dev = {
        "ok": dave_ok,
        "status": "active" if dave_ok else "unknown",
        "specialization": "Full-stack Technical Consultant & Agentic Architecture Specialist" if dave_ok else "Geen data ontvangen",
    }

    recent_commits = []
    working_tree_top = []
    try:
        r = subprocess.run(
            ["git", "log", "-5", "--oneline"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        )
        if r.returncode == 0 and r.stdout:
            recent_commits = [line.strip() for line in r.stdout.strip().split("\n") if line.strip()]
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        )
        if r.returncode == 0 and r.stdout:
            working_tree_top = [line.strip() for line in r.stdout.strip().split("\n")[:8] if line.strip()]
    except Exception:
        pass

    return {
        "health": health,
        "systemd": systemd,
        "settings": {
            "ok": settings_ok,
            "active_providers": active_providers,
        },
        "dave_dev": dave_dev,
        "recent": {
            "recent_commits": recent_commits,
            "working_tree_top": working_tree_top,
        },
        "all_ok": all_ok,
    }

@router.get("/keys")
async def status_keys():
    """Zichtbaar op live URL: of API-keys geladen zijn (zonder de key te tonen). Fingerprint = eerste 8 tekens van sha256 om te verifiëren dat de juiste key geladen is."""
    anthropic_key = os.getenv('ANTHROPIC_API_KEY', '').strip()
    openai_key = os.getenv('OPENAI_API_KEY', '').strip()
    def _hash8(k):
        return hashlib.sha256(k.encode()).hexdigest()[:8] if k else ""
    return {
        "anthropic": {
            "loaded": bool(anthropic_key),
            "length": len(anthropic_key) if anthropic_key else 0,
            "fingerprint": _hash8(anthropic_key),
        },
        "openai": {
            "loaded": bool(openai_key),
            "length": len(openai_key) if openai_key else 0,
            "fingerprint": _hash8(openai_key),
        },
    }


@router.get("/api/health")
async def health_check():
    return {"status": "ok"}
