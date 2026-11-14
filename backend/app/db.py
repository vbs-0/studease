from collections.abc import Iterator

from sqlalchemy import Connection, create_engine

from app.config import settings

engine = create_engine(settings.database_url, pool_size=5, max_overflow=5, pool_pre_ping=True)


def get_conn() -> Iterator[Connection]:
    # looked up at call time so tests can swap app.db.engine
    with globals()["engine"].connect() as conn:
        yield conn
