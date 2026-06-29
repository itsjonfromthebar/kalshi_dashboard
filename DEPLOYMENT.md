# Cloud deployment

This app is ready to deploy as a Streamlit app. The cloud version starts with a fresh SQLite database and demo/public market behavior. Do not upload your local `.venv`, `.env`, private key, or `.db` files.

## Recommended: Render with GitHub

This is closest to the setup you probably used for the office-job app:

1. Push this project folder to GitHub.
2. In Render, create a new **Web Service** from that GitHub repo.
3. Choose **Docker** as the environment. Render will use the included `Dockerfile`.
4. Add these Environment Variables in Render:

```text
APP_AUTH_REQUIRED=true
APP_USERNAME=admin
APP_PASSWORD=choose-a-real-password
KALSHI_ENV=prod
DATABASE_URL=sqlite:///./kalshi_dashboard.db
SNAPSHOT_LIMIT=2500
PUBLIC_MARKET_LIMIT=10000
SNAPSHOT_INTERVAL_MINUTES=5
```

5. Deploy.
6. Open the Render URL and log in with the username/password above.

The included `render.yaml` can also be used as a Render Blueprint. It defines the web service and leaves `APP_PASSWORD` as a private value that Render asks you to fill in.

## Streamlit Community Cloud alternative

1. Push this project folder to GitHub.
2. In Streamlit Community Cloud, create a new app from the repository.
3. Set the main file path to:

```text
app.py
```

4. Add these as secrets/environment variables:

```text
APP_AUTH_REQUIRED=true
APP_USERNAME=admin
APP_PASSWORD=choose-a-real-password
KALSHI_ENV=prod
DATABASE_URL=sqlite:///./kalshi_dashboard.db
SNAPSHOT_LIMIT=2500
PUBLIC_MARKET_LIMIT=10000
SNAPSHOT_INTERVAL_MINUTES=5
```

For cloud use, keep `DATABASE_URL` as SQLite unless you intentionally move to a hosted database later. SQLite is simple and good for a personal dashboard, but cloud storage can reset during redeploys. Treat it as a lightweight cache, not permanent history.

## Docker deployment

The included Dockerfile runs the Streamlit app and honors a cloud-provided `PORT` variable.

```bash
docker build -t kalshi-dashboard .
docker run --rm -p 8501:8501 kalshi-dashboard
```

Then open:

```text
http://localhost:8501
```

## What should not be deployed

These are ignored on purpose:

- `.venv/`
- `.env`
- `*.key`
- `*.db`
- `*.db-wal`
- `*.db-shm`
- `__pycache__/`

Your current local database is several GB. It should stay on your Windows machine, not in the cloud repo.
