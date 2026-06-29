from __future__ import annotations

import hmac
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

PACKAGE_DIR = Path(__file__).resolve().parent / 'app'
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import select, desc

from kalshi_dashboard.api.client import KalshiClient
from kalshi_dashboard.config import get_settings
from kalshi_dashboard.db.init_db import init_db
from kalshi_dashboard.db.models import Alert, AlertEvent, Market, PriceSnapshot, WatchlistItem
from kalshi_dashboard.db.session import SessionLocal
from kalshi_dashboard.services.alerts import evaluate_alerts
from kalshi_dashboard.services.analytics import build_movers, opportunity_score
from kalshi_dashboard.services.briefing import generate_markdown_brief
from kalshi_dashboard.services.ingest import ingest_open_markets, market_category
from kalshi_dashboard.services.demo_data import seed_demo_data
@st.cache_data(ttl=60, show_spinner="Scanning snapshots…")
def get_movers(minutes: int, limit: int = 200):
    with SessionLocal() as db:
        return build_movers(db, minutes=minutes, limit=limit)

# ============================================================ PAGE / THEME
st.set_page_config(page_title='Live Odds', layout='wide',
                   initial_sidebar_state='collapsed')

st.markdown('''
<style>
  :root { --bg:#080c12; --panel:#101722; --panel-2:#141e2b; --line:#2b3949;
          --text:#e7edf4; --muted:#91a0b1; --accent:#f2a93b; --cyan:#56c8d8; }
  html, body, [class*="css"] { font-family:Inter, "Segoe UI", Arial, sans-serif; }
  .stApp { background:var(--bg); color:var(--text); }
  .block-container { padding:0.75rem 1.15rem 1.4rem; max-width:100%; }
  .workspace-header { display:flex; align-items:center; justify-content:space-between;
      padding:0.3rem 0 0.85rem; border-bottom:1px solid var(--line); margin-bottom:0.85rem; }
  .workspace-brand { color:var(--text); font-weight:800; font-size:1.1rem; letter-spacing:.11em; }
  .workspace-brand span { color:var(--accent); }
  .workspace-meta { color:var(--muted); font:600 .66rem "SFMono-Regular", Consolas, monospace;
      letter-spacing:.08em; text-transform:uppercase; }
  .stApp h1, .stApp h2, .stApp h3 {
      color:var(--text); font-size:1rem !important; margin:.35rem 0 .5rem !important;
      font-weight:750; letter-spacing:.01em; }
  .stApp label, .stApp p { color:var(--text); }
  .stApp [data-testid="stCaptionContainer"] { color:var(--muted); }
  .stDataFrame, [data-testid="stDataFrame"] { font-size:.8rem; }
  div[data-testid="stMetric"] { background:var(--panel); padding:8px 11px;
      border:1px solid var(--line); border-radius:3px; }
  [data-testid="stMetricLabel"] { color:var(--muted) !important; font-size:.7rem !important;
      text-transform:uppercase; letter-spacing:.045em; }
  [data-testid="stMetricValue"] { color:var(--text) !important; font-family:"SFMono-Regular", Consolas, monospace; }
  .stTabs [data-baseweb="tab-list"] { gap:.2rem; border-bottom:1px solid var(--line); }
  .stTabs [data-baseweb="tab"] { color:var(--muted); font-weight:700; font-size:.78rem;
      padding:.55rem .8rem; }
  .stTabs [aria-selected="true"] { color:var(--text) !important; background:var(--panel); }
  .stTabs [data-baseweb="tab-highlight"] { background:var(--accent) !important; height:2px !important; }
  [data-testid="stDataFrame"] [role="columnheader"] { font-weight:800 !important; color:#dce6ef !important;
      background:#121b27 !important; }
  [data-testid="stSidebar"] { background:#0c1119; border-right:1px solid var(--line); }
  [data-testid="stSidebar"] .stButton button, .stButton button { border:1px solid #3b5062;
      background:#172433; color:var(--text); border-radius:3px; font-weight:650; }
  [data-testid="stSidebar"] .stButton button:hover, .stButton button:hover { border-color:var(--cyan);
      color:#fff; background:#1c3042; }
  [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input { background:#0d131c;
      color:var(--text); border-color:#344657; border-radius:3px; }
  [data-testid="stExpander"] { border:1px solid var(--line); border-radius:3px; background:var(--panel); }
  footer, #MainMenu { visibility:hidden; }
</style>''', unsafe_allow_html=True)

