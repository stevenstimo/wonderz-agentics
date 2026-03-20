import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.token_guard import TokenGuard


@pytest.mark.asyncio
async def test_register_usage_casts_str_tokens_and_step_id(caplog):
    token_guard = TokenGuard()

    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch.object(
        token_guard, "_get_conn", new=AsyncMock(return_value=mock_cm)
    ):
        await token_guard.register_usage(
            job_id="job-1", tokens_used="1500", step_id="12"
        )

    # 2 writes: jobs + job_steps
    assert mock_conn.execute.call_count == 2

    job_update = mock_conn.execute.call_args_list[0].args
    job_steps_update = mock_conn.execute.call_args_list[1].args

    assert (
        "UPDATE jobs SET tokens_used" in job_update[0]
    ), "jobs update query expected"
    assert isinstance(job_update[1], int) and job_update[1] == 1500

    assert (
        "UPDATE job_steps SET tokens_used" in job_steps_update[0]
    ), "job_steps update query expected"
    assert isinstance(job_steps_update[2], int) and job_steps_update[2] == 12


@pytest.mark.asyncio
async def test_register_usage_invalid_tokens_casts_to_zero_and_updates(caplog):
    token_guard = TokenGuard()

    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    caplog.set_level(logging.WARNING, logger="app.services.token_guard")

    with patch.object(
        token_guard, "_get_conn", new=AsyncMock(return_value=mock_cm)
    ):
        await token_guard.register_usage(
            job_id="job-1", tokens_used="not-a-number", step_id="12"
        )

    assert mock_conn.execute.call_count == 2

    # Ensure tokens_used fell back to 0
    tokens_used_arg = mock_conn.execute.call_args_list[0].args[1]
    assert isinstance(tokens_used_arg, int) and tokens_used_arg == 0

    assert "fallback to 0" in caplog.text


@pytest.mark.asyncio
async def test_register_usage_invalid_step_id_skips_job_steps_update():
    token_guard = TokenGuard()

    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch.object(
        token_guard, "_get_conn", new=AsyncMock(return_value=mock_cm)
    ):
        await token_guard.register_usage(
            job_id="job-1", tokens_used="1500", step_id="not-a-number"
        )

    # Only jobs update should run
    assert mock_conn.execute.call_count == 1
    assert "UPDATE jobs SET tokens_used" in mock_conn.execute.call_args_list[0].args[0]

