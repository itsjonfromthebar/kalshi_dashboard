"""Run the local read-only public ticker listener."""

import sys
from pathlib import Path

# Lets a beginner run this script directly on Windows without PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))

from kalshi_dashboard.db.init_db import init_db
from kalshi_dashboard.services.live_feed import run_public_live_feed


if __name__ == '__main__':
    init_db()
    run_public_live_feed()
