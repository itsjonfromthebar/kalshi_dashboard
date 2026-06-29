from __future__ import annotations

from datetime import datetime, timedelta
from math import log1p
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from kalshi_dashboard.db.models import PriceSnapshot


def latest_snapshot_map(db: Session) -> dict[str, PriceSnapshot]:
    latest_subq = (
        select(PriceSnapshot.ticker, func.max(PriceSnapshot.ts).label('max_ts'))
        .group_by(PriceSnapshot.ticker)
        .subquery()
    )
    rows = db.execute(
        select(PriceSnapshot).join(
            latest_subq,
            (PriceSnapshot.ticker == latest_subq.c.ticker) & (PriceSnapshot.ts == latest_subq.c.max_ts),
        )
    ).scalars().all()
    return {r.ticker: r for r in rows}


def snapshot_at_or_before_map(db: Session, cutoff: datetime) -> dict[str, PriceSnapshot]:
    """Get one prior snapshot per market in a single query, not one per ticker."""
    prior_subq = (
        select(PriceSnapshot.ticker, func.max(PriceSnapshot.ts).label('prior_ts'))
        .where(PriceSnapshot.ts <= cutoff)
        .group_by(PriceSnapshot.ticker)
        .subquery()
    )
    rows = db.execute(
        select(PriceSnapshot).join(
            prior_subq,
            (PriceSnapshot.ticker == prior_subq.c.ticker) & (PriceSnapshot.ts == prior_subq.c.prior_ts),
        )
    ).scalars().all()
    return {row.ticker: row for row in rows}


def snapshot_near_target_map(
    db: Session,
    latest: dict[str, PriceSnapshot],
    target_time: datetime,
    tolerance: timedelta,
) -> dict[str, PriceSnapshot]:
    """Pick the closest real prior snapshot for each market near the target time.

    Fresh cloud deployments often collect snapshots a little before or after
    the exact 1-minute/1-hour mark. Choosing the closest earlier observation
    within tolerance keeps Movers populated without comparing against fake 0%
    baselines or very old stale rows.
    """
    if not latest:
        return {}

    earliest_allowed = target_time - tolerance
    latest_allowed = target_time + tolerance

    before_subq = (
        select(PriceSnapshot.ticker, func.max(PriceSnapshot.ts).label('candidate_ts'))
        .where(PriceSnapshot.ts >= earliest_allowed)
        .where(PriceSnapshot.ts <= target_time)
        .group_by(PriceSnapshot.ticker)
        .subquery()
    )
    after_subq = (
        select(PriceSnapshot.ticker, func.min(PriceSnapshot.ts).label('candidate_ts'))
        .where(PriceSnapshot.ts > target_time)
        .where(PriceSnapshot.ts <= latest_allowed)
        .group_by(PriceSnapshot.ticker)
        .subquery()
    )
    before_rows = db.execute(
        select(PriceSnapshot).join(
            before_subq,
            (PriceSnapshot.ticker == before_subq.c.ticker)
            & (PriceSnapshot.ts == before_subq.c.candidate_ts),
        )
    ).scalars().all()
    after_rows = db.execute(
        select(PriceSnapshot).join(
            after_subq,
            (PriceSnapshot.ticker == after_subq.c.ticker)
            & (PriceSnapshot.ts == after_subq.c.candidate_ts),
        )
    ).scalars().all()

    priors: dict[str, PriceSnapshot] = {}
    for row in [*before_rows, *after_rows]:
        current = latest.get(row.ticker)
        if not current or row.ts >= current.ts:
            continue
        if abs(row.ts - target_time) > tolerance:
            continue
        existing = priors.get(row.ticker)
        if existing is None or abs(row.ts - target_time) < abs(existing.ts - target_time):
            priors[row.ticker] = row
    return priors


def immediate_prior_snapshot_map(db: Session) -> dict[str, PriceSnapshot]:
    """Fallback for manual cloud syncs: latest row versus previous real row.

    Render users may click the public fetch button at uneven intervals. When
    there is no snapshot close to the selected horizon yet, this still lets
    Movers populate after two fetches while preserving the invalid-baseline
    checks in build_movers.
    """
    latest_subq = (
        select(PriceSnapshot.ticker, func.max(PriceSnapshot.ts).label('max_ts'))
        .group_by(PriceSnapshot.ticker)
        .subquery()
    )
    prior_subq = (
        select(PriceSnapshot.ticker, func.max(PriceSnapshot.ts).label('prior_ts'))
        .join(latest_subq, PriceSnapshot.ticker == latest_subq.c.ticker)
        .where(PriceSnapshot.ts < latest_subq.c.max_ts)
        .group_by(PriceSnapshot.ticker)
        .subquery()
    )
    rows = db.execute(
        select(PriceSnapshot).join(
            prior_subq,
            (PriceSnapshot.ticker == prior_subq.c.ticker)
            & (PriceSnapshot.ts == prior_subq.c.prior_ts),
        )
    ).scalars().all()
    return {row.ticker: row for row in rows}


