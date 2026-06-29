from datetime import datetime
from sqlalchemy import delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from kalshi_dashboard.api.client import KalshiClient
from kalshi_dashboard.config import get_settings
from kalshi_dashboard.db.models import Market, PriceSnapshot
from kalshi_dashboard.db.session import SessionLocal
from kalshi_dashboard.services.demo_data import seed_demo_data


def _legacy_market_category(m: dict) -> str:
    """Use Kalshi's category when present; otherwise provide a useful local grouping."""
    # Multi-leg sports markets occasionally arrive tagged with an unrelated
    # top-level category, while their ticker is unambiguous.
    if 'MVESPORT' in str(m.get('ticker') or '').upper():
        return 'Sports'
    if m.get('category'):
        return str(m['category']).title()
    text = ' '.join(str(m.get(key) or '') for key in ('ticker', 'title', 'subtitle')).lower()
    groups = {
        'Sports': ('sport', 'kxitf', 'kxatp', 'nfl', 'nba', 'mlb', 'nhl', 'soccer', 'football', 'basketball', 'baseball', 'world cup', 'ufc', 'golf', 'tennis'),
        'Politics': ('election', 'president', 'congress', 'senate', 'governor', 'mayor', 'democrat', 'republican', 'warnock'),
        'Economy': ('fed', 'rate', 'inflation', 'gdp', 'jobs', 'unemployment', 'recession', 'tariff'),
        'Crypto': ('bitcoin', 'btc', 'ethereum', 'crypto'),
        'Weather': ('temperature', 'weather', 'rain', 'snow', 'hurricane', 'degrees', '°'),
        'Entertainment': ('oscar', 'grammy', 'movie', 'album', 'box office', 'celebrity'),
    }
    for category, keywords in groups.items():
        if any(keyword in text for keyword in keywords):
            return category
    return 'Other'


def market_category(m: dict) -> str:
    """Assign an Explorer-friendly, topic-level category to every market."""
    ticker = str(m.get('ticker') or '').upper()
    text = ' '.join(str(m.get(key) or '') for key in ('title', 'subtitle')).lower()

    # Ticker families are more reliable and more granular than broad labels
    # such as "Sports" or "Politics" supplied by the public feed.
    ticker_groups = (
        ('KXWNBA', 'Sports · WNBA'), ('KXNBA', 'Sports · NBA'),
        ('KXNFL', 'Sports · NFL'), ('KXNHL', 'Sports · NHL'),
        ('KXMLB', 'Sports · MLB'), ('KXITF', 'Sports · Tennis'),
        ('KXATP', 'Sports · Tennis'), ('KXWTA', 'Sports · Tennis'),
        ('KXTHEWEEKNIGHT', 'Politics · US media mentions'),
        ('KXALLIN', 'Politics · US media mentions'),
        ('KXFED', 'Economy · Federal Reserve'),
        ('KXBTC', 'Crypto · Bitcoin'), ('KXETH', 'Crypto · Ethereum'),
    )
    for prefix, category in ticker_groups:
        if ticker.startswith(prefix):
            return category
    if 'MVESPORT' in ticker:
        return 'Sports · Multi-leg'

    keyword_groups = (
        (('election', 'president', 'congress', 'senate', 'governor', 'mayor', 'democrat', 'republican'), 'Politics · Elections'),
        (('federal reserve', 'fed ', 'interest rate', 'inflation', 'gdp', 'unemployment', 'recession', 'tariff'), 'Economy · Macro'),
        (('bitcoin', 'crypto', 'ethereum'), 'Crypto · Digital assets'),
        (('temperature', 'weather', 'rain', 'snow', 'hurricane'), 'Weather · Forecasts'),
        (('oscar', 'grammy', 'movie', 'album', 'box office', 'celebrity'), 'Entertainment · Culture'),
        (('soccer', 'football', 'world cup'), 'Sports · Soccer'),
        (('basketball',), 'Sports · Basketball'),
        (('baseball',), 'Sports · Baseball'),
    )
    for keywords, category in keyword_groups:
        if any(keyword in text for keyword in keywords):
            return category

    source_category = str(m.get('category') or '').strip().title()
    if source_category and source_category not in {'Other', 'Sports', 'Politics', 'Economy'}:
        return source_category
    if source_category:
        return f'{source_category} · General'
    return 'Other · General'


def _quote_cents(m: dict, field: str) -> int | None:
    """Read both legacy cents fields and the current API dollar-string fields."""
    value = m.get(field)
    if value is not None:
        return int(round(float(value)))
    dollar_value = m.get(f'{field}_dollars')
    if dollar_value is not None:
        return int(round(float(dollar_value) * 100))
    return None


