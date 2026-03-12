"""Scheduler — APScheduler AsyncIO for periodic background tasks.

Runs stale detection daily at 02:00 UTC.
P8: A/B validation daily at 03:00 UTC.
"""

import logging

logger = logging.getLogger(__name__)

_scheduler = None


def start_scheduler(pool):
    """Start the APScheduler scheduler with the stale detection and A/B validation jobs."""
    global _scheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:
        logger.warning("apscheduler not installed — stale detection cron disabled. pip install apscheduler")
        return

    from app.services.stale_detection import StaleDetectionService
    from app.agents.hr_manager import HRManager as SpecHRManager

    async def _run_stale_detection():
        try:
            result = await StaleDetectionService().run(pool)
            logger.info("Scheduled stale detection: %s", result)
        except Exception:
            logger.exception("Scheduled stale detection failed")

    async def _run_ab_validation():
        try:
            hr = SpecHRManager(pool)
            result = await hr.run_ab_validation(pool)
            logger.info("Scheduled A/B validation: %s", result)
        except Exception:
            logger.exception("Scheduled A/B validation failed")

    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        func=_run_stale_detection,
        trigger="cron",
        hour=2,
        minute=0,
        id="stale_detection",
        replace_existing=True,
    )
    _scheduler.add_job(
        func=_run_ab_validation,
        trigger="cron",
        hour=3,
        minute=0,
        id="ab_validation",
        replace_existing=True,
    )
    _scheduler.start()
    logging.getLogger("uvicorn.error").info("Stale detection (02:00) + A/B validation (03:00) scheduler gestart")


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler gestopt")
