import hashlib
import os

import jwt
import psycopg
import pytest

from leecad_api.auth import ACCESS_TTL, PREFIX

EMAIL = "resident@example.com"
PASSWORD = "correct horse battery"


def register(client, email=EMAIL, password=PASSWORD):
    return client.post(f"{PREFIX}/register", json={"email": email, "password": password})


def login(client, email=EMAIL, password=PASSWORD):
    return client.post(f"{PREFIX}/login", json={"email": email, "password": password})


def refresh_cookie(response):
    header = next(h for h in response.headers.getlist("Set-Cookie") if h.startswith("refresh_token="))
    return header.split(";")[0].split("=", 1)[1], header


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
    response = auth_client.post(f"{PREFIX}/register", json={"email": EMAIL, "password": password})
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
    _, header = refresh_cookie(register(auth_client))
    assert "HttpOnly" in header
    assert f"Path={PREFIX}" in header


def test_the_refresh_token_itself_is_not_in_the_database(auth_client, database_url):
    token, _ = refresh_cookie(register(auth_client))
    with psycopg.connect(database_url) as conn:
        stored = conn.execute("SELECT token_hash FROM refresh_tokens").fetchone()[0]
    assert stored == hashlib.sha256(token.encode()).digest()
    assert token.encode() not in stored


def test_logging_in_twice_leaves_two_live_sessions(auth_client, database_url):
    register(auth_client)
    login(auth_client)
    with psycopg.connect(database_url) as conn:
        assert conn.execute("SELECT count(*) FROM refresh_tokens").fetchone()[0] == 2


def test_logging_in_clears_out_expired_tokens(auth_client, database_url):
    register(auth_client)
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("UPDATE refresh_tokens SET expires_at = now() - interval '1 day'")
        login(auth_client)
        assert conn.execute("SELECT count(*) FROM refresh_tokens").fetchone()[0] == 1
