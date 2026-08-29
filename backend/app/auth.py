"""Role-based authentication for the RailSync demo.

Sample credentials (hackathon prototype, do not reuse in production):

    Username      Password        Role
    ---------     ----------      ----------
    controller    admin@123       controller
    passenger     pass@123        passenger

Passwords are never stored in plaintext; each user's password is hashed with
PBKDF2-HMAC-SHA256 at import time. Sessions use a short-lived HMAC-signed token
issued by the backend and verified with hmac.compare_digest.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

AUTH_SECRET = os.getenv("RAILSYNC_AUTH_SECRET", "railsync-dev-secret-change-me")
TOKEN_TTL_SECONDS = int(os.getenv("RAILSYNC_TOKEN_TTL_SECONDS", "28800"))

SAMPLE_USERS: dict[str, dict] = {
    "controller": {
        "password": "admin@123",
        "role": "controller",
        "display_name": "Station Controller",
    },
    "passenger": {
        "password": "pass@123",
        "role": "passenger",
        "display_name": "Passenger",
    },
}


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000).hex()


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(payload: dict) -> str:
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64encode(hmac.new(AUTH_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def _users() -> dict[str, dict]:
    users = {}
    for username, info in SAMPLE_USERS.items():
        salt = f"railsync::{username}"
        users[username] = {
            "username": username,
            "role": info["role"],
            "display_name": info["display_name"],
            "password_hash": _hash_password(info["password"], salt),
            "salt": salt,
        }
    return users


USERS = _users()


def authenticate(username: str, password: str) -> dict | None:
    """Return the public user profile if the credentials match, else None."""
    user = USERS.get(username)
    if user is None:
        return None
    expected = _hash_password(password, user["salt"])
    if not hmac.compare_digest(expected, user["password_hash"]):
        return None
    return {
        "username": user["username"],
        "role": user["role"],
        "display_name": user["display_name"],
    }


def issue_token(username: str, role: str) -> str:
    now = int(time.time())
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + TOKEN_TTL_SECONDS,
    }
    return _sign(payload)


def verify_token(token: str) -> dict | None:
    """Return the token payload if valid and unexpired, else None."""
    try:
        body, signature = token.split(".")
        expected = _b64encode(hmac.new(AUTH_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature):
            return None
        payload = json.loads(_b64decode(body))
        if int(payload.get("exp", 0)) < time.time():
            return None
        return payload
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None