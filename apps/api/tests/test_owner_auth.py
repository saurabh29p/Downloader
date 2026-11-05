# ruff: noqa: S105, S106  (test passwords)
"""Owner sign-in (v2): session cookie, CSRF header, hosted fail-closed, login limits."""

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from anyget.core.session import COOKIE, Sessions, hash_password
from anyget.core.settings import Settings, get_settings
from anyget.main import create_app

EMAIL = "owner@example.org"
PASSWORD = "correct horse battery"
HASH = hash_password(PASSWORD)
WEB = {"X-Requested-With": "anyget"}


@pytest.fixture
def make_client(env_settings: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    clients: list[TestClient] = []

    def make(**env: str) -> TestClient:
        for name, value in env.items():
            key = name if name.isupper() else f"ANYGET_{name.upper()}"
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()
        client = TestClient(create_app())
        client.__enter__()
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.__exit__(None, None, None)
    get_settings.cache_clear()


def owner(make_client: Any, **env: str) -> TestClient:
    client: TestClient = make_client(owner_email=EMAIL, owner_password_hash=HASH, **env)
    return client


def sign_in(client: TestClient, email: str = EMAIL, password: str = PASSWORD) -> Any:
    return client.post("/api/auth/login", json={"email": email, "password": password}, headers=WEB)


def test_owner_must_sign_in(make_client: Any) -> None:
    client = owner(make_client)
    assert client.get("/api/health").status_code == 200  # stays open
    denied = client.get("/api/jobs")
    assert denied.status_code == 401 and denied.json()["code"] == "auth_required"
    me = client.get("/api/auth/me").json()
    assert me == {
        "signed_in": False,
        "method": "",
        "login_required": True,
        "owner_configured": True,
        "email": None,
    }

    ok = sign_in(client)
    assert ok.status_code == 200 and ok.json()["signed_in"] is True
    cookie = ok.headers["set-cookie"]
    assert f"{COOKIE}=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert client.get("/api/jobs").status_code == 200
    assert client.get("/api/auth/me").json()["email"] == EMAIL

    assert client.post("/api/auth/logout").status_code == 403  # CSRF header missing
    assert client.post("/api/auth/logout", headers=WEB).status_code == 204
    assert client.get("/api/jobs").status_code == 401


def test_wrong_password_or_email(make_client: Any) -> None:
    client = owner(make_client)
    assert sign_in(client, password="nope").status_code == 401
    assert sign_in(client, email="else@example.org").status_code == 401
    assert sign_in(client, email=" OWNER@example.org ").status_code == 200  # case-insensitive


def test_login_needs_the_web_header(make_client: Any) -> None:
    client = owner(make_client)
    response = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 403 and response.json()["code"] == "csrf"


def test_cookie_writes_need_the_csrf_header(make_client: Any) -> None:
    client = owner(make_client)
    sign_in(client)
    blocked = client.post("/api/jobs", json={"urls": []})
    assert blocked.status_code == 403 and blocked.json()["code"] == "csrf"
    assert client.post("/api/jobs", json={"urls": []}, headers=WEB).status_code != 403


def test_tampered_and_expired_cookies(make_client: Any, env_settings: Path) -> None:
    client = owner(make_client)
    good = sign_in(client).cookies[COOKIE]
    client.cookies.clear()
    payload, mac = good.split(".")
    client.cookies.set(COOKIE, payload + "." + mac[::-1])
    assert client.get("/api/jobs").status_code == 401
    client.cookies.set(COOKIE, "garbage")
    assert client.get("/api/jobs").status_code == 401

    settings = Settings(owner_email=EMAIL, owner_password_hash=HASH, data_dir=env_settings / "data")
    sessions = Sessions(settings)
    old = sessions.issue("owner", now=time.time() - 31 * 86400)
    assert sessions.verify(old) is None
    assert sessions.verify(sessions.issue("owner")) == "owner"


def test_changing_the_password_signs_out(env_settings: Path) -> None:
    data = env_settings / "data"
    first = Sessions(Settings(owner_email=EMAIL, owner_password_hash=HASH, data_dir=data))
    token = first.issue("owner")
    other = hash_password("another password!")
    second = Sessions(Settings(owner_email=EMAIL, owner_password_hash=other, data_dir=data))
    assert first.verify(token) == "owner" and second.verify(token) is None
    key = data / "session.key"
    assert key.is_file() and key.stat().st_mode & 0o777 == 0o600


def test_bearer_token_still_works(make_client: Any) -> None:
    client = owner(make_client, api_token="s3cret-token")
    ok = client.post(
        "/api/jobs", json={"urls": []}, headers={"Authorization": "Bearer s3cret-token"}
    )
    assert ok.status_code != 401 and ok.status_code != 403


def test_hosted_without_owner_fails_closed(make_client: Any) -> None:
    client = make_client(RAILWAY_ENVIRONMENT="production")
    response = client.get("/api/jobs")
    assert response.status_code == 401 and response.json()["code"] == "owner_required"
    assert client.get("/api/health").status_code == 200
    login = client.post("/api/auth/login", json={"email": EMAIL, "password": "x"}, headers=WEB)
    assert login.status_code == 503 and login.json()["code"] == "owner_required"


def test_public_flag_without_owner_fails_closed(make_client: Any) -> None:
    client = make_client(public="true")
    assert client.get("/api/jobs").status_code == 401


def test_hosted_with_owner_sets_secure_cookie(make_client: Any) -> None:
    client = owner(make_client, RAILWAY_ENVIRONMENT="production")
    response = sign_in(client)
    assert "Secure" in response.headers["set-cookie"]


def test_sign_in_attempts_are_limited(make_client: Any) -> None:
    client = owner(make_client)
    codes = [sign_in(client, password="wrong").status_code for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429


def test_local_use_without_owner_is_unchanged(make_client: Any) -> None:
    client = make_client()
    assert client.get("/api/jobs").status_code == 200
    me = client.get("/api/auth/me").json()
    assert me["signed_in"] is True and me["method"] == "local" and me["login_required"] is False
