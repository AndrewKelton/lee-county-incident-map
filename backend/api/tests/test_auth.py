import hashlib
import os
from datetime import UTC, datetime, timedelta

import jwt
import psycopg
import pytest

from leecad_api.auth import ACCESS_TTL, API, AUTH, REFRESH_COOKIE

EMAIL = "resident@example.com"
PASSWORD = "correct horse battery"


def register(client, email=EMAIL, password=PASSWORD):
    return client.post(f"{AUTH}/register", json={"email": email, "password": password})


def login(client, email=EMAIL, password=PASSWORD):
    return client.post(f"{AUTH}/login", json={"email": email, "password": password})


def bearer(response):
    return {"Authorization": f"Bearer {response.json['access_token']}"}


def set_cookie_header(response):
    return next(h for h in response.headers.getlist("Set-Cookie") if h.startswith("refresh_token="))


def refresh_token(response):
    return set_cookie_header(response).split(";")[0].split("=", 1)[1]


def token_count(database_url):
    with psycopg.connect(database_url) as conn:
        return conn.execute("SELECT count(*) FROM refresh_tokens").fetchone()[0]


def test_registering_creates_an_account_and_signs_you_in(auth_client):
    response = register(auth_client)
    assert response.status_code == 201
    body = response.json
    assert body["user"]["email"] == EMAIL
    assert body["expires_in"] == ACCESS_TTL.total_seconds()
    assert body["access_token"]


def test_the_response_never_contains_the_password(auth_client):
    assert PASSWORD not in register(auth_client).text


def test_the_password_is_stored_hashed(auth_client, database_url):
    register(auth_client)
    with psycopg.connect(database_url) as conn:
        stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
    assert stored.startswith("$argon2")
    assert PASSWORD not in stored


def test_the_same_email_cannot_register_twice(auth_client):
    register(auth_client)
    assert register(auth_client).status_code == 409


def test_email_uniqueness_ignores_case(auth_client):
    register(auth_client)
    assert register(auth_client, email="Resident@Example.com").status_code == 409


@pytest.mark.parametrize("email", ["", "not-an-email", "a@" + "b" * 260])
def test_a_bad_email_is_rejected(auth_client, email):
    assert register(auth_client, email=email).status_code == 400


@pytest.mark.parametrize("password", ["short", "x" * 129, None])
def test_a_bad_password_is_rejected(auth_client, password):
    response = auth_client.post(f"{AUTH}/register", json={"email": EMAIL, "password": password})
    assert response.status_code == 400


def test_logging_in_returns_a_new_session(auth_client):
    register(auth_client)
    response = login(auth_client)
    assert response.status_code == 200
    assert response.json["user"]["email"] == EMAIL


def test_logging_in_ignores_email_case_and_whitespace(auth_client):
    register(auth_client)
    assert login(auth_client, email="  Resident@Example.COM ").status_code == 200


def test_the_wrong_password_is_rejected(auth_client):
    register(auth_client)
    response = login(auth_client, password="not the password")
    assert response.status_code == 401
    assert response.json["error"] == "email or password is incorrect"


def test_an_unknown_email_gives_the_same_answer_as_a_wrong_password(auth_client):
    register(auth_client)
    unknown = login(auth_client, email="nobody@example.com")
    wrong = login(auth_client, password="not the password")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json == wrong.json


def test_the_access_token_identifies_the_user_and_expires(auth_client):
    body = register(auth_client).json
    claims = jwt.decode(body["access_token"], os.environ["JWT_SECRET"], algorithms=["HS256"])
    assert claims["sub"] == str(body["user"]["id"])
    assert claims["exp"] - claims["iat"] == ACCESS_TTL.total_seconds()


def test_the_access_token_is_rejected_if_it_was_signed_with_another_key(auth_client):
    token = register(auth_client).json["access_token"]
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "someone elses key that is also 32 bytes", algorithms=["HS256"])


def test_the_refresh_cookie_is_http_only_and_scoped_to_the_auth_routes(auth_client):
    header = set_cookie_header(register(auth_client))
    assert "HttpOnly" in header
    assert f"Path={AUTH}" in header


def test_the_refresh_token_itself_is_not_in_the_database(auth_client, database_url):
    token = refresh_token(register(auth_client))
    with psycopg.connect(database_url) as conn:
        stored = conn.execute("SELECT token_hash FROM refresh_tokens").fetchone()[0]
    assert stored == hashlib.sha256(token.encode()).digest()
    assert token.encode() not in stored


