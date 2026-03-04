"""Async retry decorator with exponential backoff."""
import asyncio
import logging
from functools import wraps
from typing import Callable, Tuple, Type

logger = logging.getLogger(__name__)


def async_retry(
    max_attempts: int = 3,
    backoff_seconds: float = 2.0,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
):
    """Retry decorator met exponential backoff.

    Usage::

        @async_retry(max_attempts=3, backoff_seconds=2, exceptions=(httpx.HTTPStatusError,))
        async def call_api(...):
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt == max_attempts:
                        logger.error(
                            "%s failed after %d attempts: %s",
                            func.__name__, max_attempts, e,
                        )
                        raise
                    wait_time = backoff_seconds * (2 ** (attempt - 1))
                    logger.warning(
                        "%s attempt %d/%d failed: %s — retrying in %.1fs",
                        func.__name__, attempt, max_attempts, e, wait_time,
                    )
                    await asyncio.sleep(wait_time)
            # Should not reach here, but just in case
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator
