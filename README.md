# Ram's News Portal

A private, locally hosted news dashboard that brings RSS feeds, selected X accounts through Nitter, and a Gmail newsletter into one editorial interface. Its built-in assistant answers questions using the current day's headlines as context.

This repository is intended as a portfolio project. It is not a hosted product and does not collect telemetry.

## Features

- Aggregates configurable global, Malaysian, technology, and AI RSS feeds.
- Fetches selected X accounts through Nitter. Individual Nitter failures remain visible in the dashboard and do not stop the other sources.
- Reads a single Gmail newsletter using the minimum read-only Gmail OAuth scope.
- Stores deduplicated articles in SQLite and removes unpinned items older than seven days.
- Runs scheduled refreshes in the Europe/Amsterdam timezone, with a manual refresh option.
- Provides a concise OpenAI Responses API chat panel grounded in today's headlines.

## Quick start

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env
uv run python run.py
```

Add `OPENAI_API_KEY` to `.env` to enable the News Assistant. The dashboard is available at http://127.0.0.1:5000.

## Gmail setup

Gmail is optional. To enable the newsletter source, create an OAuth desktop-client credential in Google Cloud, save it as `credentials.json` in the repository root, and trigger a refresh. The browser consent flow creates `token.json` after approval.

The application requests only `https://www.googleapis.com/auth/gmail.readonly`. Neither OAuth file is committed to Git.

## Configuration

Edit `config.yaml` to set feed sources, Nitter accounts, the Gmail sender filter, dashboard item limits, and Europe/Amsterdam refresh times. `NITTER_BASE_URL` can override the configured Nitter instance without changing the file. `OPENAI_MODEL` can override the default `gpt-5.6-terra` model.

## Project structure

```
ai/                 OpenAI Responses API chat integration
db/                 SQLite schema and queries
fetcher/            RSS, Nitter, and Gmail ingestion adapters
server/             Flask application, templates, and static assets
tests/              Lightweight regression tests
config.yaml         User-configurable feed and runtime settings
scheduler.py        Scheduled, fault-tolerant refresh pipeline
run.py              Local application entry point
```

## Development checks

```bash
uv run python -m py_compile run.py scheduler.py db/store.py fetcher/*.py ai/*.py server/*.py
uv run python -m unittest discover -s tests
```

## Data and privacy

`news.db`, OAuth credentials, access tokens, virtual environments, and `.env` are local-only and ignored by Git. The project keeps article records for seven days, except pinned items, which are retained until unpinned. The OpenAI API key is read only from `OPENAI_API_KEY` and is never logged.
