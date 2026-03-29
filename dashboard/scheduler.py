"""
dashboard/scheduler.py

APScheduler integration — runs scrape_prices() automatically every 5 minutes.

Concepts covered:
- Background jobs in Django
- Scheduled tasks without Celery (good for simple use cases)
- AppConfig pattern for startup initialization
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution
import django

logger = logging.getLogger('dashboard')

scheduler = None


def scheduled_scrape():
    """
    This function is called by APScheduler on a schedule.
    It runs in a background thread.
    """
    logger.info("⏰ Scheduled scrape starting...")
    try:
        from scraper.coingecko import scrape_prices
        result = scrape_prices()
        logger.info(f"✅ Scheduled scrape done: {result}")
    except Exception as e:
        logger.error(f"❌ Scheduled scrape failed: {e}")


def start_scheduler():
    """
    Starts the background scheduler.
    Called from AppConfig.ready() so it runs once on server startup.
    """
    global scheduler

    if scheduler and scheduler.running:
        logger.info("Scheduler already running, skipping.")
        return

    scheduler = BackgroundScheduler()
    scheduler.add_jobstore(DjangoJobStore(), "default")

    # Schedule scrape every 5 minutes
    scheduler.add_job(
        scheduled_scrape,
        trigger=IntervalTrigger(minutes=5),
        id="scrape_prices",
        name="Scrape crypto prices every 5 minutes",
        jobstore="default",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping runs
    )

    scheduler.start()
    logger.info("✅ APScheduler started. Scraping every 5 minutes.")


def stop_scheduler():
    """Gracefully stops the scheduler."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped.")
