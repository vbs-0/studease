#!/usr/bin/env python3
"""Fail if the public repository contains private details (spec S-20). Standard library only.

    python scripts/scrub_check.py            scan every tracked file (or, outside git, every file) and prompts/

Checks: e-mail addresses other than the reserved synthetic ones, IPv4 addresses other than loopback and the
documentation ranges, local user paths, private keys, secret-looking assignments with a value, and words the owner
asked to keep out of the repository. Exit 1 with a list of findings; exit 0 when clean."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "node_modules", ".venv", ".pgdata", "dist", "__pycache__", ".pytest_cache", ".ruff_cache"}
SKIP_SUFFIXES = {".csv", ".gz", ".png", ".jpg", ".woff2", ".lock", ".sql", ".json"}   # generated data, not prose
SKIP_FILES = {"scrub_check.py", "test_scrub_check.py", "package-lock.json"}

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
ALLOWED_EMAIL_DOMAINS = {"example.edu", "example.com", "example.org", "mail.test"}
IPV4 = re.compile(r"(?<![\d.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![\d.])")
LOCAL_PATH = re.compile(r"(?:[A-Za-z]:\\Users\\|/Users/[A-Za-z]|/home/[a-z][a-z0-9_-]+/)")
PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
SECRET = re.compile(r"\b(SMTP_PASSWORD|JWT_SECRET|DEMO_PASSWORD|SMTP_USER|DATABASE_URL)\s*[=:]\s*[^\s#<]+")
# Words kept out of the public repository by the owner's decision (an earlier project is referred to only as such).
BANNED = re.compile(r"\bpam\b|pam-redesign", re.IGNORECASE)


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
        paths = [ROOT / p for p in out.decode().split("\0") if p]
    except (OSError, subprocess.CalledProcessError):
        paths = [p for p in ROOT.rglob("*") if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS)]
    return [p for p in paths if p.is_file() and p.suffix not in SKIP_SUFFIXES and p.name not in SKIP_FILES]


def private_ip(m: re.Match) -> bool:
    a, b, c, d = (int(x) for x in m.groups())
    if max(a, b, c, d) > 255:
        return False                                   # not an address (a version number such as 2026.9.5.10)
    return not (a == 127 or (a, b, c) in {(0, 0, 0), (192, 0, 2), (198, 51, 100), (203, 0, 113)} or a == 0)


def scan_text(name: str, text: str) -> list[str]:
    found: list[str] = []
    for n, line in enumerate(text.splitlines(), 1):
        where = f"{name}:{n}"
        for m in EMAIL.finditer(line):
            domain = m.group().rsplit("@", 1)[1].lower()
            looks_like_url_login = domain.replace(".", "").isdigit() or domain in {"localhost"}   # user:pw@127.0.0.1
            if domain not in ALLOWED_EMAIL_DOMAINS and not looks_like_url_login:
                found.append(f"{where}: e-mail address on {domain}")
        found += [f"{where}: IP address {m.group()}" for m in IPV4.finditer(line) if private_ip(m)]
        if LOCAL_PATH.search(line):
            found.append(f"{where}: local user path")
        if PRIVATE_KEY.search(line):
            found.append(f"{where}: private key")
        if SECRET.search(line):
            found.append(f"{where}: secret assigned a value")
        if BANNED.search(line):
            found.append(f"{where}: word the owner asked to keep out of the repository")
    return found


def scan() -> list[str]:
    findings: list[str] = []
    for path in tracked_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        findings += scan_text(str(path.relative_to(ROOT)).replace("\\", "/"), text)
    return findings


def main() -> int:
    findings = scan()
    for f in findings:
        print(f)
    print(f"scrub check: {len(findings)} finding(s)" if findings else "scrub check: clean")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
