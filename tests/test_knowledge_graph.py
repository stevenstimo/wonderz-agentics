"""
Platform Spec V5 — Knowledge Graph unit tests.
Stap 1: add_edge deduplicatie (zelfde from_id, to_id, edge_type → zelfde edge_id).
Stap 2: register_pattern → pattern_id, patterns row, edges, event (mocked).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.knowledge_graph import KnowledgeGraph
from app.services.lessons_lifecycle import _extract_pattern_name


def _mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    acm = MagicMock()
    acm.__aenter__ = AsyncMock(return_value=conn)
    acm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = acm
    return pool, conn


@pytest.mark.asyncio
async def test_add_edge_deduplication_same_edge_id():
    """Stap 1: Twee add_edge metzelfde from_id, to_id, edge_type → zelfde edge_id, COUNT 1."""
    pool, conn = _mock_pool()
    fake_id = "550e8400-e29b-41d4-a716-446655440000"
    conn.fetchrow = AsyncMock(side_effect=[
        None,
        {"edge_id": fake_id},
        {"edge_id": fake_id},
    ])
    conn.execute = AsyncMock()

    graph = KnowledgeGraph()
    edge_id_1 = await graph.add_edge(
        pool,
        "lesson:TEST-001",
        "task:CI-TEST",
        "LESSON_DERIVED_FROM",
    )
    edge_id_2 = await graph.add_edge(
        pool,
        "lesson:TEST-001",
        "task:CI-TEST",
        "LESSON_DERIVED_FROM",
    )

    assert edge_id_1 is not None
    assert edge_id_2 is not None
    assert edge_id_1 == edge_id_2 == fake_id
    conn.execute.assert_called()


@pytest.mark.asyncio
async def test_register_pattern_returns_pattern_id_and_emits_event():
    """Stap 2: register_pattern → pattern_id = pattern:useasyncresource, edges + event (mocked)."""
    pool, conn = _mock_pool()
    conn.execute = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)

    with patch("app.services.knowledge_graph.KnowledgeGraph.add_edge", new_callable=AsyncMock) as mock_add:
        mock_add.return_value = "edge-uuid"
        with patch("app.services.event_emitter.EventEmitter.emit", new_callable=AsyncMock) as mock_emit:
            mock_emit.return_value = "event-uuid"
            graph = KnowledgeGraph()
            pattern_id = await graph.register_pattern(
                pool,
                lesson_id="TEST-2026-03-001",
                pattern_name="useAsyncResource",
                applies_to_domain="frontend",
            )

    assert pattern_id == "pattern:useasyncresource"
    assert conn.execute.called
    assert mock_add.call_count >= 2
    mock_emit.assert_called_once()


def test_extract_pattern_name_returns_first_five_words_when_suffix_found():
    """Heuristiek: zin met woord dat eindigt op hook/pattern/... → eerste 5 woorden."""
    assert _extract_pattern_name("Use a custom hook for data loading.") == "Use a custom hook for"
    assert _extract_pattern_name("We should use the useAsyncResource pattern here.") is not None


def test_extract_pattern_name_returns_none_when_short_or_no_suffix():
    """Korte tekst of geen suffix → None."""
    assert _extract_pattern_name("") is None
    assert _extract_pattern_name("short") is None
    assert _extract_pattern_name("Just some random text without any keywords here.") is None
