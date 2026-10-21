"""Configured administrator credentials and revocable, opaque cookie sessions."""

import hashlib
import hmac
import secrets
import time
from contextlib import contextmanager

from fastapi import HTTPException, Request

from app.core.config import settings
from app.db.session import get_connection

COOKIE_NAME = "collab_admin_session"
SESSION_SECONDS = 8 * 60 * 60


@contextmanager
def admin_connection():
    connection = get_connection()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, expected = encoded.split("$")
        if algorithm != "scrypt" or len(salt) != 32 or len(expected) != 64:
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=32)
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def configured() -> bool:
    return bool(settings.admin_username.strip() and settings.admin_password_hash.get_secret_value())


def credential_version() -> str:
    value = settings.admin_username + ":" + settings.admin_password_hash.get_secret_value()
    return hashlib.sha256(value.encode()).hexdigest()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_session(request: Request) -> dict | None:
    token = request.cookies.get("squad_session", "")
    if not token or len(token) > 128:
        return None
    with admin_connection() as connection:
        row = connection.execute(
            "SELECT email, role, human_id, expires_at FROM user_sessions WHERE token_hash = ?",
            (token_hash(token),),
        ).fetchone()
    if row is None or row["expires_at"] <= int(time.time()):
        return None
    return dict(row)


def session_user(request: Request) -> str | None:
    session = current_session(request)
    if session and session["email"] == "admin@squad-oracle.com" and session["role"] == "admin":
        return session["email"]
    return None


def require_session(request: Request) -> dict:
    session = current_session(request)
    if session is None:
        raise HTTPException(status_code=401, detail="Sign in to SQUAD to continue")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_origin(request)
    request.state.user = session
    return session


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if (origin and origin not in settings.cors_origins) or request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(status_code=403, detail="This origin cannot perform admin actions")


def require_admin(request: Request) -> str:
    username = session_user(request)
    if username is None:
        raise HTTPException(status_code=403, detail="Sign in as a SQUAD administrator to access agent templates")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_origin(request)
    return username


def require_template_access(request: Request) -> None:
    # Applied to the entire agents router, including uploads, jobs and downloads.
    route = request.scope.get("route")
    path = getattr(route, "path", "")
    restricted = "/templates" in path or path.endswith("/upgrade-template")
    agent_id = request.path_params.get("agent_id")
    if not restricted and agent_id is not None:
        with admin_connection() as connection:
            row = connection.execute("SELECT is_template FROM agents WHERE id = ?", (agent_id,)).fetchone()
        restricted = bool(row and row["is_template"])
    if restricted:
        require_admin(request)
