from kalshi_dashboard.db.init_db import init_db
from kalshi_dashboard.db.session import SessionLocal
from kalshi_dashboard.services.alerts import evaluate_alerts

if __name__ == '__main__':
    init_db()
    with SessionLocal() as db:
        events = evaluate_alerts(db)
    print(f'Triggered {len(events)} alert events')
