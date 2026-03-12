"""
Email Intake Channel §4.3 — SenderMatcher unit tests (3 required).
Uses mocked DB pool/conn so no real DB needed.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.sender_matcher import SenderMatcher


def _mock_pool(fetchrow_result):
    """Build mock pool with conn that returns fetchrow_result from fetchrow()."""
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow_result)
    acm = MagicMock()
    acm.__aenter__ = AsyncMock(return_value=conn)
    acm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = acm
    return pool


@pytest.mark.asyncio
async def test_known_sender():
    """When email exists in users, match() returns that user's id."""
    user_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    pool = _mock_pool({"id": user_id})

    with patch("app.services.sender_matcher.get_db", AsyncMock(return_value=pool)):
        result = await SenderMatcher.match("jan@example.com")

    assert result == user_id


@pytest.mark.asyncio
async def test_unknown_sender():
    """When email is not in users, match() returns None."""
    pool = _mock_pool(None)

    with patch("app.services.sender_matcher.get_db", AsyncMock(return_value=pool)):
        result = await SenderMatcher.match("stranger@example.com")

    assert result is None


@pytest.mark.asyncio
async def test_case_insensitive():
    """Matching is case-insensitive: User@Example.COM matches same row as user@example.com."""
    user_id = "f0000000-0000-4000-8000-000000000001"
    pool = _mock_pool({"id": user_id})

    with patch("app.services.sender_matcher.get_db", AsyncMock(return_value=pool)):
        result = await SenderMatcher.match("User@Example.COM")

    assert result == user_id
    # Verify the query used LOWER so DB does case-insensitive match
    conn = pool.acquire.return_value.__aenter__.return_value
    call_args = conn.fetchrow.call_args[0]
    assert "LOWER" in call_args[0]
    assert call_args[1] == "User@Example.COM"
