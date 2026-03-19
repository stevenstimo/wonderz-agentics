"""Clients API stub — list, CRUD, datasources, knowledge, platforms, dashboard, integrations config."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.get("")
async def list_clients():
    return []


@router.post("")
async def create_client():
    return {"ok": True}


@router.get("/{slug}")
async def get_client(slug: str):
    return {}


@router.patch("/{slug}")
async def update_client(slug: str):
    return {"ok": True}


@router.get("/{slug}/datasources")
async def list_datasources(slug: str):
    return []


@router.post("/{slug}/datasources")
async def create_datasource(slug: str):
    return {"ok": True}


@router.get("/{slug}/knowledge")
async def get_client_knowledge(slug: str):
    return []


@router.get("/{slug}/platforms")
async def get_client_platforms(slug: str):
    return {}


@router.get("/{slug}/dashboard")
async def get_client_dashboard(slug: str):
    return {}


@router.get("/{slug}/integrations/{service_type}/config")
async def get_integration_config(slug: str, service_type: str):
    return {}


@router.post("/{slug}/integrations/{service_type}/config")
async def save_integration_config(slug: str, service_type: str):
    return {"ok": True}
