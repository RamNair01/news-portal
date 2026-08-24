"""Nitter RSS fetcher — one feed per Twitter account, fails gracefully."""

import logging
import os
from datetime import datetime, timezone

import feedparser

from db.store import insert_item

logger = logging.getLogger(__name__)

# Tracks which accounts failed in the last cycle (surfaced in the dashboard)
failed_accounts: list[str] = []


def _parse_date(entry) -> str:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def fetch_nitter(config: dict) -> int:
    global failed_accounts
    failed_accounts = []

    nitter_cfg = config.get("nitter", {})
    base_url = os.environ.get("NITTER_BASE_URL", nitter_cfg.get("base_url", "https://nitter.privacydev.net")).rstrip("/")
    accounts = nitter_cfg.get("accounts", [])

    new_count = 0
    for username in accounts:
        url = f"{base_url}/{username}/rss"
        try:
            parsed = feedparser.parse(url)
            if parsed.bozo and not parsed.entries:
                raise ValueError(f"Feed parse error: {parsed.bozo_exception}")
            for entry in parsed.entries:
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                guid = entry.get("id", link)
                body = entry.get("summary", "")
                published_at = _parse_date(entry)
                inserted = insert_item(
                    category="twitter",
                    source=f"@{username}",
                    title=title,
                    url=link,
                    guid=guid,
                    body=body,
                    published_at=published_at,
                )
                if inserted:
                    new_count += 1
            logger.info("Nitter [@%s] — %d entries fetched", username, len(parsed.entries))
        except Exception as exc:
            logger.error("Nitter fetch failed for @%s: %s", username, exc)
            failed_accounts.append(username)

    return new_count


def get_failed_accounts() -> list[str]:
    return list(failed_accounts)
