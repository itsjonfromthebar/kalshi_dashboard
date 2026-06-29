import time
from apscheduler.schedulers.background import BackgroundScheduler

from kalshi_dashboard.config import get_settings
from kalshi_dashboard.db.init_db import init_db
from kalshi_dashboard.db.session import SessionLocal
from kalshi_dashboard.services.alerts import evaluate_alerts
from kalshi_dashboard.services.ingest import ingest_open_markets


def job():
    count = ingest_open_markets()
    with SessionLocal() as db:
        events = evaluate_alerts(db)
    print(f'Snapshot complete: {count} markets; alerts triggered: {len(events)}')


if __name__ == '__main__':
    settings = get_settings()
    init_db()
    scheduler = BackgroundScheduler()
    scheduler.add_job(job, 'interval', minutes=settings.snapshot_interval_minutes)
    scheduler.start()
    job()
    print('Scheduler running. Press Ctrl+C to stop.')
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.shutdown()
