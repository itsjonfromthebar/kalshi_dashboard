from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from kalshi_dashboard.config import get_settings
from kalshi_dashboard.db.models import PriceSnapshot


def prune_old_price_snapshots(db: Session, now: datetime | None = None) -> int:
    """Delete stored price snapshots older than the configured retention window.

    The dashboard only needs recent snapshots for Movers. Keeping this as a
    rolling 24-hour window prevents SQLite from growing into multi-GB history.
    Market Explorer still keeps the latest market quote in the markets table.
    """
    settings = get_settings()
    retention_hours = max(int(settings.snapshot_retention_hours or 24), 1)
    cutoff = (now or datetime.utcnow()) - timedelta(hours=retention_hours)
    result = db.execute(delete(PriceSnapshot).where(PriceSnapshot.ts < cutoff))
    return int(result.rowcount or 0)
