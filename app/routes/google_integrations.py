"""
Router voor Google Integrations API endpoints.
Prefix: /api/integrations/google
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.integrations import (
    GOOGLE_INTEGRATIONS_STATUS,
    fetch_crux,
    fetch_pagespeed,
    nl_analyze,
    request_indexing,
    search_entity,
    translate,
)

router = APIRouter(prefix="/api/integrations/google", tags=["google-integrations"])


@router.get("/status")
async def get_integration_status():
    """Retourneert welke Google-integraties actief zijn op platformniveau."""
    return {"status": GOOGLE_INTEGRATIONS_STATUS}


class PageSpeedRequest(BaseModel):
    url: str
    strategy: str = "mobile"


@router.post("/pagespeed")
async def pagespeed(req: PageSpeedRequest):
    result = await fetch_pagespeed(req.url, req.strategy)
    if not result.get("enabled"):
        raise HTTPException(status_code=503, detail="PageSpeed integratie niet actief")
    return result


class CruxRequest(BaseModel):
    origin: str
    form_factor: str = "PHONE"


@router.post("/crux")
async def crux(req: CruxRequest):
    result = await fetch_crux(req.origin, req.form_factor)
    if not result.get("enabled"):
        raise HTTPException(status_code=503, detail="CrUX integratie niet actief")
    return result


class NLRequest(BaseModel):
    text: str


@router.post("/natural-language/analyze")
async def natural_language_analyze(req: NLRequest):
    result = await nl_analyze(req.text)
    if not result.get("enabled"):
        raise HTTPException(status_code=503, detail="Natural Language integratie niet actief")
    return result


class IndexingRequest(BaseModel):
    url: str
    notification_type: str = "URL_UPDATED"


@router.post("/indexing/notify")
async def indexing_notify(req: IndexingRequest):
    result = await request_indexing(req.url, req.notification_type)
    if not result.get("enabled"):
        raise HTTPException(status_code=503, detail="Indexing integratie niet actief")
    return result


class KGRequest(BaseModel):
    query: str
    limit: int = 5


@router.post("/knowledge-graph/search")
async def knowledge_graph_search(req: KGRequest):
    result = await search_entity(req.query, req.limit)
    if not result.get("enabled"):
        raise HTTPException(status_code=503, detail="Knowledge Graph integratie niet actief")
    return result


class TranslateRequest(BaseModel):
    text: str
    target_language: str
    source_language: str | None = None


@router.post("/translate")
async def translate_text(req: TranslateRequest):
    result = await translate(req.text, req.target_language, req.source_language)
    if not result.get("enabled"):
        raise HTTPException(status_code=503, detail="Translate integratie niet actief")
    return result
