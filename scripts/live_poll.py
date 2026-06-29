"""Reliable read-only live-price updater using the public Kalshi REST feed."""

import sys
import time
from pathlib import Path

# Lets a beginner run this script directly on Windows without PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))

from kalshi_dashboard.db.init_db import init_db
from kalshi_dashboard.services.ingest import ingest_open_markets


INTERVAL_SECONDS = 60
# The full catalogue is loaded from the dashboard. This smaller batch keeps
# the recurring updater quick enough to create dependable one-minute history.
LIVE_UPDATE_LIMIT = 2_500


if __name__ == '__main__':
    init_db()
    print(f'Live price updater running. Refreshes {LIVE_UPDATE_LIMIT:,} public market quotes every 60 seconds. Press Ctrl+C to stop.')
    while True:
        started = time.monotonic()
        try:
            count = ingest_open_markets(limit=LIVE_UPDATE_LIMIT, use_public_api=True)
            print(f'Updated {count:,} public markets.')
        except Exception as exc:
            print(f'Update failed: {exc}. Retrying in {INTERVAL_SECONDS} seconds.')
        # Count fetch and database time toward the one-minute interval.
        time.sleep(max(0, INTERVAL_SECONDS - (time.monotonic() - started)))
