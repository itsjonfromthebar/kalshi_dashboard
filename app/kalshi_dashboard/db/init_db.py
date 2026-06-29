from sqlalchemy import inspect, text

from kalshi_dashboard.db.session import Base, engine
from kalshi_dashboard.db import models  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    # SQLite does not add new columns when create_all runs against an existing
    # database. This tiny migration keeps local installations up to date.
    additions = {
        'markets': {'no_bid': 'INTEGER'},
        'price_snapshots': {'category': 'VARCHAR(128)', 'no_bid': 'INTEGER'},
    }
    inspector = inspect(engine)
    missing = [
        (table, name, sql_type)
        for table, columns in additions.items()
        for name, sql_type in columns.items()
        if name not in {column['name'] for column in inspector.get_columns(table)}
    ]
    snapshot_indexes = {index['name'] for index in inspector.get_indexes('price_snapshots')}
    needs_snapshot_lookup_index = 'ix_price_snapshots_ticker_ts' not in snapshot_indexes
    # Do not open a write transaction on each Streamlit rerun. This block only
    # runs once for an older local database that genuinely needs new columns.
    if not missing and not needs_snapshot_lookup_index:
        return
    with engine.begin() as connection:
        for table, name, sql_type in missing:
            connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {sql_type}'))
        if missing:
            # Give existing local demo/history rows the newly displayed context.
            connection.execute(text("""
                UPDATE price_snapshots
                SET category = (
                    SELECT markets.category FROM markets
                    WHERE markets.ticker = price_snapshots.ticker
                )
                WHERE category IS NULL
            """))
            connection.execute(text("""
                UPDATE price_snapshots
                SET no_bid = 100 - yes_ask
                WHERE no_bid IS NULL AND yes_ask IS NOT NULL
            """))
        # Supports the grouped “latest/prior snapshot per ticker” lookup used
        # by Movers, keeping the tab fast as the local history grows.
        if needs_snapshot_lookup_index:
            connection.execute(text(
                'CREATE INDEX IF NOT EXISTS ix_price_snapshots_ticker_ts '
                'ON price_snapshots (ticker, ts)'
            ))


if __name__ == '__main__':
    init_db()
