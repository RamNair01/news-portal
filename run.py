"""Entrypoint — starts Flask + APScheduler together."""

import logging
import os

import yaml
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

from scheduler import create_scheduler, get_refresh_times
from server.app import create_app

if __name__ == "__main__":
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)

    port = config.get("server", {}).get("port", 5000)
    debug = config.get("server", {}).get("debug", False)

    # When debug/reloader is on, Werkzeug forks the process — only start the
    # scheduler in the child (reloader main) to avoid it running twice.
    reloader_active = debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true"
    if not reloader_active:
        scheduler = create_scheduler()
        scheduler.start()
        logging.getLogger(__name__).info(
            "Scheduler started — news refreshes at %s Amsterdam time.",
            ", ".join(get_refresh_times(config)),
        )
    else:
        scheduler = None

    app = create_app()
    try:
        app.run(host="127.0.0.1", port=port, debug=debug, use_reloader=debug)
    finally:
        if scheduler:
            scheduler.shutdown()