def build_movers(
    db: Session,
    hours: int = 24,
    limit: int = 100,
    minutes: int | None = None,
) -> list[dict]:
    latest = latest_snapshot_map(db)
    if not latest:
        return []
    # Use the most recent saved batch as the reference point. This makes a
    # "1 minute" comparison independent of when the user opens the tab.
    reference_time = max(snapshot.ts for snapshot in latest.values())
    interval = timedelta(minutes=minutes) if minutes is not None else timedelta(hours=hours)
    target_time = reference_time - interval
    rows: list[dict] = []

    # Allow for collection-time drift without labeling an old observation as a
    # fresh 1-minute, 1-hour, or 24-hour move.
    interval_minutes = minutes if minutes is not None else hours * 60
    tolerance = timedelta(seconds=max(60, interval_minutes * 6))
    priors = snapshot_near_target_map(db, latest, target_time, tolerance)
    used_immediate_fallback = False
    if not priors:
        priors = immediate_prior_snapshot_map(db)
        used_immediate_fallback = True

    for ticker, cur in latest.items():
        prior = priors.get(ticker)
        # A mover needs two distinct, usable observations. In particular, a
        # zero prior is an unpriced/invalid baseline, not a real 0% forecast.
        if not prior or prior.ts >= cur.ts:
            continue
        if cur.probability is None or prior.probability is None:
            continue
        prior_probability = float(prior.probability)
        current_probability = float(cur.probability)
        if prior_probability <= 0.0 or prior_probability > 1.0:
            continue
        if current_probability < 0.0 or current_probability > 1.0:
            continue
        observed_gap = cur.ts - prior.ts
        # For exact horizon matches, reject stale comparisons. If we had to use
        # the immediate-prior fallback, allow the comparison so a fresh cloud app
        # begins populating Movers after two manual public syncs.
        if observed_gap <= timedelta(0):
            continue
        if not used_immediate_fallback and observed_gap > interval + tolerance:
            continue

        change = current_probability - prior_probability
        volume_change = None
        if cur.volume is not None and prior.volume is not None:
            volume_change = cur.volume - prior.volume
        row = {
            'ticker': ticker,
            'probability': current_probability,
            'prior_probability': prior_probability,
            'change': change,
            'change_points': change * 100,
            'volume': cur.volume,
            'volume_change': volume_change,
            'liquidity': cur.liquidity,
            'latest_ts': cur.ts,
            'prior_ts': prior.ts,
        }
        row['opportunity_score'] = opportunity_score(row)
        rows.append(row)

    # Use the balanced score—not raw magnitude—to rank the scan.
    rows.sort(key=lambda row: (row['opportunity_score'], abs(row['change_points'])), reverse=True)
    return rows[:limit]


def opportunity_score(row: dict) -> float:
    """Return a 0–100 normalized research ranking for a valid market move.

    Formula: 45% move magnitude (capped at 20 points), 25% current volume,
    15% current liquidity, and 15% uncertainty. Volume and liquidity use a
    log scale capped at 100,000; uncertainty is highest near a 50% midpoint.
    This prevents one giant raw move or one huge market from dominating.
    """
    move_points = abs(float(row.get('change_points') or 0))
    volume = max(float(row.get('volume') or 0), 0)
    liquidity = max(float(row.get('liquidity') or 0), 0)
    prior_probability = float(row.get('prior_probability') or 0)
    probability = float(row.get('probability') or 0)
    midpoint = (prior_probability + probability) / 2

    move_component = min(move_points / 20.0, 1.0)
    volume_component = min(log1p(volume) / log1p(100_000), 1.0)
    liquidity_component = min(log1p(liquidity) / log1p(100_000), 1.0)
    uncertainty_component = max(0.0, 1.0 - (abs(midpoint - 0.5) / 0.5))

    return round(100 * (
        0.45 * move_component
        + 0.25 * volume_component
        + 0.15 * liquidity_component
        + 0.15 * uncertainty_component
    ), 2)
