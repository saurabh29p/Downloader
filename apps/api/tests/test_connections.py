# ruff: noqa: S105, S106  (fake test secrets)
"""Connections (v2): cookies and keys per site, encrypted at rest, never returned."""

import logging
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from anyget.connections.sites import BY_ID
from anyget.connections.store import ConnectionStore, cookie_expiry, parse_cookies
from anyget.core.db import Database
from anyget.core.settings import Settings, get_settings
from anyget.core.settings_store import SettingRow
from anyget.handlers.ytdlp import YtDlpHandler
from anyget.main import create_app

SECRET = "very-secret-cookie-value"
FUTURE = int(time.time()) + 30 * 86400
PAST = int(time.time()) - 86400


def line(domain: str, name: str, value: str = SECRET, expires: int = FUTURE) -> str:
    return f"{domain}\tTRUE\t/\tTRUE\t{expires}\t{name}\t{value}\n"


COOKIES = (
    "# Netscape HTTP Cookie File\n"
    + line(".youtube.com", "LOGIN_INFO")
    + line(".youtube.com", "PREF", "f1=1")
    + line(".reddit.com", "reddit_session")
    + line(".bank.example", "session", "do-not-keep")
)


@pytest.fixture
def client(env_settings: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("ANYGET_DPLA_KEY", "from-env")
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def site(view: dict[str, object], site_id: str) -> dict[str, object]:
    sites = view["sites"]
    assert isinstance(sites, list)
    return next(s for s in sites if s["id"] == site_id)


def test_cookies_are_kept_per_site_and_encrypted(client: TestClient, env_settings: Path) -> None:
    services = client.app.state.services  # type: ignore[attr-defined]
    assert site(client.get("/api/connections").json(), "youtube")["status"] == "not_connected"

    saved = client.put("/api/connections/youtube", json={"cookies": COOKIES})
    assert saved.status_code == 200 and SECRET not in saved.text
    youtube = site(saved.json(), "youtube")
    assert youtube["status"] == "connected" and youtube["cookie_count"] == 2
    assert youtube["expires_on"] is not None

    db_bytes = (env_settings / "data" / "anyget.db").read_bytes()
    assert SECRET.encode() not in db_bytes  # encrypted at rest
    text, _ = services.connections.cookies_for("www.youtube.com")
    assert SECRET in text and "reddit" not in text and "bank.example" not in text

    wrong = client.put("/api/connections/vimeo", json={"cookies": COOKIES})
    assert wrong.status_code == 400 and wrong.json()["code"] == "invalid_connection"
    bad = client.put("/api/connections/youtube", json={"cookies": "not a cookies file"})
    assert bad.status_code == 400

    assert client.delete("/api/connections/youtube").status_code == 204
    assert services.connections.cookies_for("youtube.com") == ("", None)


def test_expired_cookies_show_as_expired(client: TestClient) -> None:
    old = "# Netscape HTTP Cookie File\n" + line(".x.com", "auth_token", expires=PAST)
    view = client.put("/api/connections/x", json={"cookies": old}).json()
    assert site(view, "x")["status"] == "expired"
    test = client.post("/api/connections/x/test").json()
    assert test == {"ok": False, "result": "expired"}


def test_import_splits_one_file_into_sites(client: TestClient) -> None:
    result = client.post("/api/connections/import", json={"cookies": COOKIES})
    assert result.status_code == 200
    body = result.json()
    assert sorted(body["imported"]) == ["reddit", "youtube"]
    assert SECRET not in result.text and "do-not-keep" not in result.text
    none = client.post(
        "/api/connections/import",
        json={"cookies": "# Netscape HTTP Cookie File\n" + line(".bank.example", "s")},
    )
    assert none.status_code == 400


def test_keys_fill_settings_and_removing_restores_env(client: TestClient) -> None:
    settings = client.app.state.services.settings  # type: ignore[attr-defined]
    assert site(client.get("/api/connections").json(), "dpla")["status"] == "server"
    view = client.put("/api/connections/dpla", json={"fields": {"token": "mine-123"}}).json()
    assert site(view, "dpla")["status"] == "connected" and "mine-123" not in str(view)
    assert settings.dpla_key == "mine-123"
    client.delete("/api/connections/dpla")
    assert settings.dpla_key == "from-env"

    half = client.put("/api/connections/kaggle", json={"fields": {"username": "me"}})
    assert half.status_code == 400
    both = {"fields": {"username": "me", "key": "k-1"}}
    assert client.put("/api/connections/kaggle", json=both).status_code == 200
    assert (settings.kaggle_username, settings.kaggle_key) == ("me", "k-1")
    assert client.get("/api/connections/nope").status_code in (404, 405)
    assert client.put("/api/connections/nope", json=both).status_code == 404


@respx.mock(assert_all_called=False)
def test_key_test_calls_the_service(client: TestClient, respx_mock: respx.MockRouter) -> None:
    respx_mock.route(host="testserver").pass_through()
    github = respx_mock.get("https://api.github.com/user")
    github.side_effect = [httpx.Response(200, json={}), httpx.Response(401, json={})]
    client.put("/api/connections/github", json={"fields": {"token": "ghp_x"}})
    assert client.post("/api/connections/github/test").json() == {"ok": True, "result": "ok"}
    assert github.calls[0].request.headers["authorization"] == "Bearer ghp_x"
    assert client.post("/api/connections/github/test").json()["result"] == "rejected"
    assert site(client.get("/api/connections").json(), "github")["last_test_ok"] is False
    client.put("/api/connections/europeana", json={"fields": {"token": "e"}})
    assert client.post("/api/connections/europeana/test").json()["result"] == "untested"
    assert client.post("/api/connections/vimeo/test").status_code == 400  # not connected


def test_proxy_per_site(client: TestClient) -> None:
    store = client.app.state.services.connections  # type: ignore[attr-defined]
    client.put("/api/connections/youtube", json={"cookies": COOKIES})
    bad = client.put("/api/connections/youtube", json={"proxy": "ftp://proxy:1"})
    assert bad.status_code == 422
    view = client.put("/api/connections/youtube", json={"proxy": "socks5://10.0.0.2:1080"}).json()
    assert site(view, "youtube")["proxy"] is True and "10.0.0.2" not in str(view)
    assert store.proxy_for("m.youtube.com") == "socks5://10.0.0.2:1080"
    assert store.proxy_for("vimeo.com") is None


def test_v1_secrets_move_in_and_plain_files_go(env_settings: Path) -> None:
    data = env_settings / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "cookies.txt").write_text(COOKIES)
    settings = Settings(data_dir=data, downloads_dir=env_settings / "downloads")
    db = Database(settings)
    db.create_all()
    with db.session() as session:
        session.add(SettingRow(key="hf_token", value='"hf_old"'))
        session.commit()
    db.dispose()

    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        view = client.get("/api/connections").json()
        assert site(view, "huggingface")["status"] == "connected"
        assert site(view, "youtube")["status"] == "connected"
        assert client.app.state.services.settings.hf_token == "hf_old"  # type: ignore[attr-defined]
    get_settings.cache_clear()
    assert not (data / "cookies.txt").exists()
    key = data / "secrets.key"
    assert key.is_file() and key.stat().st_mode & 0o777 == 0o600
    db = Database(settings)
    with db.session() as session:
        assert session.get(SettingRow, "hf_token") is None
    db.dispose()


