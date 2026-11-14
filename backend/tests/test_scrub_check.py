"""The public-repository scrub check (S-20): it must catch each kind of leak, allow the synthetic data, and the
repository itself must be clean."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("scrub_check", ROOT / "scripts" / "scrub_check.py")
scrub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scrub)


def kinds(text):
    return [f.split(": ", 1)[1] for f in scrub.scan_text("f.md", text)]


def test_it_catches_each_kind_of_leak():
    assert kinds("write to someone@gmail.com") == ["e-mail address on gmail.com"]
    assert kinds("server at 10.20.30.40") == ["IP address 10.20.30.40"]
    assert kinds(r"see C:\Users\someone\Desktop") == ["local user path"]
    assert kinds("see /home/someone/app") == ["local user path"]
    assert kinds("-----BEGIN OPENSSH PRIVATE KEY-----") == ["private key"]
    assert kinds("SMTP_PASSWORD=hunter2hunter2") == ["secret assigned a value"]
    assert kinds("copied from the PAM project") == ["word the owner asked to keep out of the repository"]


def test_it_allows_what_the_repository_legitimately_contains():
    ok = ["student@example.edu", "bind 127.0.0.1:8000", "SMTP_PASSWORD=", "JWT_SECRET=<hidden>",
          "version 2026.9.5.10", "pamphlet and pamper are fine", "documentation ip 192.0.2.7"]
    for text in ok:
        assert kinds(text) == [], text


def test_the_repository_is_clean():
    assert scrub.scan() == []
