from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from kalshi_dashboard.db.models import Alert, AlertEvent, PriceSnapshot


def _already_triggered_recently(db: Session, alert_id: int, minutes: int = 60) -> bool:
    cutoff = datetime.utcnow() - timedelta(minutes=minutes)
    existing = db.execute(
        select(AlertEvent)
        .where(AlertEvent.alert_id == alert_id, AlertEvent.triggered_at >= cutoff)
        .limit(1)
    ).scalar_one_or_none()
    return existing is not None


def evaluate_alerts(db: Session) -> list[AlertEvent]:
    created: list[AlertEvent] = []
    alerts = db.execute(select(Alert).where(Alert.enabled == 1)).scalars().all()
    for alert in alerts:
        snap = db.execute(
            select(PriceSnapshot)
            .where(PriceSnapshot.ticker == alert.ticker)
            .order_by(desc(PriceSnapshot.ts))
            .limit(1)
        ).scalar_one_or_none()
        if not snap or snap.probability is None:
            continue
        triggered = False
        if alert.kind == 'above' and snap.probability >= alert.threshold:
            triggered = True
        elif alert.kind == 'below' and snap.probability <= alert.threshold:
            triggered = True
        if triggered and not _already_triggered_recently(db, alert.id):
            msg = f'{alert.ticker} is {snap.probability:.1%}, {alert.kind} {alert.threshold:.1%}'
            ev = AlertEvent(alert_id=alert.id, ticker=alert.ticker, message=msg)
            db.add(ev)
            created.append(ev)
    db.commit()
    return created
