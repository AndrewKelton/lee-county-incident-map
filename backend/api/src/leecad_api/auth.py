import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta

import jwt
import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import Blueprint, current_app, jsonify, request

PREFIX = "/api/v1/auth"
REFRESH_COOKIE = "refresh_token"
ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(days=30)
MIN_PASSWORD = 8
MAX_PASSWORD = 128
MAX_EMAIL = 254

bp = Blueprint("auth", __name__, url_prefix=PREFIX)

hasher = PasswordHasher()
NO_SUCH_USER_HASH = hasher.hash(secrets.token_urlsafe(32))

CREATE_USER = """
    INSERT INTO users (email, password_hash) VALUES (%s, %s)
    RETURNING id, email, created_at
"""

FIND_USER = "SELECT id, email, password_hash, created_at FROM users WHERE lower(email) = %s"

STORE_REFRESH = "INSERT INTO refresh_tokens (token_hash, user_id, expires_at) VALUES (%s, %s, %s)"


@bp.post("/register")
def register():
    email, password = _body()
    if "@" not in email or len(email) > MAX_EMAIL:
        raise ValueError("email is not valid")
    if not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
        raise ValueError(f"password must be {MIN_PASSWORD} to {MAX_PASSWORD} characters")

    password_hash = hasher.hash(password)
    with current_app.pool.connection() as conn:
        try:
            with conn.transaction():
                user = conn.execute(CREATE_USER, (email, password_hash)).fetchone()
        except psycopg.errors.UniqueViolation:
            return jsonify({"error": "that email is already registered"}), 409
        return _session(conn, user), 201


@bp.post("/login")
def login():
    email, password = _body()
    with current_app.pool.connection() as conn:
        user = conn.execute(FIND_USER, (email,)).fetchone()
        if not _password_matches(user, password):
            return jsonify({"error": "email or password is incorrect"}), 401
        conn.execute("DELETE FROM refresh_tokens WHERE expires_at < now()")
        return _session(conn, user)


def _body() -> tuple[str, str]:
    body = request.get_json(silent=True) or {}
    email = body.get("email")
    password = body.get("password")
    email = email.strip().lower() if isinstance(email, str) else ""
    return email, password if isinstance(password, str) else ""


def _password_matches(user, password: str) -> bool:
    if len(password) > MAX_PASSWORD:
        return False
    try:
        hasher.verify(user["password_hash"] if user else NO_SUCH_USER_HASH, password)
    except VerifyMismatchError:
        return False
    return user is not None


def _session(conn, user):
    token = secrets.token_urlsafe(32)
    conn.execute(STORE_REFRESH, (_digest(token), user["id"], datetime.now(UTC) + REFRESH_TTL))

    response = jsonify({
        "user": {
            "id": user["id"],
            "email": user["email"],
            "created_at": user["created_at"].isoformat(),
        },
        "access_token": _access_token(user["id"]),
        "expires_in": int(ACCESS_TTL.total_seconds()),
    })
    secure = os.environ.get("COOKIE_SECURE", "true").lower() != "false"
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=int(REFRESH_TTL.total_seconds()),
        path=PREFIX,
        httponly=True,
        secure=secure,
        samesite="None" if secure else "Lax",
    )
    return response


def _digest(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def _access_token(user_id: int) -> str:
    now = datetime.now(UTC)
    claims = {"sub": str(user_id), "iat": now, "exp": now + ACCESS_TTL}
    return jwt.encode(claims, current_app.config["JWT_SECRET"], algorithm="HS256")