settings = get_settings()


def require_login() -> None:
    """Small password gate for personal deployments.

    Render should provide APP_USERNAME and APP_PASSWORD as environment
    variables. That keeps the real password out of GitHub.
    """
    if not settings.login_enabled:
        return

    if settings.app_auth_required and not settings.app_password:
        st.error('Login is turned on, but APP_PASSWORD is not set.')
        st.info('Set APP_PASSWORD in your cloud environment variables, then redeploy.')
        st.stop()

    if st.session_state.get('authenticated'):
        with st.sidebar:
            st.caption(f"Signed in as {settings.app_username}")
            if st.button('Log out', use_container_width=True):
                st.session_state.pop('authenticated', None)
                st.rerun()
        return

    st.markdown(
        "<div style='max-width:420px;margin:9vh auto 0;padding:24px;"
        "background:#101722;border:1px solid #2b3949;border-radius:6px;'>"
        "<div style='color:#f2a93b;font-weight:900;letter-spacing:.12em;"
        "font-size:1.15rem;margin-bottom:4px;'>LIVE ODDS</div>"
        "<div style='color:#91a0b1;font-size:.8rem;margin-bottom:18px;'>"
        "Private market dashboard login</div>",
        unsafe_allow_html=True,
    )
    with st.form('login_form'):
        username = st.text_input('Username')
        password = st.text_input('Password', type='password')
        submitted = st.form_submit_button('Log in', use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if submitted:
        username_ok = hmac.compare_digest(username.strip(), settings.app_username)
        password_ok = hmac.compare_digest(password, settings.app_password or '')
        if username_ok and password_ok:
            st.session_state['authenticated'] = True
            st.rerun()
        st.error('Wrong username or password.')
    st.stop()


require_login()
init_db()
if not settings.has_api_credentials:
    seed_demo_data()

st.markdown(
    "<div class='workspace-header'><div class='workspace-brand'>LIVE <span>ODDS</span></div>"
    "<div class='workspace-meta'>Market intelligence workspace</div></div>",
    unsafe_allow_html=True,
)

# ============================================================ HELPERS
def cents_to_prob(v):
    return None if v is None else v / 100

EASTERN_TIME = ZoneInfo('America/New_York')

def eastern_snapshot_time(value) -> str:
    """SQLite stores UTC; show local Eastern time with an explicit label."""
    if pd.isna(value):
        return '—'
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize('UTC')
    return timestamp.tz_convert(EASTERN_TIME).strftime('%b %d, %I:%M %p ET').replace(' 0', ' ')

def short_ticker(ticker: str | None) -> str:
    ticker = ticker or ''
    return ticker if len(ticker) <= 18 else f'{ticker[:10]}…{ticker[-6:]}'

def friendly_title(ticker: str | None, title: str | None) -> str:
    title = title or 'Untitled market'
    if (ticker or '').startswith('KXMVE'):
        legs = [leg.strip() for leg in title.split(',') if leg.strip()]
        preview = ' · '.join(legs[:3])
        remainder = f' + {len(legs) - 3} more' if len(legs) > 3 else ''
        return f'Multi-leg combo ({len(legs)} legs): {preview}{remainder}'
    return title

def current_probability(last_price, yes_bid, yes_ask):
    if yes_bid is not None and yes_ask is not None:
        return (yes_bid + yes_ask) / 200
    return cents_to_prob(last_price if last_price is not None else (yes_ask if yes_ask is not None else yes_bid))

def markets_df(limit: int = 10_000) -> pd.DataFrame:
    with SessionLocal() as db:
        rows = db.execute(select(Market).order_by(desc(Market.updated_at)).limit(limit)).scalars().all()
    return pd.DataFrame([{
        'ticker': r.ticker,
        'title': r.title,
        'display_title': friendly_title(r.ticker, r.title),
        'category': market_category({'ticker': r.ticker, 'title': r.title, 'subtitle': r.subtitle, 'category': r.category}),
        'status': r.status,
        'probability': current_probability(r.last_price, r.yes_bid, r.yes_ask),
        'yes_bid': r.yes_bid,
        'no_bid': r.no_bid,
        'yes_ask': r.yes_ask,
        'last_price': r.last_price,
        'volume': r.volume,
        'liquidity': r.liquidity,
        'close_time': r.close_time,
        'updated_at': r.updated_at,
    } for r in rows])

def add_watchlist(ticker: str, note: str = '') -> None:
    with SessionLocal() as db:
        existing = db.get(WatchlistItem, ticker.strip().upper())
        if not existing:
            db.add(WatchlistItem(ticker=ticker.strip().upper(), note=note))
        elif note:
            existing.note = note
        db.commit()

def chg_color(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 'color:#888'
    return 'color:#26C281' if v > 0 else 'color:#ED4337' if v < 0 else 'color:#888'

def show_market_details(row: pd.Series) -> None:
    st.subheader(str(row.get('display_title') or row.get('title') or 'Selected market'))
    st.caption(f"{row.get('category') or 'Other'} · {short_ticker(row.get('ticker'))} · Full ticker: {row.get('ticker', '')}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Category', row.get('category') or '—')
    c2.metric('Probability', f"{row['probability']:.1%}" if pd.notna(row.get('probability')) else '—')
    c3.metric('Yes bid', f"{row['yes_bid']}¢" if pd.notna(row.get('yes_bid')) else '—')
    c4.metric('No bid', f"{row['no_bid']}¢" if pd.notna(row.get('no_bid')) else '—')
    c5, c6, c7 = st.columns(3)
    c5.metric('Last price', f"{row['last_price']}¢" if pd.notna(row.get('last_price')) else '—')
    c6.metric('Volume', f"{row['volume']:,}" if pd.notna(row.get('volume')) else '—')
    c7.metric('Liquidity', f"{row['liquidity']:,}" if pd.notna(row.get('liquidity')) else '—')

# ============================================================ SIDEBAR
with st.sidebar:
    st.header('Controls')
    st.caption('Local demo plus public market search' if not settings.has_api_credentials else f'Kalshi environment: {settings.kalshi_env}')

    if not settings.has_api_credentials and st.button('Fetch public live markets', use_container_width=True):
        try:
            with st.spinner('Loading public open markets into local SQLite…'):
                count = ingest_open_markets(use_public_api=True)
            get_movers.clear()
            st.success(f'Live sync complete: saved {count} regular public open markets to SQLite. Search now uses this local copy.')
            st.rerun()
        except Exception as e:
            st.error(f'Live sync could not connect: {e}')
            st.caption('Check that you have internet access and try again. No API key is required for this public-market sync.')

    with SessionLocal() as db:
        last_live_update = db.execute(select(PriceSnapshot.ts).order_by(desc(PriceSnapshot.ts)).limit(1)).scalar_one_or_none()
    if last_live_update:
        st.caption(f'Latest local quote: {eastern_snapshot_time(last_live_update)}')
    st.caption('On Render/cloud, click “Fetch public live markets” again to collect another price snapshot for Movers.')

    if settings.has_api_credentials and st.button('Refresh open markets now', use_container_width=True):
        try:
            count = ingest_open_markets()
            with SessionLocal() as db:
                events = evaluate_alerts(db)
            st.success(f'Saved {count} market snapshots. Alerts triggered: {len(events)}')
        except Exception as e:
            st.error(f'Refresh failed: {e}')

    if st.button('Generate daily brief', use_container_width=True):
        with SessionLocal() as db:
            path = generate_markdown_brief(db)
        st.success(f'Brief saved: {path}')

    st.divider()
    st.subheader('Add to watchlist')
    ticker_in = st.text_input('Market ticker')
    note = st.text_input('Note', placeholder='World Cup, NYC, rates...')
    if st.button('Add ticker', use_container_width=True) and ticker_in:
        add_watchlist(ticker_in, note)
        st.success('Added')

tabs = st.tabs([
    'Market Explorer', 'Movers', 'Watchlist', 'Daily briefing', 'Alerts',
    'Account', 'Historical snapshots',
])

# ------------------------------------------------------------ TAB 0: EXPLORER
with tabs[0]:
    df = markets_df()
    if df.empty:
        st.info('No local data yet. Click "Refresh open markets now" or run python scripts/snapshot.py.')
    else:
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            q = st.text_input('Search markets')
        with c2:
            categories = ['All'] + sorted([x for x in df['category'].dropna().unique().tolist() if x])
            category = st.selectbox('Category', categories)
        with c3:
            min_volume = st.number_input('Min volume', min_value=0, value=0, step=100)

        include_combos = st.checkbox('Include multi-leg combo markets', value=False,
                                     help='The live sync prioritizes regular markets, so this only applies when combo data was imported separately.')

        show = df.copy()
        if q:
            mask = show['title'].fillna('').str.contains(q, case=False) | show['ticker'].fillna('').str.contains(q, case=False)
            show = show[mask]
        if category != 'All':
            show = show[show['category'] == category]
        show = show[show['volume'].fillna(0) >= min_volume]
        if not include_combos:
            show = show[~show['ticker'].fillna('').str.startswith('KXMVE')]

        st.caption('Quotes shown in cents. Probability is the midpoint of the live Yes bid/ask; Last is the most recent trade.')
        ordered = show.sort_values(['updated_at', 'volume'], ascending=False)
        page_size = st.session_state.get('explorer_page_size', 25)
        page_count = max(1, (len(ordered) + page_size - 1) // page_size)
        page = min(st.session_state.get('explorer_page', 1), page_count)
        start = (page - 1) * page_size

        cols = ['display_title', 'category', 'ticker', 'probability',
                'yes_bid', 'no_bid', 'last_price', 'volume', 'liquidity']
        page_df = ordered.iloc[start:start + page_size][cols].copy()
        st.dataframe(
            page_df.style.format({
                'probability': lambda v: '—' if pd.isna(v) else f'{v:.1%}',
                'yes_bid': '{:.0f}¢', 'no_bid': '{:.0f}¢', 'last_price': '{:.0f}¢',
                'volume': '{:,.0f}', 'liquidity': '{:,.0f}'}, na_rep='—'),
            use_container_width=True, hide_index=True, height=560)

        pager_info, pager_size, pager_nav = st.columns([3.1, 1.05, 3.15])
        with pager_info:
            st.caption(
                f'Showing {start + 1:,}–{min(start + page_size, len(ordered)):,} of '
                f'{len(ordered):,} markets · page {page:,} of {page_count:,}'
            )
        with pager_size:
            st.selectbox(
                'Markets per page', [25, 50, 100], index=[25, 50, 100].index(page_size),
                key='explorer_page_size', label_visibility='collapsed',
                format_func=lambda rows: f'{rows} / page',
                help='Markets shown per page',
            )
        with pager_nav:
            first_visible = max(1, min(page - 2, page_count - 4))
            last_visible = min(page_count, first_visible + 4)
            visible_pages = list(range(first_visible, last_visible + 1))
            nav_cols = st.columns([0.65] + [0.72] * len(visible_pages) + [0.65])
            with nav_cols[0]:
                if st.button('‹', key='explorer_previous_page', disabled=page == 1,
                             help='Previous page', use_container_width=True):
                    st.session_state.explorer_page = page - 1
                    st.rerun()
            for index, visible_page in enumerate(visible_pages, start=1):
                with nav_cols[index]:
                    if st.button(
                        str(visible_page), key=f'explorer_page_{visible_page}',
                        type='primary' if visible_page == page else 'secondary',
                        use_container_width=True,
                    ):
                        st.session_state.explorer_page = visible_page
                        st.rerun()
            with nav_cols[-1]:
                if st.button('›', key='explorer_next_page', disabled=page == page_count,
                             help='Next page', use_container_width=True):
                    st.session_state.explorer_page = page + 1
                    st.rerun()

# ------------------------------------------------------------ TAB 1: MOVERS
with tabs[1]:
    horizon = st.session_state.get('mover_horizon', 60)

    movers = get_movers(minutes=horizon, limit=200)

    if not movers:
        st.info(
            'Need at least two real price updates for the selected horizon. '
            'On Render, click “Fetch public live markets” again after the horizon passes '
            '(about 1 minute, 1 hour, or 24 hours) so Movers has two cloud snapshots to compare.'
        )
    else:
        mdf = pd.DataFrame(movers)
        mdf['opportunity_score'] = mdf.apply(lambda r: opportunity_score(r.to_dict()), axis=1)

        summary_ups = mdf.loc[mdf['change_points'] > 0, 'change_points']
        summary_downs = mdf.loc[mdf['change_points'] < 0, 'change_points']
        s1, s2, s3 = st.columns(3)
        s1.metric('Matching movers', len(mdf))
        s2.metric('Largest up move', f"+{summary_ups.max():.1f} pts" if len(summary_ups) else '—')
        s3.metric('Largest down move', f"{summary_downs.min():.1f} pts" if len(summary_downs) else '—')

        with st.expander('Movers key', expanded=False):
            st.caption(
                '**Change points** is the probability movement; **prior/current probability** are the two compared prices; '
                '**previous/latest snapshot** are stored in ET. **Opportunity score** uses normalized weights: '
                '45% move size, 25% volume, 15% liquidity, and 15% uncertainty (markets nearer 50% rank higher). '
                'It is a research ranking, not a trading signal.'
            )
            st.caption(
                'Cloud note: Movers uses snapshots collected after deployment. '
                'A fresh Render app starts with little history, so the list grows after repeated public syncs.'
            )

        f1, f2, f3, f4, f5 = st.columns([2.35, 2.15, 1, 1, 1.15])
        with f1:
            horizon = st.radio(
                'Horizon', [1, 60, 1440], horizontal=True, key='mover_horizon',
                format_func=lambda minutes: '1 min' if minutes == 1 else '1 hr' if minutes == 60 else '24 hr',
            )
        with f2:
            mover_q = st.text_input('Search movers', key='mover_search', placeholder='Ticker or market')
        with f3:
            min_abs_move = st.number_input('Min move', min_value=0.0, value=0.0, step=1.0, key='mover_min_move')
        with f4:
            min_score = st.number_input('Min score', min_value=0.0, value=0.0, step=0.1, key='mover_min_score')
        with f5:
            direction = st.selectbox('Direction', ['All', 'Up only', 'Down only'], key='mover_direction')

        view = mdf.copy()
        if mover_q:
            cols_to_search = [c for c in ['ticker', 'title', 'display_title'] if c in view.columns]
            if cols_to_search:
                mask = pd.Series(False, index=view.index)
                for c in cols_to_search:
                    mask = mask | view[c].fillna('').astype(str).str.contains(mover_q, case=False)
                view = view[mask]

        if 'change_points' in view.columns:
            view = view[view['change_points'].abs() >= min_abs_move]
            if direction == 'Up only':
                view = view[view['change_points'] > 0]
            elif direction == 'Down only':
                view = view[view['change_points'] < 0]

        view = view[view['opportunity_score'] >= min_score]

        mover_view = view.rename(columns={
            'ticker': 'Ticker',
            'change_points': 'Change points',
            'prior_probability': 'Prior probability',
            'probability': 'Current probability',
            'opportunity_score': 'Opportunity score',
            'prior_ts': 'Previous snapshot',
            'latest_ts': 'Latest snapshot',
        })[[
            'Ticker', 'Change points', 'Prior probability', 'Current probability',
            'Opportunity score', 'Previous snapshot', 'Latest snapshot',
        ]].copy()
        mover_view['Prior probability'] = mover_view['Prior probability'] * 100
        mover_view['Current probability'] = mover_view['Current probability'] * 100
        mover_view['Previous snapshot'] = mover_view['Previous snapshot'].map(eastern_snapshot_time)
        mover_view['Latest snapshot'] = mover_view['Latest snapshot'].map(eastern_snapshot_time)

        st.caption('Snapshot times are shown in Eastern Time (ET).')
        st.dataframe(
            mover_view.sort_values('Opportunity score', ascending=False),
            use_container_width=True,
            hide_index=True,
            height=460,
            column_config={
                'Change points': st.column_config.NumberColumn(format='%+.1f pts'),
                'Prior probability': st.column_config.NumberColumn(format='%.1f%%'),
                'Current probability': st.column_config.NumberColumn(format='%.1f%%'),
                'Opportunity score': st.column_config.NumberColumn(format='%.1f'),
                'Previous snapshot': st.column_config.TextColumn('Previous snapshot'),
                'Latest snapshot': st.column_config.TextColumn('Latest snapshot'),
            },
        )

    st.divider()
    st.subheader('Backtest a probability-threshold rule')
    st.caption('Analytical lookback over locally stored snapshots only. This does not place, '
               'simulate live, or recommend any trades — it just reports how a simple rule would '
               'have looked historically given the data on hand.')

    with SessionLocal() as db:
        bt_tickers = [x[0] for x in db.execute(select(PriceSnapshot.ticker).distinct().order_by(PriceSnapshot.ticker)).all()]

    if not bt_tickers:
        st.info('No snapshot history yet. Sync public markets and let snapshots accumulate first.')
    else:
        bc1, bc2, bc3 = st.columns(3)
        with bc1:
            bt_ticker = st.selectbox('Ticker', bt_tickers, key='bt_ticker')
        with bc2:
            bt_side = st.selectbox('Entry trigger', ['Crosses above', 'Crosses below'], key='bt_side')
        with bc3:
            bt_threshold = st.number_input('Probability threshold', min_value=0.0, max_value=1.0, value=0.5, step=0.01, key='bt_threshold')

        if st.button('Run backtest', key='bt_run'):
            with SessionLocal() as db:
                snaps = db.execute(
                    select(PriceSnapshot).where(PriceSnapshot.ticker == bt_ticker).order_by(PriceSnapshot.ts)
                ).scalars().all()
            series = pd.DataFrame([{'time': s.ts, 'probability': s.probability} for s in snaps]).dropna(subset=['probability'])
            if len(series) < 2:
                st.warning('Not enough snapshots with a probability value to backtest this ticker.')
            else:
                series = series.sort_values('time').reset_index(drop=True)
                prev = series['probability'].shift(1)
                if bt_side == 'Crosses above':
                    cross_idx = series.index[(prev < bt_threshold) & (series['probability'] >= bt_threshold)]
                else:
                    cross_idx = series.index[(prev > bt_threshold) & (series['probability'] <= bt_threshold)]

                if len(cross_idx) == 0:
                    st.info('The probability never crossed that threshold in the stored history.')
                else:
                    entry_i = int(cross_idx[0])
                    entry = series.iloc[entry_i]
                    exit_row = series.iloc[-1]
                    entry_prob = entry['probability']
                    exit_prob = exit_row['probability']
                    move_pts = (exit_prob - entry_prob) * 100

                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric('Entry prob', f'{entry_prob:.1%}')
                    m2.metric('Exit prob (latest)', f'{exit_prob:.1%}')
                    m3.metric('Move since entry', f'{move_pts:+.1f} pts')
                    m4.metric('Threshold crossings', len(cross_idx))

                    chart = series.copy()
                    chart['threshold'] = bt_threshold
                    fig = px.line(chart, x='time', y=['probability', 'threshold'],
                                  title=f'{bt_ticker} — probability vs. threshold')
                    fig.add_vline(x=entry['time'], line_dash='dash', line_color='#ff4fb7')
                    st.plotly_chart(fig, use_container_width=True)
                    st.caption('Entry is the first time the rule triggered; exit is the most recent stored '
                               'snapshot. "Move since entry" is the change in probability, in percentage points — '
                               'a descriptive statistic, not a profit/return figure or a recommendation.')

# ------------------------------------------------------------ TAB 2: WATCHLIST
with tabs[2]:
    with SessionLocal() as db:
        items = db.execute(select(WatchlistItem).order_by(WatchlistItem.created_at)).scalars().all()
    if not items:
        st.info('Add tickers from the sidebar or Markets tab.')
    for item in items:
        left, right = st.columns([5, 1])
        with left:
            st.subheader(item.ticker)
            if item.note:
                st.caption(item.note)
        with right:
            if st.button('Remove', key=f'remove_{item.ticker}'):
                with SessionLocal() as db:
                    db.delete(db.get(WatchlistItem, item.ticker))
                    db.commit()
                st.rerun()
        with SessionLocal() as db:
            snaps = db.execute(select(PriceSnapshot).where(PriceSnapshot.ticker == item.ticker).order_by(PriceSnapshot.ts)).scalars().all()
        if snaps:
            cdf = pd.DataFrame([{
                'time': s.ts, 'category': s.category, 'probability': s.probability,
                'yes_bid': s.yes_bid, 'no_bid': s.no_bid, 'last_price': s.last_price,
                'volume': s.volume, 'liquidity': s.liquidity,
            } for s in snaps])
            fig = px.line(cdf, x='time', y='probability', title=item.ticker)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(cdf.tail(20), use_container_width=True, hide_index=True)
        else:
            st.caption('No snapshots for this ticker yet.')

# ------------------------------------------------------------ TAB 3: DAILY BRIEF
with tabs[3]:
    st.subheader('Daily Brief')
    st.caption('Creates a Markdown report in the local briefings/ folder.')
    if st.button('Create brief now'):
        with SessionLocal() as db:
            path = generate_markdown_brief(db)
            content = path.read_text(encoding='utf-8')
        st.success(f'Created {path}')
        st.download_button('Download Markdown brief', data=content, file_name=path.name, mime='text/markdown')

# ------------------------------------------------------------ TAB 4: ALERTS
# ------------------------------------------------------------ TAB 4: ALERTS
with tabs[4]:
    st.subheader('Create probability alert')
    c1, c2, c3 = st.columns(3)
    with c1:
        alert_ticker = st.text_input('Ticker for alert')
    with c2:
        kind = st.selectbox('Condition', ['above', 'below'])
    with c3:
        threshold = st.number_input('Probability threshold', min_value=0.0, max_value=1.0, value=0.5, step=0.01)

    if st.button('Save alert') and alert_ticker:
        with SessionLocal() as db:
            db.add(Alert(ticker=alert_ticker.strip().upper(), kind=kind, threshold=threshold))
            db.commit()
        st.success('Alert saved locally')

    if st.button('Evaluate alerts now'):
        with SessionLocal() as db:
            events = evaluate_alerts(db)
        st.success(f'Triggered {len(events)} alert events')

    with SessionLocal() as db:
        alerts = db.execute(select(Alert).order_by(desc(Alert.created_at))).scalars().all()
        events = db.execute(select(AlertEvent).order_by(desc(AlertEvent.triggered_at)).limit(100)).scalars().all()

    st.write('Alert Rules')
    st.dataframe(pd.DataFrame([{'id': a.id, 'ticker': a.ticker, 'kind': a.kind, 'threshold': a.threshold, 'enabled': a.enabled} for a in alerts]), use_container_width=True, hide_index=True)
    st.write('Alert History')
    st.dataframe(pd.DataFrame([{'time': e.triggered_at, 'ticker': e.ticker, 'message': e.message} for e in events]), use_container_width=True, hide_index=True)

# ------------------------------------------------------------ TAB 5: ACCOUNT
with tabs[5]:
    st.subheader('Account — read-only portfolio view')
    st.caption('Display only. This view never places, modifies, or cancels orders. '
               'Portfolio endpoints require a Kalshi API key and private key.')
    if not settings.has_api_credentials:
        st.info('Add both credential values to .env to enable this read-only account view.')

    def _dollars(cents):
        if cents is None or (isinstance(cents, float) and pd.isna(cents)):
            return '—'
        return f'${cents / 100:,.2f}'

    def localprob_lookup() -> dict:
        df_local = markets_df()
        if df_local.empty:
            return {}
        return df_local.set_index('ticker')['probability'].to_dict()

    if st.button('Load portfolio', disabled=not settings.has_api_credentials):
        try:
            client = KalshiClient(settings.base_url, settings.kalshi_api_key_id, settings.kalshi_private_key_path)
            balance = client.get_balance()
            positions = client.get_positions()
            orders = client.get_orders()

            st.markdown('### Balance')
            bal = balance if isinstance(balance, dict) else {}
            b1, b2, b3 = st.columns(3)
            b1.metric('Cash balance', _dollars(bal.get('balance')))
            b2.metric('Portfolio value', _dollars(bal.get('portfolio_value')))
            total_value = bal.get('total_value')
            if total_value is None:
                total_value = (bal.get('balance') or 0) + (bal.get('portfolio_value') or 0)
            b3.metric('Total value', _dollars(total_value))
            with st.expander('Raw balance payload'):
                st.json(balance)

            st.markdown('### Positions')
            pos_list = []
            if isinstance(positions, dict):
                pos_list = positions.get('market_positions') or positions.get('positions') or []
            elif isinstance(positions, list):
                pos_list = positions

            if not pos_list:
                st.info('No open positions returned.')
            else:
                prob_lookup = localprob_lookup()
                rows = []
                for p in pos_list:
                    ticker = p.get('ticker') or p.get('market_ticker')
                    qty = p.get('position') if p.get('position') is not None else p.get('quantity')
                    avg_cost = p.get('market_exposure') or p.get('average_price') or p.get('avg_price')
                    current_prob = prob_lookup.get(ticker)
                    est_price_cents = None if current_prob is None else current_prob * 100
                    market_value = None
                    if est_price_cents is not None and qty is not None:
                        market_value = est_price_cents * qty
                    unrealized = None
                    if market_value is not None and avg_cost is not None:
                        unrealized = market_value - avg_cost
                    rows.append({
                        'ticker': ticker,
                        'display_title': friendly_title(ticker, None),
                        'quantity': qty,
                        'avg_cost': _dollars(avg_cost),
                        'current_prob': None if current_prob is None else f'{current_prob:.1%}',
                        'est_market_value': _dollars(market_value),
                        'unrealized_pnl': _dollars(unrealized),
                    })
                pos_df = pd.DataFrame(rows)
                st.dataframe(pos_df, use_container_width=True, hide_index=True)
                st.caption('Estimated market value and unrealized P&L use the most recent locally '
                           'stored probability for each ticker, so they are approximations. '
                           'Sync public markets for fresher estimates.')
                with st.expander('Raw positions payload'):
                    st.json(positions)

            st.markdown('### Orders')
            ord_list = []
            if isinstance(orders, dict):
                ord_list = orders.get('orders') or []
            elif isinstance(orders, list):
                ord_list = orders

            if not ord_list:
                st.info('No orders returned.')
            else:
                ord_df = pd.DataFrame([{
                    'ticker': o.get('ticker') or o.get('market_ticker'),
                    'side': o.get('side'),
                    'action': o.get('action'),
                    'type': o.get('type') or o.get('order_type'),
                    'quantity': o.get('quantity') or o.get('count'),
                    'price': _dollars(o.get('price') or o.get('yes_price') or o.get('no_price')),
                    'status': o.get('status'),
                    'created': o.get('created_time') or o.get('created_at'),
                } for o in ord_list])
                st.dataframe(ord_df, use_container_width=True, hide_index=True)
                with st.expander('Raw orders payload'):
                    st.json(orders)

        except Exception as e:
            st.error(f'Portfolio load failed: {e}')

# ------------------------------------------------------------ TAB 6: HISTORICAL SNAPSHOTS
with tabs[6]:
    st.subheader('Historical snapshots')
    st.caption('Prices and volumes below are stored locally in SQLite each time a snapshot is saved.')

    with SessionLocal() as db:
        tickers = [x[0] for x in db.execute(select(PriceSnapshot.ticker).distinct().order_by(PriceSnapshot.ticker)).all()]

    ticker = st.selectbox('Ticker', tickers) if tickers else None
    if ticker:
        with SessionLocal() as db:
            snaps = db.execute(select(PriceSnapshot).where(PriceSnapshot.ticker == ticker).order_by(PriceSnapshot.ts)).scalars().all()
        cdf = pd.DataFrame([{
            'time': s.ts, 'category': s.category, 'probability': s.probability,
            'yes_bid': s.yes_bid, 'no_bid': s.no_bid, 'last_price': s.last_price,
            'volume': s.volume, 'liquidity': s.liquidity,
        } for s in snaps])
        st.plotly_chart(px.line(cdf, x='time', y='probability', title=f'{ticker} probability'), use_container_width=True)
        st.plotly_chart(px.line(cdf, x='time', y='volume', title=f'{ticker} volume'), use_container_width=True)
        st.write('Recorded price updates')
        st.dataframe(cdf.tail(100), use_container_width=True, hide_index=True)
