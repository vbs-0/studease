"""Bulk load a dataset into PostgreSQL with COPY, parent tables first, in one transaction."""
from __future__ import annotations

from sqlalchemy.engine import Engine

from app import schema

Dataset = dict[str, list[dict]]
LOAD_ORDER = [*schema.DATA_TABLES]
ALL_TABLES = ["gt.ground_truth", *reversed(schema.DATA_TABLES), "exception", "idempotency_key", "app_user"]


def _copy(cur, table: str, columns: list[str], rows: list[dict]) -> None:
    with cur.copy(f"COPY {table} ({', '.join(columns)}) FROM STDIN") as cp:
        for row in rows:
            cp.write_row([row[c] for c in columns])


def load(engine: Engine, ds: Dataset, gt: list[dict], exceptions: list[dict] | None = None) -> dict[str, int]:
    """Replace the contents of every table with this dataset. Returns the row count of each table as stored.

    The ground truth goes to its own schema (`gt`); it is never joined into the input tables."""
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cur:
            cur.execute("TRUNCATE " + ", ".join(ALL_TABLES) + " CASCADE")
            for name in LOAD_ORDER:
                _copy(cur, name, schema.columns(name), ds[name])
            _copy(cur, "gt.ground_truth", schema.columns("ground_truth"), gt)
            if exceptions:
                _copy(cur, "exception", schema.columns("exception"), exceptions)
            counts = {}
            for name in [*LOAD_ORDER, "gt.ground_truth", "exception"]:
                cur.execute(f"SELECT count(*) FROM {name}")
                counts[name] = cur.fetchone()[0]
        raw.commit()
        return counts
    except BaseException:
        raw.rollback()
        raise
    finally:
        raw.close()
