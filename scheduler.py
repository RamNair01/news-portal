"""Daily fetch + summarise job definition."""

import logging
import os

import yaml
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

AMSTERDAM = ZoneInfo("Europe/Amsterdam")


def _load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_refresh_times(config: dict) -> list[str]:
    """Return validated Amsterdam-time refresh slots with legacy config support."""
    configured = config.get("refresh_times")
    times = configured if configured is not None else [config.get("refresh_time", "07:00")]
    if not isinstance(times, list) or not times:
        raise ValueError("refresh_times must be a non-empty list of HH:MM values")

    validated: list[str] = []
    for value in times:
        if not isinstance(value, str):
            raise ValueError("refresh_times entries must be strings in HH:MM format")
        hour, minute = map(int, value.split(":"))
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError(f"Invalid refresh time: {value}")
        normalized = f"{hour:02d}:{minute:02d}"
        if normalized not in validated:
            validated.append(normalized)
    return validated


def run_pipeline():
    """Refresh every source without allowing one failure to stop the rest."""
    logger.info("Starting news refresh pipeline...")
    config = _load_config()

    from db.store import purge_old_items, record_refresh
    from fetcher.rss import fetch_all_rss
    from fetcher.nitter import fetch_nitter, get_failed_accounts
    from fetcher.gmail import fetch_gmail

    jobs = {
        "cleanup": lambda: purge_old_items(),
        "rss": lambda: fetch_all_rss(config),
        "twitter": lambda: fetch_nitter(config),
        "gmail": lambda: fetch_gmail(config),
    }
    results: dict[str, int | None] = {}
    failures: list[str] = []
    for name, job in jobs.items():
        try:
            result = job()
            results[name] = result
        except Exception as exc:
            logger.exception("Refresh step failed [%s]: %s", name, exc)
            failures.append(name)

    if results.get("gmail") is None:
        failures.append("gmail")
    if get_failed_accounts():
        failures.append("twitter")

    status = "partial" if failures else "ok"
    details = ", ".join(sorted(set(failures))) if failures else ""
    try:
        record_refresh(status, details)
    except Exception:
        logger.exception("Could not record refresh status")

    logger.info("News refresh pipeline complete: %s", status)
    return {"status": status, "results": results, "failures": sorted(set(failures))}


def create_scheduler() -> BackgroundScheduler:
    config = _load_config()
    refresh_times = get_refresh_times(config)

    scheduler = BackgroundScheduler(timezone=AMSTERDAM)
    for refresh_time in refresh_times:
        hour, minute = map(int, refresh_time.split(":"))
        scheduler.add_job(
            run_pipeline,
            trigger=CronTrigger(hour=hour, minute=minute, timezone=AMSTERDAM),
            id=f"news_fetch_{hour:02d}{minute:02d}",
            name=f"News refresh at {refresh_time} Amsterdam time",
            replace_existing=True,
        )
    return scheduler
