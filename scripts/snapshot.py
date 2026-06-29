from kalshi_dashboard.db.init_db import init_db
from kalshi_dashboard.services.ingest import ingest_open_markets

if __name__ == '__main__':
    init_db()
    count = ingest_open_markets()
    print(f'Saved {count} open market snapshots')
