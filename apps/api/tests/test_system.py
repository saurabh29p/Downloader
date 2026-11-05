from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from anyget import __version__
from anyget.main import create_app


@pytest.fixture
def client(env_settings: Path) -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["components"]) == {
        "yt_dlp",
        "yt_dlp_ejs",
        "deno",
        "ffmpeg",
        "ocrmypdf",
        "tesseract",
        "tesseract_langs",
        "calibre",
        "img2pdf",
    }
    assert body["components"]["img2pdf"]  # a Python dependency, always present
    assert body["components"]["yt_dlp"] == "2026.10.26"
    assert body["components"]["yt_dlp_ejs"]
    assert body["torrent"] is False  # off by default
    assert all(not p["loaded"] for p in body["plugins"])  # none enabled by default


def test_version(client: TestClient) -> None:
    body = client.get("/api/version").json()
    assert body["name"] == "anyget"
    assert body["version"] == __version__


def test_openapi_has_operation_ids(client: TestClient) -> None:
    schema = client.get("/api/openapi.json").json()
    assert schema["paths"]["/api/health"]["get"]["operationId"] == "getHealth"
