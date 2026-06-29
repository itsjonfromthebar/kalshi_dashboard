# Codex Next Steps

Use these prompts in order after confirming the app runs locally.

## 1. Add World Cup Dashboard
Add a dedicated World Cup dashboard tab. Let me define keyword groups such as `World Cup`, `USA`, `soccer`, `FIFA`, and `CONCACAF`. Search locally saved markets for those keywords, save matches to a World Cup watchlist, and show 24-hour, 7-day, and 30-day movement charts.

## 2. Add NYC Opportunity Dashboard
Add a dedicated NYC Opportunity Dashboard that searches and tracks markets related to New York City, tourism, hospitality, consumer spending, employment, inflation, sports attendance, and major events. Create a composite NYC Business Sentiment Score with transparent inputs and a short explanation.

## 3. Add OpenAI Explain This Move
Add an OpenAI-powered `Explain This Move` feature. User selects a ticker. The app sends recent price snapshots, volume changes, and market metadata to OpenAI and gets back: what changed, plausible reasons, what to watch next, and uncertainty.

## 4. Add WebSocket Streaming
Use Kalshi WebSocket docs to stream live market updates for watchlist tickers. Keep the 5-minute snapshot job as a fallback.

## 5. Add CSV Export
Add CSV export buttons for markets, movers, watchlist snapshots, alert history, and daily briefs.

## 6. Add PostgreSQL Option
Keep SQLite as default, but make sure PostgreSQL works through DATABASE_URL and Docker Compose.
