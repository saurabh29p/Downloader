# ruff: noqa: S106  (test tokens)
"""Access control: Cloudflare Access JWTs, bearer token, local requests, limits, headers."""

import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from anyget.core.auth import RateLimiter
from anyget.core.settings import get_settings
from anyget.main import create_app

TEAM = "myteam.cloudflareaccess.com"
AUD = "aud-tag-1234567890"
CERTS = f"https://{TEAM}/cdn-cgi/access/certs"

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def jwks(key: rsa.RSAPrivateKey = KEY, kid: str = "k1") -> dict[str, Any]:
    public = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    return {"keys": [{**public, "kid": kid, "alg": "RS256", "use": "sig"}]}


def token(
    key: rsa.RSAPrivateKey = KEY,
    kid: str = "k1",
    aud: str = AUD,
    iss: str = f"https://{TEAM}",
    exp_in: int = 600,
) -> str:
    now = int(time.time())
    claims = {"aud": [aud], "iss": iss, "iat": now, "exp": now + exp_in, "email": "me@example.org"}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


THROUGH_CF = {"Cf-Connecting-Ip": "203.0.113.7", "Cf-Ray": "8abc-LHR"}


@pytest.fixture
def make_client(env_settings: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    clients: list[TestClient] = []

    def make(**env: str) -> TestClient:
        for name, value in env.items():
            monkeypatch.setenv(f"ANYGET_{name.upper()}", value)
        get_settings.cache_clear()
        client = TestClient(create_app())
        client.__enter__()
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.__exit__(None, None, None)
    get_settings.cache_clear()


def test_local_requests_need_nothing(make_client: Any) -> None:
    client = make_client()
    response = client.get("/api/jobs")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in response.headers["content-security-policy"]


def test_cloudflare_without_access_setup_fails_closed(make_client: Any) -> None:
    client = make_client()
    response = client.get("/api/jobs", headers=THROUGH_CF)
    assert response.status_code == 401
    assert response.json()["code"] == "auth_required"
    assert "ANYGET_ACCESS_TEAM_DOMAIN" in response.json()["message"]


@respx.mock(assert_all_called=False)
def test_access_jwt_is_verified(make_client: Any, respx_mock: respx.MockRouter) -> None:
    respx_mock.route(host="testserver").pass_through()
    certs = respx_mock.get(CERTS).mock(return_value=httpx.Response(200, json=jwks()))
    client = make_client(access_team_domain=TEAM, access_aud=AUD)
    ok = client.get("/api/jobs", headers={**THROUGH_CF, "Cf-Access-Jwt-Assertion": token()})
    assert ok.status_code == 200
    again = client.get("/api/jobs", headers={**THROUGH_CF, "Cf-Access-Jwt-Assertion": token()})
    assert again.status_code == 200 and certs.call_count == 1  # keys are cached

    cases = {
        "missing": None,
        "wrong signer": token(key=OTHER),
        "wrong audience": token(aud="someone-else"),
        "wrong issuer": token(iss="https://evil.cloudflareaccess.com"),
        "expired": token(exp_in=-3600),
        "garbage": "not-a-jwt",
    }
    for name, value in cases.items():
        headers = dict(THROUGH_CF)
        if value is not None:
            headers["Cf-Access-Jwt-Assertion"] = value
        response = client.get("/api/jobs", headers=headers)
        assert response.status_code == 401, name


@respx.mock(assert_all_called=False)
def test_rotated_keys_are_fetched_again(
    make_client: Any, respx_mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    respx_mock.route(host="testserver").pass_through()
    certs = respx_mock.get(CERTS)
    certs.side_effect = [
        httpx.Response(200, json=jwks(kid="old")),
        httpx.Response(200, json=jwks(kid="new")),
    ]
    monkeypatch.setattr("anyget.core.auth.JWKS_RETRY", 0.0)  # no minute wait in the test
    client = make_client(access_team_domain=TEAM, access_aud=AUD)
    first = client.get(
        "/api/jobs", headers={**THROUGH_CF, "Cf-Access-Jwt-Assertion": token(kid="old")}
    )
    assert first.status_code == 200
    # A token signed with a new key id makes AnyGet read the keys again.
    rotated = client.get(
        "/api/jobs", headers={**THROUGH_CF, "Cf-Access-Jwt-Assertion": token(kid="new")}
    )
    assert rotated.status_code == 200 and certs.call_count == 2


def test_bearer_token(make_client: Any) -> None:
    client = make_client(api_token="s3cret-token")
    remote_ok = client.get(
        "/api/jobs", headers={**THROUGH_CF, "Authorization": "Bearer s3cret-token"}
    )
    assert remote_ok.status_code == 200
    wrong = client.get("/api/jobs", headers={"Authorization": "Bearer nope"})
    assert wrong.status_code == 401 and wrong.headers["www-authenticate"].startswith("Bearer")


def test_always_mode_needs_auth_even_locally(make_client: Any) -> None:
    client = make_client(auth_mode="always", api_token="s3cret-token")
    assert client.get("/api/jobs").status_code == 401
    assert (
        client.get("/api/jobs", headers={"Authorization": "Bearer s3cret-token"}).status_code == 200
    )


def test_remote_clients_are_rate_limited(make_client: Any) -> None:
    client = make_client(api_token="t", rate_limit_writes_per_minute="2")
    headers = {**THROUGH_CF, "Authorization": "Bearer t"}
    codes = [
        client.post("/api/jobs", json={"urls": []}, headers=headers).status_code for _ in range(3)
    ]
    assert codes[:2] != [429, 429] and codes[2] == 429
    limited = client.post("/api/jobs", json={"urls": []}, headers=headers)
    assert limited.headers["retry-after"] == "60" and limited.json()["code"] == "rate_limited"
    other_ip = {**headers, "Cf-Connecting-Ip": "198.51.100.9"}
    assert client.post("/api/jobs", json={"urls": []}, headers=other_ip).status_code != 429
    # Local requests are the owner's own and are not limited.
    assert all(client.post("/api/jobs", json={"urls": []}).status_code != 429 for _ in range(5))


def test_rate_limiter_window() -> None:
    limiter = RateLimiter()
    assert limiter.hit("a", "w", 2, now=0) is None
    assert limiter.hit("a", "w", 2, now=1) is None
    wait = limiter.hit("a", "w", 2, now=2)
    assert wait is not None and 50 < wait <= 60
    assert limiter.hit("a", "w", 2, now=61) is None  # the window moved on


def test_library_files_may_be_framed_by_the_site(make_client: Any, env_settings: Path) -> None:
    client = make_client()
    root = env_settings / "downloads"
    root.mkdir(parents=True, exist_ok=True)
    (root / "doc.pdf").write_bytes(b"%PDF-1.4")
    client.post("/api/library/scan")
    item = client.get("/api/library").json()["items"][0]
    response = client.get(f"/api/library/{item['id']}/file")
    assert response.headers["x-frame-options"] == "SAMEORIGIN"
    assert response.headers["content-security-policy"] == "sandbox"
