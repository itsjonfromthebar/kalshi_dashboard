from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from kalshi_dashboard.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine():
    settings = get_settings()
    kwargs = (
        {'connect_args': {'check_same_thread': False, 'timeout': 30}}
        if settings.database_url.startswith('sqlite') else {}
    )
    database_engine = create_engine(settings.database_url, echo=False, future=True, **kwargs)
    if settings.database_url.startswith('sqlite'):
        # WAL permits Streamlit reads while the separate live-price updater
        # writes. The busy timeout lets short write bursts finish cleanly.
        @event.listens_for(database_engine, 'connect')
        def configure_sqlite_connection(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute('PRAGMA journal_mode=WAL')
            cursor.execute('PRAGMA busy_timeout=30000')
            cursor.close()
    return database_engine


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
