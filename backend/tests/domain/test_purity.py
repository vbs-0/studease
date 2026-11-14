"""The domain package must stay pure: no database, no HTTP, no randomness, no clock (practices.md section 1)."""
import ast
from pathlib import Path

DOMAIN = Path(__file__).resolve().parents[2] / "app" / "domain"
FORBIDDEN_IMPORTS = {"sqlalchemy", "fastapi", "random", "psycopg", "time", "app.api", "app.datagen", "app.engine",
                     "app.schema", "app.db", "app.config"}
FORBIDDEN_CALLS = {"now", "today", "utcnow"}


def test_domain_files_exist():
    assert len(list(DOMAIN.glob("*.py"))) >= 10


def test_domain_imports_and_calls_are_pure():
    for path in DOMAIN.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                names = []
            for name in names:
                assert not any(name == f or name.startswith(f + ".") for f in FORBIDDEN_IMPORTS), \
                    f"{path.name} imports {name}"
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in FORBIDDEN_CALLS, f"{path.name} calls .{node.func.attr}()"
