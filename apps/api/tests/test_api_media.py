"""API pieces added for media: probe options, playlist items, archive skips, cookies."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from anyget.core.settings import Settings
from anyget.handlers.base import Probe
from anyget.handlers.ytdlp import YtDlpHandler
from anyget.handlers.ytdlp_support.archive import archive_path
from anyget.main import create_app


@pytest.fixture
def client(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    seen: list[dict[str, Any] | None] = []

    async def fake_probe(
        self: YtDlpHandler, url: str, options: dict[str, Any] | None = None
    ) -> Probe:
        seen.append(options)
        return Probe(url=url, handler="ytdlp", title="t", extra={"kind": "channel"})

    async def never_finish(self: YtDlpHandler, *args: Any) -> Any:
        import asyncio

        await asyncio.Event().wait()

    monkeypatch.setattr(YtDlpHandler, "probe", fake_probe)
    monkeypatch.setattr(YtDlpHandler, "download", never_finish)
    with TestClient(create_app(settings)) as test_client:
        test_client.seen = seen
        yield test_client


def test_probe_passes_options(client: TestClient) -> None:
    body = {"url": "https://www.youtube.com/@BlenderStudio", "options": {"tab": "shorts"}}
    response = client.post("/api/probe", json=body)
    assert response.status_code == 200
    assert response.json()["handler"] == "ytdlp"
    assert client.seen == [{"tab": "shorts"}]


def test_items_with_own_options_and_archive_skip(client: TestClient, settings: Settings) -> None:
    archive_path(settings.data_dir, "youtubetab-PL1").write_text("youtube saved00001\n")
    shared = {"preset": "720", "archive": "youtubetab-PL1", "folder": "Open Movies"}
    items = [
        {
            "url": f"https://www.youtube.com/watch?v={vid}",
            "options": {"index": i, "archive_id": f"youtube {vid}"},
        }
        for i, vid in enumerate(["aaaaaaaaaaa", "saved00001", "bbbbbbbbbbb"], start=1)
    ]
    response = client.post("/api/jobs", json={"items": items, "options": shared})
    assert response.status_code == 201
    body = response.json()
    assert [j["options"]["index"] for j in body["jobs"]] == [1, 3]
    assert body["jobs"][0]["options"]["preset"] == "720"
    assert [s["code"] for s in body["skipped"]] == ["already_downloaded"]


def test_audio_of_saved_playlist_items_is_queued(client: TestClient, settings: Settings) -> None:
    archive_path(settings.data_dir, "youtubetab-PL2").write_text("youtube saved00002\n")
    items = [
        {
            "url": "https://www.youtube.com/watch?v=saved00002",
            "options": {"archive_id": "youtube saved00002"},
        }
    ]
    audio = {"preset": "audio", "audio_format": "mp3", "archive": "youtubetab-PL2"}
    body = client.post("/api/jobs", json={"items": items, "options": audio}).json()
    assert len(body["jobs"]) == 1 and body["skipped"] == []


def test_same_link_with_different_options_is_not_dropped(client: TestClient) -> None:
    url = "https://www.youtube.com/watch?v=aaaaaaaaaaa"
    items = [
        {"url": url, "options": {"preset": "720"}},
        {"url": url, "options": {"preset": "audio", "audio_format": "mp3"}},
        {"url": url, "options": {"preset": "720"}},  # a true duplicate: one job only
    ]
    body = client.post("/api/jobs", json={"items": items}).json()
    assert sorted(j["options"]["preset"] for j in body["jobs"]) == ["720", "audio"]


def test_create_needs_urls_or_items(client: TestClient) -> None:
    assert client.post("/api/jobs", json={}).status_code == 422
