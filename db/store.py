"""SQLite read/write helpers."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

AMSTERDAM = ZoneInfo("Europe/Amsterdam")

DB_PATH = Path(__file__).parent.parent / "news.db"


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                category    TEXT    NOT NULL,
                source      TEXT    NOT NULL,
                title       TEXT    NOT NULL,
                url         TEXT,
                guid        TEXT    UNIQUE,
                body        TEXT,
                summary     TEXT,
                published_at TEXT,
                fetched_at  TEXT    NOT NULL,
                pinned      INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Migrate existing DB — add pinned column if it doesn't exist yet
        try:
            con.execute("ALTER TABLE items ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass  # column already exists
        con.execute("""
            CREATE TABLE IF NOT EXISTS refresh_state (
                id          INTEGER PRIMARY KEY CHECK (id = 1),
                refreshed_at TEXT NOT NULL,
                status      TEXT NOT NULL,
                details     TEXT
            )
        """)


# ── Write ────────────────────────────────────

def insert_item(category: str, source: str, title: str, url: str,
                guid: str, body: str, published_at: str) -> bool:
    """Insert a new item. Returns True if inserted, False if duplicate."""
    fetched_at = datetime.now(timezone.utc).isoformat()
    try:
        with _conn() as con:
            con.execute(
                """INSERT INTO items
                   (category, source, title, url, guid, body, published_at, fetched_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (category, source, title, url, guid, body, published_at, fetched_at),
            )
        return True
    except sqlite3.IntegrityError:
        return False  # duplicate guid


# ── Read ─────────────────────────────────────

def get_today_items(max_per_category: int = 5) -> dict[str, list[dict]]:
    """Return today's items grouped by category, capped per section."""
    today = datetime.now(AMSTERDAM).replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff = today.astimezone(timezone.utc).isoformat()
    with _conn() as con:
        rows = con.execute(
            """SELECT * FROM items
               WHERE fetched_at >= ?
               ORDER BY category, COALESCE(published_at, fetched_at) DESC""",
            (cutoff,),
        ).fetchall()

    grouped: dict[str, list[dict]] = {}
    counts: dict[str, int] = {}
    for row in rows:
        d = dict(row)
        cat = d["category"]
        counts.setdefault(cat, 0)
        if counts[cat] < max_per_category:
            grouped.setdefault(cat, []).append(d)
            counts[cat] += 1
    return grouped


def get_today_headlines() -> list[dict]:
    """Today's items (title + source + category) — used as chat context."""
    today = datetime.now(AMSTERDAM).replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff = today.astimezone(timezone.utc).isoformat()
    with _conn() as con:
        rows = con.execute(
            """SELECT category, source, title
               FROM items
               WHERE fetched_at >= ?
               ORDER BY category, COALESCE(published_at, fetched_at) DESC""",
            (cutoff,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_refresh_state() -> dict | None:
    """Return the outcome of the most recent refresh, if one has completed."""
    with _conn() as con:
        row = con.execute(
            "SELECT refreshed_at, status, details FROM refresh_state WHERE id = 1"
        ).fetchone()
    return dict(row) if row else None


def record_refresh(status: str, details: str = ""):
    """Persist refresh health separately from article insertion timestamps."""
    with _conn() as con:
        con.execute(
            """INSERT INTO refresh_state (id, refreshed_at, status, details)
               VALUES (1, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   refreshed_at = excluded.refreshed_at,
                   status = excluded.status,
                   details = excluded.details""",
            (datetime.now(timezone.utc).isoformat(), status, details),
        )


# ── Pins ─────────────────────────────────────

def toggle_pin(item_id: int) -> bool:
    """Flip pinned state. Returns the new pinned state (True = pinned)."""
    with _conn() as con:
        con.execute(
            "UPDATE items SET pinned = CASE WHEN pinned = 1 THEN 0 ELSE 1 END WHERE id = ?",
            (item_id,),
        )
        row = con.execute("SELECT pinned FROM items WHERE id = ?", (item_id,)).fetchone()
    return bool(row["pinned"]) if row else False


def get_pinned_items() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """SELECT * FROM items WHERE pinned = 1
               ORDER BY COALESCE(published_at, fetched_at) DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


# ── Maintenance ───────────────────────────────

def purge_old_items(days: int = 7):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _conn() as con:
        # Never purge pinned items
        con.execute("DELETE FROM items WHERE fetched_at < ? AND pinned = 0", (cutoff,))