def _quantity(m: dict, field: str) -> int | None:
    """Volumes/liquidity can arrive as integers or fixed-point strings."""
    for key in (field, f'{field}_fp'):
        if m.get(key) is not None:
            return int(float(m[key]))
    # Liquidity is sometimes returned as a dollar string rather than cents.
    if field == 'liquidity' and m.get('liquidity_dollars') is not None:
        return int(round(float(m['liquidity_dollars']) * 100))
    return None


def _probability(m: dict) -> float | None:
    for field in ('last_price', 'yes_ask', 'yes_bid'):
        value = _quote_cents(m, field)
        if value is not None:
            return value / 100.0
    return None


def _no_bid(m: dict) -> int | None:
    """Use the direct API value, with a best-effort quote-derived fallback."""
    value = _quote_cents(m, 'no_bid')
    if value is not None:
        return value
    yes_ask = _quote_cents(m, 'yes_ask')
    if yes_ask is not None:
        return 100 - yes_ask
    return None


def upsert_market(db: Session, m: dict, captured_at: datetime | None = None) -> None:
    payload = {
        'ticker': m.get('ticker'),
        'event_ticker': m.get('event_ticker'),
        'series_ticker': m.get('series_ticker'),
        'title': m.get('title'),
        'subtitle': m.get('subtitle'),
        'category': market_category(m),
        'status': m.get('status'),
        'yes_bid': _quote_cents(m, 'yes_bid'),
        'no_bid': _no_bid(m),
        'yes_ask': _quote_cents(m, 'yes_ask'),
        'last_price': _quote_cents(m, 'last_price'),
        'volume': _quantity(m, 'volume'),
        'liquidity': _quantity(m, 'liquidity'),
        'close_time': str(m.get('close_time')) if m.get('close_time') else None,
        'updated_at': captured_at or datetime.utcnow(),
    }
    if not payload['ticker']:
        return

    stmt = sqlite_insert(Market).values(**payload)
    # Ticker messages often contain only quote fields. Preserve descriptive
    # fields already loaded from the REST market catalogue when absent.
    updates = {key: value for key, value in payload.items() if key != 'ticker' and value is not None}
    updates['updated_at'] = payload['updated_at']
    stmt = stmt.on_conflict_do_update(index_elements=['ticker'], set_=updates)
    db.execute(stmt)


def ingest_open_markets(
    limit: int | None = None,
    use_public_api: bool = False,
    include_combos: bool = False,
) -> int:
    settings = get_settings()
    # A first launch should work offline and never require a key file. The UI
    # can explicitly opt into the public market feed, which has no credentials.
    if not settings.has_api_credentials and not use_public_api:
        return seed_demo_data()
    base_url = settings.public_market_base_url if use_public_api else settings.base_url
    client = KalshiClient(base_url, settings.kalshi_api_key_id, settings.kalshi_private_key_path)
    # Build a broad local catalogue. The previous 2,500-row cap could omit
    # otherwise available matchups from the public market feed.
    limit = limit or (max(settings.public_market_limit, settings.snapshot_limit) if use_public_api else settings.snapshot_limit)
    markets: list[dict] = []
    cursor: str | None = None
    # The API returns markets in pages. Keeping pages modest avoids a huge
    # response while still letting a non-developer load a broad local search index.
    while len(markets) < limit:
        page_size = min(1_000, limit - len(markets))
        data = client.get_markets(
            status='open',
            limit=page_size,
            cursor=cursor,
            mve_filter=None if include_combos else 'exclude',
        )
        page = data.get('markets', [])
        markets.extend(page)
        cursor = data.get('cursor')
        if not page or not cursor:
            break

    # One shared capture time makes the historical intervals meaningful; it
    # represents when this complete public-market batch was received locally.
    captured_at = datetime.utcnow()
    with SessionLocal() as db:
        if use_public_api and not include_combos:
            # Remove stale multi-leg rows from the earlier broad starter feed.
            db.execute(delete(PriceSnapshot).where(PriceSnapshot.ticker.like('KXMVE%')))
            db.execute(delete(Market).where(Market.ticker.like('KXMVE%')))
        for m in markets:
            upsert_market(db, m, captured_at=captured_at)
            db.add(PriceSnapshot(
                ticker=m.get('ticker'),
                ts=captured_at,
                category=market_category(m),
                probability=_probability(m),
                yes_bid=_quote_cents(m, 'yes_bid'),
                no_bid=_no_bid(m),
                yes_ask=_quote_cents(m, 'yes_ask'),
                last_price=_quote_cents(m, 'last_price'),
                volume=_quantity(m, 'volume'),
                liquidity=_quantity(m, 'liquidity'),
            ))
        db.commit()
    return len(markets)
