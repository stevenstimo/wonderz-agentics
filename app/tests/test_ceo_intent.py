"""CEO intent: detect_job_type + check_resources (asyncpg)."""

import os

import asyncpg
import pytest
import pytest_asyncio

from app.orchestration.ceo_intent import check_resources, detect_job_type

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://wonderz:wonderz123@localhost:5432/wonderz"
)


@pytest_asyncio.fixture
async def db_conn():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_detect_job_type_blog_seo(db_conn):
    pid = await detect_job_type(db_conn, "schrijf een blog artikel over SEO")
    assert pid == "seo-content-campaign"


@pytest.mark.asyncio
async def test_check_resources_seo_campaign_has_ready_and_message(db_conn):
    report = await check_resources(db_conn, "seo-content-campaign")
    assert "ready" in report
    assert "message" in report
    assert isinstance(report["message"], str)
