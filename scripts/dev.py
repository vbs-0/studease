#!/usr/bin/env python3
"""Cross-platform task runner (Windows, macOS, Linux). Standard library only.

    python scripts/dev.py <command> [args]        (the Makefile forwards `make <command>` here)

Commands run from the repository root. `python scripts/dev.py help` lists them.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND, FRONTEND, DATABASE = ROOT / "backend", ROOT / "frontend", ROOT / "database"
PGDATA = ROOT / ".pgdata"
PORT = os.environ.get("STUDEASE_PG_PORT", "15433")
SCALE = os.environ.get("SCALE", "starter")
ALEMBIC = ["uv", "run", "alembic", "-c", str(DATABASE / "alembic.ini")]
EXE = ".exe" if os.name == "nt" else ""


def run(cmd: list[str], cwd: Path = ROOT, check: bool = True, **kw) -> subprocess.CompletedProcess:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run(cmd, cwd=cwd, check=check, **kw)


def pg_bin(name: str) -> str:
    """Find a PostgreSQL binary: $PGBIN, then PATH, then the usual install folders."""
    candidates = []
    if os.environ.get("PGBIN"):
        candidates.append(Path(os.environ["PGBIN"]))
    found = shutil.which(name)
    if found:
        return found
    for base in (Path("C:/Program Files/PostgreSQL"), Path("/usr/lib/postgresql"),
                 Path("/opt/homebrew/opt"), Path("/usr/local/opt")):
        if base.exists():
            candidates += sorted(base.glob("*/bin"), reverse=True) + sorted(base.glob("*/*/bin"), reverse=True)
    for d in candidates:
        if (d / f"{name}{EXE}").exists():
            return str(d / f"{name}{EXE}")
    sys.exit(f"PostgreSQL tool '{name}' not found. Install PostgreSQL 14+ or set PGBIN to its bin folder.")


def psql(sql: str, db: str = "postgres", tuples: bool = False) -> str:
    cmd = [pg_bin("psql"), "-h", "127.0.0.1", "-p", PORT, "-U", "postgres", "-d", db, "-v", "ON_ERROR_STOP=1", "-q"]
    if tuples:
        cmd += ["-At"]
    return subprocess.run([*cmd, "-c", sql], check=True, capture_output=True, text=True).stdout.strip()


# ---------------------------------------------------------------------------------------- database
def db_init() -> None:
    """Create the throwaway development cluster in .pgdata (trust auth, localhost only)."""
    if (PGDATA / "PG_VERSION").exists():
        print("cluster already exists:", PGDATA)
        return
    run([pg_bin("initdb"), "-D", str(PGDATA), "-U", "postgres", "--auth=trust", "-E", "UTF8", "--locale=C"])


def db_up() -> None:
    """Start the cluster on 127.0.0.1:$STUDEASE_PG_PORT and create role and databases if missing."""
    db_init()
    status = run([pg_bin("pg_ctl"), "status", "-D", str(PGDATA)], check=False, capture_output=True)
    if status.returncode != 0:
        # stdio goes to DEVNULL so the long-lived server never inherits (and holds open) our pipes
        run([pg_bin("pg_ctl"), "start", "-D", str(PGDATA), "-w", "-l", str(PGDATA / "server.log"),
             "-o", f"-p {PORT} -c listen_addresses=127.0.0.1"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            # Windows: own process group, no console, so killing the calling shell cannot take the server down
            creationflags=0x00000208 if os.name == "nt" else 0)
    if not psql("SELECT 1 FROM pg_roles WHERE rolname = 'studease'", tuples=True):
        psql("CREATE ROLE studease LOGIN PASSWORD 'studease'")
    for name in ("studease", "studease_test"):
        if not psql(f"SELECT 1 FROM pg_database WHERE datname = '{name}'", tuples=True):
            psql(f"CREATE DATABASE {name} OWNER studease")
    print(f"database ready: postgresql://studease:studease@127.0.0.1:{PORT}/studease")


def db_down() -> None:
    run([pg_bin("pg_ctl"), "stop", "-D", str(PGDATA), "-m", "fast"], check=False)


def db_reset() -> None:
    """Drop and recreate the studease database (not the test database)."""
    psql("DROP DATABASE IF EXISTS studease WITH (FORCE)")
    psql("CREATE DATABASE studease OWNER studease")
    migrate()


def migrate() -> None:
    run([*ALEMBIC, "upgrade", "head"], cwd=BACKEND)


def schema_sql() -> None:
    out = DATABASE / "schema.sql"
    res = run([*ALEMBIC, "upgrade", "head", "--sql"], cwd=BACKEND, capture_output=True, text=True)
    out.write_text(res.stdout.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    print("wrote", out)


# ---------------------------------------------------------------------------------------- app
def install() -> None:
    run(["uv", "sync"], cwd=BACKEND)
    if FRONTEND.joinpath("package.json").exists():
        run(["npm", "ci" if FRONTEND.joinpath("package-lock.json").exists() else "install"], cwd=FRONTEND,
            shell=os.name == "nt")


def cli(*args: str) -> None:
    run(["uv", "run", "python", "-m", "app.cli", *args], cwd=BACKEND)


def test() -> None:
    run(["uv", "run", "pytest", "-q", *sys.argv[2:]], cwd=BACKEND)


def lint() -> None:
    run(["uv", "run", "ruff", "check", "app", "tests"], cwd=BACKEND)


def api() -> None:
    run(["uv", "run", "uvicorn", "app.main:create_app", "--factory", "--reload", "--port", "8000"], cwd=BACKEND)


def web() -> None:
    run(["npm", "run", "dev"], cwd=FRONTEND, shell=os.name == "nt")


COMMANDS = {
    "install": install, "db-init": db_init, "db-up": db_up, "db-down": db_down, "db-reset": db_reset,
    "migrate": migrate, "schema-sql": schema_sql, "test": test, "lint": lint, "api": api, "web": web,
    "data": lambda: cli("generate", "--scale", SCALE),
    "validate": lambda: cli("validate", "--scale", SCALE),
    "repro": lambda: cli("repro", "--scale", SCALE),
    "load": lambda: cli("load", "--scale", SCALE),
    "reconcile": lambda: cli("reconcile", "--scale", SCALE),
    "docs": lambda: cli("docs"),
    "all": lambda: cli("all", "--scale", SCALE),
}


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd not in COMMANDS:
        print(__doc__)
        print("commands:", ", ".join(COMMANDS), "\nenvironment: SCALE=starter|full, PGBIN, STUDEASE_PG_PORT")
        sys.exit(0 if cmd == "help" else 2)
    COMMANDS[cmd]()


if __name__ == "__main__":
    main()
