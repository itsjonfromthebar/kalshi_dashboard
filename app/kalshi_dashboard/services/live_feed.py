"""Read-only public Kalshi ticker listener that records local SQLite history."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime

import websocket
from sqlalchemy import select

from kalshi_dashboard.config import get_settings
from kalshi_dashboard.db.models import Market, PriceSnapshot
from kalshi_dashboard.db.session import SessionLocal
from kalshi_dashboard.services.ingest import _no_bid, _probability, _quantity, _quote_cents, upsert_market

LOG = logging.getLogger(__name__)
SUBSCRIPTION_BATCH_SIZE = 100


def tracked_open_tickers() -> list[str]:
    """Tickers come from the public REST sync, which runs before the feed."""
    with SessionLocal() as db:
        return list(db.execute(
            select(Market.ticker).where(Market.status == 'open').order_by(Market.ticker)
        ).scalars())


def _ticker_message(message: dict) -> dict | None:
    """Extract the ticker body from Kalshi WebSocket envelopes."""
    if message.get('type') != 'ticker':
        return None
    ticker = dict(message.get('msg') or {})
    if ticker.get('market_ticker') and not ticker.get('ticker'):
        ticker['ticker'] = ticker['market_ticker']
    return ticker if ticker.get('ticker') else None


def record_ticker_update(message: dict) -> None:
    """Store one received quote, retaining market metadata from the REST sync."""
    ticker = _ticker_message(message)
    if not ticker:
        return
    with SessionLocal() as db:
        existing = db.get(Market, ticker['ticker'])
        upsert_market(db, ticker)
        db.add(PriceSnapshot(
            ticker=ticker['ticker'],
            category=ticker.get('category') or (existing.category if existing else None),
            probability=_probability(ticker),
            yes_bid=_quote_cents(ticker, 'yes_bid'),
            no_bid=_no_bid(ticker),
            yes_ask=_quote_cents(ticker, 'yes_ask'),
            last_price=_quote_cents(ticker, 'last_price'),
            volume=_quantity(ticker, 'volume'),
            liquidity=_quantity(ticker, 'liquidity'),
            ts=datetime.utcnow(),
        ))
        db.commit()


def run_public_live_feed() -> None:
    """Reconnect forever. Stop from its terminal with Ctrl+C."""
    settings = get_settings()
    tickers = tracked_open_tickers()
    if not tickers:
        raise RuntimeError('No open markets are stored yet. First use “Fetch public live markets” in the dashboard.')

    print(f'Listening for public ticker updates on {len(tickers):,} markets. Press Ctrl+C to stop.')
    while True:
        try:
            ws = websocket.create_connection(settings.public_websocket_url, timeout=30)
            for index in range(0, len(tickers), SUBSCRIPTION_BATCH_SIZE):
                ws.send(json.dumps({
                    'id': index // SUBSCRIPTION_BATCH_SIZE + 1,
                    'cmd': 'subscribe',
                    'params': {
                        'channels': ['ticker'],
                        'market_tickers': tickers[index:index + SUBSCRIPTION_BATCH_SIZE],
                    },
                }))
            while True:
                raw = ws.recv()
                if raw:
                    record_ticker_update(json.loads(raw))
        except KeyboardInterrupt:
            print('Live feed stopped.')
            return
        except Exception as exc:
            LOG.warning('Live feed disconnected (%s). Retrying in 5 seconds.', exc)
            print(f'Live feed disconnected: {exc}. Retrying in 5 seconds…')
            time.sleep(5)
