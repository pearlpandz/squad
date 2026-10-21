import re
import secrets
import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.core.admin import SESSION_SECONDS, admin_connection, check_origin, current_session, token_hash
from app.core.config import settings

router = APIRouter(prefix="/admin", tags=["session"])
COOKIE_NAME = "squad_session"
ADMIN_EMAIL = "admin@squad-oracle.com"


class SignIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    role: str = Field(min_length=1, max_length=80)


def session_response(session: dict | None) -> dict:
    return {"configured": True, "authenticated": session is not None,
            "is_admin": bool(session and session["email"] == ADMIN_EMAIL and session["role"] == "admin"),
            "username": session["email"] if session else None,
            "email": session["email"] if session else None,
            "role": session["role"] if session else None,
            "human_id": session["human_id"] if session else None}


@router.get("/session")
def status(request: Request, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return session_response(current_session(request))


@router.post("/login")
def login(payload: SignIn, request: Request, response: Response) -> dict:
    check_origin(request)
    email, role = payload.email.strip().lower(), payload.role.strip()
    is_admin = email == ADMIN_EMAIL
    if not is_admin and not re.fullmatch(r"[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@oracle\.com", email):
        raise HTTPException(status_code=422, detail="Enter your @oracle.com enterprise email address")
    if not role or any(ord(char) < 32 for char in role):
        raise HTTPException(status_code=422, detail="Enter your role")
    if is_admin and role.lower() != "admin":
        raise HTTPException(status_code=422, detail="The SQUAD administrator role must be admin")
    if not is_admin and role.lower() == "admin":
        raise HTTPException(status_code=403, detail="The admin role is reserved for admin@squad-oracle.com")
    if is_admin:
        role = "admin"
    token, now = secrets.token_urlsafe(32), int(time.time())
    with admin_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        human = connection.execute("SELECT id, status FROM humans WHERE lower(email) = ?", (email,)).fetchone()
        if human and human["status"] != "active":
            raise HTTPException(status_code=403, detail="This human member is inactive. Contact your administrator.")
        if human:
            human_id = human["id"]
        else:
            cursor = connection.execute(
                "INSERT INTO humans (display_name, username, email, role) VALUES (?, ?, ?, ?)",
                (email.split("@")[0].replace(".", " ").title(), email.split("@")[0], email, role))
            human_id = cursor.lastrowid
        connection.execute("DELETE FROM user_sessions WHERE expires_at <= ?", (now,))
        previous = request.cookies.get(COOKIE_NAME)
        if previous:
            connection.execute("DELETE FROM user_sessions WHERE token_hash = ?", (token_hash(previous),))
        connection.execute(
            "INSERT INTO user_sessions (token_hash, email, role, human_id, expires_at) VALUES (?, ?, ?, ?, ?)",
            (token_hash(token), email, role, human_id, now + SESSION_SECONDS))
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=settings.admin_cookie_secure, samesite="strict", path="/api")
    response.headers["Cache-Control"] = "no-store"
    return session_response({"email": email, "role": role, "human_id": human_id})


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    check_origin(request)
    token = request.cookies.get(COOKIE_NAME)
    if token:
        with admin_connection() as connection:
            connection.execute("DELETE FROM user_sessions WHERE token_hash = ?", (token_hash(token),))
    response.delete_cookie(COOKIE_NAME, path="/api", secure=settings.admin_cookie_secure, httponly=True, samesite="strict")
    response.delete_cookie("collab_admin_session", path="/api")
    response.headers["Cache-Control"] = "no-store"
    return session_response(None)