def test_ytdlp_gets_only_the_sites_cookies(settings: Settings, tmp_path: Path) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(settings)
    db.create_all()
    store = ConnectionStore(db, settings)
    store.import_cookies("owner", COOKIES)
    handler = YtDlpHandler(settings, store)
    temp = tmp_path / "job"
    temp.mkdir()
    cookie_file = handler._job_cookies(temp, "https://www.youtube.com/watch?v=x")
    assert cookie_file is not None
    text = cookie_file.read_text()
    assert "LOGIN_INFO" in text and "reddit_session" not in text
    assert cookie_file.stat().st_mode & 0o777 == 0o600
    cookie_file.unlink()
    assert handler._job_cookies(temp, "https://vimeo.com/1") is None
    db.dispose()


def test_bad_secrets_key_is_refused(settings: Settings) -> None:
    settings.secrets_key = "not-a-fernet-key"
    db = Database(settings)
    with pytest.raises(RuntimeError, match="anyget gen-key"):
        ConnectionStore(db, settings)


def test_cookie_helpers() -> None:
    rows = parse_cookies(COOKIES)
    assert len(rows) == 4
    expiry = cookie_expiry(BY_ID["youtube"], rows[:2])
    assert expiry is not None and int(expiry.timestamp()) == FUTURE
    session_only = parse_cookies("# x\n" + line(".vimeo.com", "vimeo", expires=0))
    assert cookie_expiry(BY_ID["vimeo"], session_only) is None


def test_secrets_never_reach_the_logs(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    client.post("/api/connections/import", json={"cookies": COOKIES})
    client.put("/api/connections/github", json={"fields": {"token": "ghp_logcheck"}})
    assert SECRET not in caplog.text and "ghp_logcheck" not in caplog.text
