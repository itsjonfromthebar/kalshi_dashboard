"""Small local dataset so the dashboard is useful before any API setup."""

from datetime import datetime, timedelta

from sqlalchemy import select

from kalshi_dashboard.db.models import Market, PriceSnapshot
from kalshi_dashboard.db.session import SessionLocal


DEMO_MARKETS = [
    ('KXWC26-CHAMP-USA', 'Will the United States win the 2026 World Cup?', 'Sports', 18, 24, 185000, 92000),
    ('KXWC26-CHAMP-ARG', 'Will Argentina win the 2026 World Cup?', 'Sports', 13, 17, 162000, 84000),
    ('KXNYC-MAYOR-DEM', 'Will the Democratic nominee win the NYC mayoral election?', 'Politics', 58, 64, 241000, 118000),
    ('KXNYC-RENT-UP', 'Will median NYC rent rise this year?', 'Economy', 42, 37, 97000, 55000),
    ('KXFED-RATE-CUT', 'Will the Fed cut rates at the next meeting?', 'Economy', 46, 51, 315000, 141000),
    ('KXTEMP-NYC-90', 'Will NYC reach 90F this week?', 'Climate', 31, 39, 76000, 43000),
]


def seed_demo_data(force: bool = False) -> int:
    """Create deterministic-looking historical samples once in the local SQLite DB."""
    with SessionLocal() as db:
        if not force and db.execute(select(Market.ticker).limit(1)).first():
            return 0
        now = datetime.utcnow().replace(second=0, microsecond=0)
        offsets = [timedelta(days=7), timedelta(days=1), timedelta(hours=1), timedelta()]
        for index, (ticker, title, category, old_price, latest_price, volume, liquidity) in enumerate(DEMO_MARKETS):
            market = Market(
                ticker=ticker, title=title, category=category, status='open',
                yes_bid=max(latest_price - 1, 1), no_bid=max(99 - latest_price, 1), yes_ask=min(latest_price + 1, 99),
                last_price=latest_price, volume=volume, liquidity=liquidity,
                close_time='Demo data — not a live market', updated_at=now,
            )
            db.merge(market)
            prices = [old_price, old_price + (latest_price - old_price) // 3, old_price + 2 * (latest_price - old_price) // 3, latest_price]
            for point, price in zip(offsets, prices):
                db.add(PriceSnapshot(
                    ticker=ticker, ts=now - point, category=category, probability=price / 100,
                    yes_bid=max(price - 1, 1), no_bid=max(99 - price, 1), yes_ask=min(price + 1, 99), last_price=price,
                    volume=max(volume - int(point.total_seconds() / 3600) * (500 + index * 40), 0), liquidity=liquidity,
                ))
        db.commit()
    return len(DEMO_MARKETS)
