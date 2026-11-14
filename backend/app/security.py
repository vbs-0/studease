"""Passwords (scrypt), access tokens and password-reset tokens (S-3, S-7, S-23).

No FastAPI or database code here, so every rule can be tested on its own."""
from __future__ import annotations

import hashlib
import hmac
import os
import time

import jwt

from app.config import settings

ALGORITHM = "HS256"                       # pinned on decode: a token can never choose its own algorithm
RESET_MINUTES = 30
_N, _R, _P = 2**14, 8, 1                  # scrypt cost (about 16 MiB, tens of ms): OWASP's minimum profile


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time comparison; a malformed stored hash is simply a failure, never an exception."""
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        got = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p),
                             dklen=len(digest) // 2)
        return hmac.compare_digest(got.hex(), digest)
    except (ValueError, TypeError):
        return False


def _fingerprint(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def make_token(user: dict) -> str:
    now = int(time.time())
    claims = {"sub": user["app_user_id"], "role": user["role"], "student_id": user["student_id"],
              "program_id": user["program_id"], "iat": now, "exp": now + settings.jwt_ttl_minutes * 60}
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM)


def read_token(token: str) -> dict | None:
    """The claims of a valid access token, else None (bad signature, expired, wrong algorithm, wrong kind)."""
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        return None
    return None if claims.get("purpose") else claims


def make_reset_token(user: dict) -> str:
    """Bound to the current password hash: once the password changes the link stops working (single use)."""
    now = int(time.time())
    claims = {"sub": user["app_user_id"], "purpose": "reset", "ph": _fingerprint(user["password_hash"]),
              "iat": now, "exp": now + RESET_MINUTES * 60}
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM)


def read_reset_token(token: str) -> dict | None:
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        return None
    return claims if claims.get("purpose") == "reset" else None


def reset_token_matches(claims: dict, user: dict) -> bool:
    return hmac.compare_digest(claims.get("ph", ""), _fingerprint(user["password_hash"]))
