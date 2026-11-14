"""Shared fixtures. Dataset fixtures are generated once per session; database fixtures skip when PostgreSQL is not
reachable (start the local one with `python scripts/dev.py db-up`)."""
import copy
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from app.config import settings
from app.datagen.generator import DEFAULT_SEED, generate

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def baseline():
    """The clean starter dataset: no anomalies injected."""
    return generate("starter", DEFAULT_SEED, inject=False)[0]


@pytest.fixture(scope="session")
def injected():
    """The starter dataset with the five labelled anomalies, plus its ground truth."""
    return generate("starter", DEFAULT_SEED, inject=True)


@pytest.fixture
def clean(baseline):
    """A private copy a test may modify."""
    return copy.deepcopy(baseline)


@pytest.fixture(scope="session")
def db_engine():
    """An engine on the test database, migrated to head. Skips the test when PostgreSQL is not reachable."""
    engine = create_engine(settings.test_url, pool_pre_ping=True)
    try:
        engine.connect().close()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PostgreSQL not reachable at the test URL: {type(exc).__name__}")
    cfg = Config(str(ROOT / "database" / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "database" / "migrations"))
    cfg.set_main_option("sqlalchemy.url", settings.test_url.replace("%", "%%"))
    command.upgrade(cfg, "head")
    yield engine
    engine.dispose()
