"""One JSON line per request (S-12). Only method, path, status, duration and ids are logged: never the query
string, a header, a body, a password or a token."""
import json
import logging
import sys

log = logging.getLogger("studease")


def setup() -> None:
    if log.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False


def event(**fields) -> None:
    log.info(json.dumps(fields, default=str, separators=(",", ":")))
