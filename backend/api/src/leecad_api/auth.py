import functools
import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta

import jwt
import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import Blueprint, current_app, g, jsonify, request

API = "/api/v1"
AUTH = f"{API}/auth"
REFRESH_COOKIE = "refresh_token"
ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(days=30)
MIN_PASSWORD = 8
MAX_PASSWORD = 128
MAX_EMAIL = 254

bp = Blueprint("auth", __name__)

hasher = PasswordHasher()
NO_SUCH_USER_HASH = hasher.hash(secrets.token_urlsafe(32))

CREATE_USER = """
    INSERT INTO users (email, password_hash) VALUES (%s, %s)
    RETURNING id, email, created_at
"""

FIND_USER = "SELECT id, email, password_hash, created_at FROM users WHERE lower(email) = %s"

FIND_USER_BY_ID = "SELECT id, email, created_at FROM users WHERE id = %s"

STORE_REFRESH = "INSERT INTO refresh_tokens (token_hash, user_id, expires_at) VALUES (%s, %s, %s)"

CONSUME_REFRESH = """
    WITH consumed AS (
        DELETE FROM refresh_tokens
         WHERE token_hash = %s AND expires_at > now()
        RETURNING user_id
    )
    SELECT u.id, u.email, u.created_at
      FROM users u JOIN consumed ON consumed.user_id = u.id
"""


def requires_access_token(view):
    @functools.wraps(view)
    def wrapped(**kwargs):
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        try:
            claims = jwt.decode(
                token if scheme.lower() == "bearer" else "",
                current_app.config["JWT_SECRET"],
                algorithms=["HS256"],
            )
        except jwt.InvalidTokenError:
            return jsonify({"error": "sign in first"}), 401
        g.user_id = int(claims["sub"])
        return view(**kwargs)

    return wrapped


@bp.post(f"{AUTH}/register")
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


@bp.post(f"{AUTH}/login")
def login():
    email, password = _body()
    with current_app.pool.connection() as conn:
        user = conn.execute(FIND_USER, (email,)).fetchone()
        if not _password_matches(user, password):
            return jsonify({"error": "email or password is incorrect"}), 401
        conn.execute("DELETE FROM refresh_tokens WHERE expires_at < now()")
        return _session(conn, user)


@bp.post(f"{AUTH}/refresh")
def refresh():
    presented = request.cookies.get(REFRESH_COOKIE, "")
    with current_app.pool.connection() as conn:
        user = conn.execute(CONSUME_REFRESH, (_digest(presented),)).fetchone()
        if user is None:
            return _forget(jsonify({"error": "sign in again"})), 401
        return _session(conn, user)


@bp.post(f"{AUTH}/logout")
def logout():
    presented = request.cookies.get(REFRESH_COOKIE, "")
    with current_app.pool.connection() as conn:
        conn.execute("DELETE FROM refresh_tokens WHERE token_hash = %s", (_digest(presented),))
    return _forget(jsonify({"status": "signed out"}))


@bp.get(f"{API}/users/me")
@requires_access_token
def me():
    with current_app.pool.connection() as conn:
        user = conn.execute(FIND_USER_BY_ID, (g.user_id,)).fetchone()
    if user is None:
        return jsonify({"error": "sign in first"}), 401
    return jsonify(_user(user))


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


def _user(row) -> dict:
    return {"id": row["id"], "email": row["email"], "created_at": row["created_at"].isoformat()}


def _session(conn, user):
    token = secrets.token_urlsafe(32)
    conn.execute(STORE_REFRESH, (_digest(token), user["id"], datetime.now(UTC) + REFRESH_TTL))

    response = jsonify({
        "user": _user(user),
        "access_token": _access_token(user["id"]),
        "expires_in": int(ACCESS_TTL.total_seconds()),
    })
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=int(REFRESH_TTL.total_seconds()),
        path=AUTH,
        httponly=True,
        **_cookie_transport(),
    )
    return response


def _forget(response):
    response.delete_cookie(REFRESH_COOKIE, path=AUTH, httponly=True, **_cookie_transport())
    return response


def _cookie_transport() -> dict:
    secure = os.environ.get("COOKIE_SECURE", "true").lower() != "false"
    return {"secure": secure, "samesite": "None" if secure else "Lax"}


def _digest(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def _access_token(user_id: int) -> str:
    now = datetime.now(UTC)
    claims = {"sub": str(user_id), "iat": now, "exp": now + ACCESS_TTL}
    return jwt.encode(claims, current_app.config["JWT_SECRET"], algorithm="HS256")
