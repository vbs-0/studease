"""The committed migration must produce exactly the schema defined in app/schema.py (no drift)."""
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app import schema

pytestmark = pytest.mark.db


def test_database_after_migrations_matches_the_python_schema(db_engine):
    with db_engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"include_schemas": True, "compare_type": True})
        diffs = [d for d in compare_metadata(ctx, schema.metadata)]
    assert diffs == [], diffs[:5]
