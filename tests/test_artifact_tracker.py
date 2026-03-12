"""
Platform Spec V6 — ArtifactTracker unit tests.
Stap 3: build_artifact_id, save_citations empty, upsert_artifact deduplicatie.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.artifact_tracker import ArtifactTracker


def _mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    acm = MagicMock()
    acm.__aenter__ = AsyncMock(return_value=conn)
    acm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = acm
    return pool, conn


def test_build_artifact_id():
    """Test A: build_artifact_id → artifact:repo:apps/web/checkout/Page.tsx"""
    tracker = ArtifactTracker()
    aid = tracker.build_artifact_id("repo", "apps/web/checkout/Page.tsx")
    assert aid == "artifact:repo:apps/web/checkout/Page.tsx"


@pytest.mark.asyncio
async def test_save_citations_empty_returns_empty_list():
    """Test B: save_citations met lege evidence_list → [] zonder error."""
    pool, conn = _mock_pool()
    tracker = ArtifactTracker()
    ids = await tracker.save_citations(pool, "job-1", "job-1", [])
    assert ids == []


@pytest.mark.asyncio
async def test_upsert_artifact_twice_same_locator_returns_same_artifact_id():
    """Test C: upsert_artifact twee keer zelfde locator → zelfde artifact_id, geen duplicate."""
    pool, conn = _mock_pool()
    conn.execute = AsyncMock()
    tracker = ArtifactTracker()
    aid1 = await tracker.upsert_artifact(
        pool,
        artifact_type="repo_file",
        locator="apps/web/checkout/Page.tsx",
    )
    aid2 = await tracker.upsert_artifact(
        pool,
        artifact_type="repo_file",
        locator="apps/web/checkout/Page.tsx",
    )
    assert aid1 is not None
    assert aid2 is not None
    assert aid1 == aid2 == "artifact:repo_file:apps/web/checkout/Page.tsx"
