"""Scheduler — APScheduler AsyncIO for periodic background tasks.

Runs stale detection daily at 02:00 UTC.
"""

import logging

logger = logging.getLogger(__name__)

_scheduler = None


def start_scheduler(pool):
    """Start the APScheduler scheduler with the stale detection job."""
    global _scheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:
        logger.warning("apscheduler not installed — stale detection cron disabled. pip install apscheduler")
        return

    from app.services.stale_detection import StaleDetectionService

    async def _run_stale_detection():
        try:
            result = await StaleDetectionService().run(pool)
            logger.info("Scheduled stale detection: %s", result)
        except Exception:
            logger.exception("Scheduled stale detection failed")

    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        func=_run_stale_detection,
        trigger="cron",
        hour=2,
        minute=0,
        id="stale_detection",
        replace_existing=True,
    )
    _scheduler.start()
    logging.getLogger("uvicorn.error").info("Stale detection scheduler gestart (dagelijks 02:00 UTC)")


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler gestopt")
