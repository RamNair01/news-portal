"""Flask application — dashboard + chat SSE endpoint."""

import json
import logging
import os
from zoneinfo import ZoneInfo

import yaml
from flask import Flask, Response, jsonify, render_template, request, stream_with_context

from ai.chat import stream_chat
from db.store import get_pinned_items, get_refresh_state, get_today_items, init_db, toggle_pin

logger = logging.getLogger(__name__)

AMSTERDAM = ZoneInfo("Europe/Amsterdam")

SECTION_ORDER = ["global", "malaysia", "tech", "ai", "twitter", "rundown"]
SECTION_LABELS = {
    "global": "Global",
    "malaysia": "Malaysia",
    "tech": "Tech",
    "ai": "AI",
    "twitter": "Twitter / X",
    "rundown": "The Rundown AI",
}


def _load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates")
    init_db()
    config = _load_config()
    max_items = config.get("max_items_per_section", 10)

    @app.route("/")
    def index():
        raw = get_today_items(max_per_category=max_items)
        refresh_state = get_refresh_state()
        refresh_failures = set((refresh_state or {}).get("details", "").split(", "))
        # Build ordered sections, skipping empty ones
        sections = []
        for cat in SECTION_ORDER:
            items = raw.get(cat, [])
            if items:
                sections.append({
                    "key": cat,
                    "label": SECTION_LABELS.get(cat, cat.title()),
                    "articles": items,
                })

        # Nitter failure notice
        from fetcher.nitter import get_failed_accounts
        failed_twitter = get_failed_accounts()

        return render_template(
            "index.html",
            sections=sections,
            failed_twitter=failed_twitter,
            twitter_unavailable=bool(failed_twitter) or "twitter" in refresh_failures,
            refresh_state=refresh_state,
            amsterdam_tz=AMSTERDAM,
        )

    @app.route("/chat", methods=["POST"])
    def chat():
        data = request.get_json(silent=True) or {}
        messages = data.get("messages", [])
        if not messages:
            return {"error": "No messages provided"}, 400

        def generate():
            for chunk in stream_chat(messages):
                yield f"data: {json.dumps({'text': chunk})}\n\n"
            yield "data: [DONE]\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.route("/pinned")
    def pinned_page():
        return render_template("pinned.html", pinned=get_pinned_items())

    @app.route("/pin/<int:item_id>", methods=["POST"])
    def pin(item_id):
        new_state = toggle_pin(item_id)
        return {"pinned": new_state}

    @app.route("/manifest.json")
    def manifest():
        return jsonify({
            "name": "Ram's News Portal",
            "short_name": "News Portal",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#0d0d0f",
            "theme_color": "#0d0d0f",
            "icons": [
                {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"},
            ],
        })

    @app.route("/refresh", methods=["POST"])
    def refresh():
        try:
            from scheduler import run_pipeline
            return run_pipeline()
        except Exception as exc:
            logger.error("Refresh failed: %s", exc)
            return {"status": "error", "message": str(exc)}, 500

    return app
