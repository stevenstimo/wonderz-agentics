"""Tests for HR Manager."""

import pytest

from app.services.hr_manager import HRManager


@pytest.mark.asyncio
async def test_scan_retry_patterns_no_pool():
    hr = HRManager(None)
    patterns = await hr.scan_retry_patterns(since_days=7)
    assert patterns == []


@pytest.mark.asyncio
async def test_process_retry_patterns_no_pool():
    hr = HRManager(None)
    result = await hr.process_retry_patterns()
    assert result == {
        "patterns_found": 0,
        "points_created": 0,
        "points_updated": 0,
    }


@pytest.mark.asyncio
async def test_generate_weekly_report_no_pool():
    hr = HRManager(None)
    report = await hr.generate_weekly_report()
    assert report == {}
