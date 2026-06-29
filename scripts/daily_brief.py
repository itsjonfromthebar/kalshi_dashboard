from kalshi_dashboard.db.init_db import init_db
from kalshi_dashboard.db.session import SessionLocal
from kalshi_dashboard.services.briefing import generate_markdown_brief

if __name__ == '__main__':
    init_db()
    with SessionLocal() as db:
        path = generate_markdown_brief(db)
    print(path)