def test_logging_in_twice_leaves_two_live_sessions(auth_client, database_url):
    register(auth_client)
    login(auth_client)
    assert token_count(database_url) == 2


def test_logging_in_clears_out_expired_tokens(auth_client, database_url):
    register(auth_client)
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("UPDATE refresh_tokens SET expires_at = now() - interval '1 day'")
    login(auth_client)
    assert token_count(database_url) == 1


def test_me_returns_the_signed_in_account(auth_client):
    created = register(auth_client)
    response = auth_client.get(f"{API}/users/me", headers=bearer(created))
    assert response.status_code == 200
    assert response.json == created.json["user"]


def test_me_needs_a_token(auth_client):
    register(auth_client)
    assert auth_client.get(f"{API}/users/me").status_code == 401


@pytest.mark.parametrize("header", ["", "Bearer", "Bearer nonsense", "Basic abc", "token abc"])
def test_me_rejects_a_malformed_authorization_header(auth_client, header):
    register(auth_client)
    response = auth_client.get(f"{API}/users/me", headers={"Authorization": header})
    assert response.status_code == 401


def test_me_rejects_a_token_signed_with_another_key(auth_client):
    user_id = register(auth_client).json["user"]["id"]
    now = datetime.now(UTC)
    forged = jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + ACCESS_TTL},
        "someone elses key that is also 32 bytes",
        algorithm="HS256",
    )
    response = auth_client.get(f"{API}/users/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_me_rejects_an_expired_token(auth_client):
    user_id = register(auth_client).json["user"]["id"]
    stale = datetime.now(UTC) - timedelta(hours=1)
    expired = jwt.encode(
        {"sub": str(user_id), "iat": stale, "exp": stale + ACCESS_TTL},
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )
    response = auth_client.get(f"{API}/users/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_me_rejects_a_token_for_a_deleted_account(auth_client, database_url):
    created = register(auth_client)
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("DELETE FROM users")
    assert auth_client.get(f"{API}/users/me", headers=bearer(created)).status_code == 401


def test_refresh_issues_a_new_access_token(auth_client):
    created = register(auth_client)
    response = auth_client.post(f"{AUTH}/refresh")
    assert response.status_code == 200
    assert response.json["user"] == created.json["user"]
    assert auth_client.get(f"{API}/users/me", headers=bearer(response)).status_code == 200


def test_refresh_replaces_the_cookie_and_leaves_one_session(auth_client, database_url):
    created = register(auth_client)
    rotated = auth_client.post(f"{AUTH}/refresh")
    assert refresh_token(rotated) != refresh_token(created)
    assert token_count(database_url) == 1


def test_a_refresh_token_works_only_once(auth_client):
    used = refresh_token(register(auth_client))
    auth_client.post(f"{AUTH}/refresh")

    auth_client.set_cookie(REFRESH_COOKIE, used, path=AUTH)
    assert auth_client.post(f"{AUTH}/refresh").status_code == 401


def test_refresh_without_a_cookie_is_rejected(auth_client):
    assert auth_client.post(f"{AUTH}/refresh").status_code == 401


def test_refresh_rejects_an_expired_token(auth_client, database_url):
    register(auth_client)
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("UPDATE refresh_tokens SET expires_at = now() - interval '1 day'")
    assert auth_client.post(f"{AUTH}/refresh").status_code == 401


def test_a_rejected_refresh_clears_the_cookie(auth_client):
    auth_client.set_cookie(REFRESH_COOKIE, "not a real token", path=AUTH)
    response = auth_client.post(f"{AUTH}/refresh")
    assert response.status_code == 401
    assert "Max-Age=0" in set_cookie_header(response)


def test_logging_out_ends_the_session(auth_client, database_url):
    register(auth_client)
    response = auth_client.post(f"{AUTH}/logout")
    assert response.status_code == 200
    assert token_count(database_url) == 0
    assert "Max-Age=0" in set_cookie_header(response)
    assert auth_client.post(f"{AUTH}/refresh").status_code == 401


def test_logging_out_twice_still_succeeds(auth_client):
    register(auth_client)
    auth_client.post(f"{AUTH}/logout")
    assert auth_client.post(f"{AUTH}/logout").status_code == 200


def test_logging_out_ends_only_the_session_that_was_presented(auth_client, database_url):
    register(auth_client)
    login(auth_client)
    auth_client.post(f"{AUTH}/logout")
    assert token_count(database_url) == 1
