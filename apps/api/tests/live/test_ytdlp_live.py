"""Live yt-dlp tests: real network, Creative Commons or test media only.

Run in Docker (has ffmpeg + Deno):   make live
Or locally:                          cd apps/api && uv run pytest -m live tests/live
Skipped by default (pytest addopts: -m 'not live').

Media used (all openly licensed or published for testing):
- Big Buck Bunny, Blender Foundation, CC BY 3.0
  https://www.youtube.com/watch?v=aqz-KE-bpKQ
- Blender Studio channel uploads (CC BY), first 3 of the Videos tab
  https://www.youtube.com/@BlenderStudio/videos   (override: ANYGET_LIVE_PLAYLIST)
- yt-dlp's own Vimeo test video (Vimeo now asks for sign-in: needs your cookies)
  https://vimeo.com/56015672
- "What is PeerTube?" by Framasoft, CC BY-SA, on framatube.org (no sign-in needed)
  https://framatube.org/w/9c9de5e8-0a1e-484a-b099-e80766180a6d

YouTube often answers datacenter IPs (CI runners) with "confirm you're not a bot".
To run against your own account, put a cookies.txt from it in ANYGET_LIVE_COOKIES
(a GitHub secret for the Live tests workflow); it is written to the test's data dir.
"""

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from anyget.core.settings import Settings
from anyget.handlers.base import DownloadResult, HandlerError, JobContext
from anyget.handlers.ytdlp import YtDlpHandler

pytestmark = [pytest.mark.live]

YOUTUBE_VIDEO = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
PLAYLIST = os.environ.get("ANYGET_LIVE_PLAYLIST") or "https://www.youtube.com/@BlenderStudio/videos"
VIMEO_VIDEO = "https://vimeo.com/56015672"
PEERTUBE_VIDEO = "https://framatube.org/w/9c9de5e8-0a1e-484a-b099-e80766180a6d"
COOKIES = os.environ.get("ANYGET_LIVE_COOKIES", "")
JS_RUNTIME_WARNINGS = ("JavaScript runtime", "No supported JavaScript runtime")


@pytest.fixture
def handler(settings: Settings) -> YtDlpHandler:
    if COOKIES.strip():
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        cookie_file = settings.data_dir / "cookies.txt"
        cookie_file.write_text(COOKIES if COOKIES.endswith("\n") else COOKIES + "\n")
        cookie_file.chmod(0o600)
    return YtDlpHandler(settings)


@pytest.fixture(autouse=True)
def no_js_runtime_warnings(caplog: pytest.LogCaptureFixture):  # type: ignore[no-untyped-def]
    caplog.set_level(logging.WARNING, logger="anyget.ytdlp")
    yield
    bad = [
        r.getMessage()
        for r in caplog.records
        if any(w in r.getMessage() for w in JS_RUNTIME_WARNINGS)
    ]
    assert not bad, f"yt-dlp could not use Deno: {bad}"


def ffprobe(path: Path) -> dict[str, Any]:
    exe = shutil.which("ffprobe")
    if exe is None:
        pytest.skip("ffprobe is not installed")
    out = subprocess.run(  # noqa: S603
        [exe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    data: dict[str, Any] = json.loads(out)
    return data


async def download(
    handler: YtDlpHandler, settings: Settings, url: str, job_id: str, **options: object
) -> DownloadResult:
    probe = await handler.probe(url)
    job = JobContext(id=job_id, url=url, output_dir=settings.downloads_dir)
    return await handler.download(
        job, {**options, "probe": probe.model_dump(mode="json")}, lambda _p: None
    )


async def test_youtube_720p_mp4(handler: YtDlpHandler, settings: Settings) -> None:
    probe = await handler.probe(YOUTUBE_VIDEO)
    assert probe.extra["kind"] == "video" and "720" in probe.extra["presets"]
    result = await download(
        handler, settings, YOUTUBE_VIDEO, "live-720", preset="720", container="mp4"
    )
    video = result.paths[0]
    assert video.suffix == ".mp4" and video.stat().st_size > 1_000_000
    streams = ffprobe(video)["streams"]
    heights = [s.get("height") for s in streams if s.get("codec_type") == "video"]
    assert heights and max(h for h in heights if h) == 720
    assert any(s.get("codec_type") == "audio" for s in streams)


async def test_youtube_mp3_with_thumbnail(handler: YtDlpHandler, settings: Settings) -> None:
    result = await download(
        handler, settings, YOUTUBE_VIDEO, "live-mp3", preset="audio", audio_format="mp3"
    )
    audio = result.paths[0]
    assert audio.suffix == ".mp3"
    from mutagen.id3 import ID3

    tags: Any = ID3(audio)  # type: ignore[no-untyped-call]
    assert tags.getall("APIC"), "thumbnail was not embedded"
    assert tags.getall("TIT2"), "title tag missing"


async def test_three_items_from_a_playlist(handler: YtDlpHandler, settings: Settings) -> None:
    probe = await handler.probe(PLAYLIST, {"max_entries": 3})
    entries = probe.extra["entries"]
    assert probe.extra["kind"] in ("playlist", "channel") and len(entries) == 3
    for entry in entries:
        job = JobContext(
            id=f"live-pl-{entry['index']}", url=entry["url"], output_dir=settings.downloads_dir
        )
        result = await handler.download(
            job,
            {
                "preset": "360",
                "folder": "Live playlist",
                "index": entry["index"],
                "archive": probe.extra["archive"],
            },
            lambda _p: None,
        )
        assert result.paths and result.paths[0].name.startswith(f"{entry['index']:03d} - ")
    files = sorted((settings.downloads_dir / "Live playlist").iterdir())
    assert len([f for f in files if f.suffix in (".mp4", ".webm", ".mkv")]) == 3
    # Downloading the same item again is skipped by the per-source archive.
    first = entries[0]
    job = JobContext(id="live-pl-again", url=first["url"], output_dir=settings.downloads_dir)
    again = await handler.download(job, {"archive": probe.extra["archive"]}, lambda _p: None)
    assert again.note == "already_downloaded"


async def test_vimeo_video(handler: YtDlpHandler, settings: Settings) -> None:
    try:
        result = await download(handler, settings, VIMEO_VIDEO, "live-vimeo", preset="360")
    except HandlerError as exc:
        if exc.code == "login_required" and not COOKIES.strip():
            pytest.xfail(
                "Vimeo's web client needs sign-in without browser impersonation;"
                " set ANYGET_LIVE_COOKIES"
            )
        raise
    assert result.paths and result.paths[0].stat().st_size > 10_000


async def test_peertube_video(handler: YtDlpHandler, settings: Settings) -> None:
    """A non-YouTube site with an openly licensed video that needs no account."""
    probe = await handler.probe(PEERTUBE_VIDEO)
    assert probe.extra["kind"] == "video"
    result = await download(
        handler, settings, PEERTUBE_VIDEO, "live-peertube", preset="480", container="mp4"
    )
    video = result.paths[0]
    assert video.suffix == ".mp4" and video.stat().st_size > 100_000


def test_tools_present() -> None:
    from anyget.core.tools import tool_versions

    versions = tool_versions()
    assert versions.yt_dlp and versions.yt_dlp_ejs
    assert versions.deno, "Deno is required for YouTube"
    assert versions.ffmpeg, "ffmpeg is required for merging and audio"
