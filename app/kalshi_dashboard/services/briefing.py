from __future__ import annotations

from datetime import datetime
from pathlib import Path
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from kalshi_dashboard.db.models import AlertEvent, WatchlistItem, PriceSnapshot
from kalshi_dashboard.services.analytics import build_movers, opportunity_score


def generate_markdown_brief(db: Session, output_dir: str = 'briefings') -> Path:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    now = datetime.utcnow()
    movers = build_movers(db, hours=24, limit=10)
    alerts = db.execute(select(AlertEvent).order_by(desc(AlertEvent.triggered_at)).limit(10)).scalars().all()
    watchlist = db.execute(select(WatchlistItem)).scalars().all()

    lines = [
        '# Kalshi Daily Brief',
        '',
        f'Generated UTC: {now:%Y-%m-%d %H:%M}',
        '',
        '## Top 24h Movers',
        '',
        '| Ticker | Current | 24h Change | Volume Change | Score |',
        '|---|---:|---:|---:|---:|',
    ]
    for r in movers:
        lines.append(
            f"| {r['ticker']} | {r['probability']:.1%} | {r['change_points']:+.1f} pts | {r.get('volume_change') or 0} | {opportunity_score(r)} |"
        )
    lines += ['', '## Recent Alerts', '']
    if alerts:
        for a in alerts:
            lines.append(f'- {a.triggered_at:%Y-%m-%d %H:%M}: {a.message}')
    else:
        lines.append('- No alerts triggered yet.')

    lines += ['', '## Watchlist Snapshot', '']
    if watchlist:
        for item in watchlist:
            snap = db.execute(
                select(PriceSnapshot).where(PriceSnapshot.ticker == item.ticker).order_by(desc(PriceSnapshot.ts)).limit(1)
            ).scalar_one_or_none()
            prob = f'{snap.probability:.1%}' if snap and snap.probability is not None else 'no data'
            lines.append(f'- {item.ticker}: {prob} — {item.note or ""}')
    else:
        lines.append('- Watchlist is empty.')

    path = Path(output_dir) / f'kalshi_brief_{now:%Y%m%d_%H%M}.md'
    path.write_text('\n'.join(lines), encoding='utf-8')
    return path
