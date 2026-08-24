"""RSS feed fetcher — parses all configured feeds and stores new items."""

import logging
from datetime import datetime, timezone

import feedparser

from db.store import insert_item

logger = logging.getLogger(__name__)


def _parse_date(entry) -> str:
    """Best-effort published date → ISO string."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def _entry_guid(entry) -> str:
    return getattr(entry, "id", None) or getattr(entry, "link", "") or entry.get("title", "")


def fetch_category(category: str, feeds: list[dict]) -> int:
    """Fetch all feeds for a category. Returns count of new items inserted."""
    new_count = 0
    for feed_cfg in feeds:
        name = feed_cfg["name"]
        url = feed_cfg["url"]
        try:
            parsed = feedparser.parse(url)
            if parsed.bozo and not parsed.entries:
                logger.warning("Feed parse error [%s]: %s", name, parsed.bozo_exception)
                continue
            for entry in parsed.entries:
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                guid = _entry_guid(entry)
                body = (
                    entry.get("summary", "")
                    or entry.get("content", [{}])[0].get("value", "")
                )
                published_at = _parse_date(entry)
                inserted = insert_item(
                    category=category,
                    source=name,
                    title=title,
                    url=link,
                    guid=guid,
                    body=body,
                    published_at=published_at,
                )
                if inserted:
                    new_count += 1
            logger.info("Fetched [%s / %s] — %d entries", category, name, len(parsed.entries))
        except Exception as exc:
            logger.error("Failed to fetch feed [%s]: %s", name, exc)
    return new_count


def fetch_all_rss(config: dict) -> int:
    total = 0
    for category, feeds in config.get("feeds", {}).items():
        total += fetch_category(category, feeds)
    logger.info("RSS fetch complete — %d new items total", total)
    return total
