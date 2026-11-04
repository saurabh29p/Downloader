"""yt-dlp handler: offline, using recorded info dicts in tests/fixtures/ytdlp."""

import asyncio
import json
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, ClassVar

import pytest

from anyget.core.net import BlockedURLError
from anyget.core.settings import Settings
from anyget.handlers.base import HandlerError, JobContext, Progress, work_dir
from anyget.handlers.ytdlp import YtDlpHandler
from anyget.handlers.ytdlp_support.archive import archive_id, archive_key, archive_path
from anyget.handlers.ytdlp_support.errors import map_error
from anyget.handlers.ytdlp_support.formats import (
    available_presets,
    estimate_size,
    format_selector,
    normalize_formats,
)
from anyget.handlers.ytdlp_support.options import MediaOptions, build_params, output_template

FIXTURES = Path(__file__).parent / "fixtures" / "ytdlp"
VIDEO_URL = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return data


class FakeYDL:
    """Stands in for yt_dlp.YoutubeDL: serves fixtures and records what it was asked."""

    instances: ClassVar[list["FakeYDL"]] = []
    by_url: ClassVar[dict[str, dict[str, Any]]] = {}
    error: ClassVar[Exception | None] = None
    on_download: ClassVar[Callable[["FakeYDL", dict[str, Any]], dict[str, Any]] | None] = None

    def __init__(self, params: dict[str, Any]) -> None:
        self.params = params
        self.extracted: list[str] = []
        FakeYDL.instances.append(self)

    def __enter__(self) -> "FakeYDL":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def extract_info(self, url: str, download: bool = False) -> dict[str, Any]:
        self.extracted.append(url)
        if FakeYDL.error is not None:
            raise FakeYDL.error
        info = json.loads(json.dumps(FakeYDL.by_url[url]))
        return self.process_ie_result(info, download=True) if download else info

    def sanitize_info(self, info: dict[str, Any]) -> dict[str, Any]:
        return info

    def process_ie_result(self, info: dict[str, Any], download: bool = True) -> dict[str, Any]:
        assert FakeYDL.on_download is not None
        return FakeYDL.on_download(self, info)


@pytest.fixture
def fake_ydl(monkeypatch: pytest.MonkeyPatch) -> Iterator[type[FakeYDL]]:
    FakeYDL.instances = []
    FakeYDL.error = None
    FakeYDL.on_download = None
    FakeYDL.by_url = {
        VIDEO_URL: load("video"),
        "https://www.youtube.com/shorts/shortid0001": load("short"),
        "https://www.youtube.com/playlist?list=PLexample123": load("playlist"),
        "https://www.youtube.com/@BlenderStudio": load("channel_home"),
        "https://www.youtube.com/@BlenderStudio/videos": load("channel_videos"),
        "https://www.youtube.com/@BlenderStudio/shorts": load("channel_shorts"),
        "https://www.youtube.com/watch?v=live0000001": load("live"),
    }
    monkeypatch.setattr(YtDlpHandler, "_ydl", lambda self, params: FakeYDL(params))
    yield FakeYDL


@pytest.fixture
def handler(settings: Settings) -> YtDlpHandler:
    return YtDlpHandler(settings)


# ----- formats ---------------------------------------------------------------


def test_normalize_formats_drops_storyboards_and_drm() -> None:
    formats = normalize_formats(load("video"))
    ids = [f.id for f in formats]
    assert "sb0" not in ids and "drm1" not in ids
    assert formats[0].height == 1080
    top = next(f for f in formats if f.id == "298")
    assert top.label == "720p60" and top.vcodec == "H.264" and top.kind == "video"
    audio = next(f for f in formats if f.id == "251")
    assert audio.kind == "audio" and audio.acodec == "Opus" and audio.label == "135 kbps"
    muxed = next(f for f in formats if f.id == "18")
    assert muxed.kind == "video+audio" and muxed.size_is_estimate


def test_presets_and_sizes() -> None:
    formats = normalize_formats(load("video"))
    assert available_presets(formats) == ["best", "1080", "720", "480", "360", "audio"]
    assert estimate_size(formats, "720") == 21_000_000 + 1_700_000  # 720p60 + best audio
    assert estimate_size(formats, "audio") == 1_700_000
    vertical = normalize_formats(load("short"))
    assert "1080" in available_presets(vertical) or "best" in available_presets(vertical)


@pytest.mark.parametrize(
    ("preset", "expected"),
    [
        ("1080", "bv*[height<=1080]+ba/b[height<=1080]"),
        ("720", "bv*[height<=720]+ba/b[height<=720]"),
        ("best", "bv*+ba/b"),
        ("audio", "ba/b"),
    ],
)
def test_format_selector(preset: str, expected: str) -> None:
    assert format_selector(preset) == expected


def test_format_id_override_adds_audio() -> None:
    assert format_selector("720", "137") == "137+ba/137"


# ----- options → yt-dlp params ---------------------------------------------------


def params_for(tmp_path: Path, **options: Any) -> dict[str, Any]:
    return build_params(
        MediaOptions(**options),
        home=tmp_path / "home",
        temp=tmp_path / "tmp",
        cache_dir=tmp_path / "cache",
        archive_file=tmp_path / "archive.txt",
        cookie_file=None,
        deno="/usr/local/bin/deno",
        proxy=None,
    )


def pp_keys(params: dict[str, Any]) -> list[str]:
    return [pp["key"] for pp in params["postprocessors"]]


def test_safety_params_always_set(tmp_path: Path) -> None:
    params = params_for(tmp_path)
    assert params["geo_bypass"] is False
    assert params["allow_unplayable_formats"] is False
    assert params["external_downloader"] == {"default": "native"}
    assert params["hls_prefer_native"] is True
    assert params["noplaylist"] is True
    assert params["js_runtimes"] == {"deno": {"path": "/usr/local/bin/deno"}}
    assert "cookiefile" not in params


def test_video_720_mp4(tmp_path: Path) -> None:
    params = params_for(tmp_path, preset="720", container="mp4")
    assert params["format"] == "bv*[height<=720]+ba/b[height<=720]"
    assert params["merge_output_format"] == "mp4"
    assert params["format_sort"] == ["res", "ext:mp4:m4a"]
    assert pp_keys(params) == [
        "FFmpegThumbnailsConvertor",
        "FFmpegVideoRemuxer",
        "FFmpegMetadata",
        "EmbedThumbnail",
    ]
    assert params["writethumbnail"] is True


def test_audio_mp3_with_thumbnail(tmp_path: Path) -> None:
    params = params_for(tmp_path, preset="audio", audio_format="mp3")
    assert params["format"] == "ba/b"
    extract = next(pp for pp in params["postprocessors"] if pp["key"] == "FFmpegExtractAudio")
    assert extract["preferredcodec"] == "mp3" and extract["preferredquality"] == "0"
    assert "EmbedThumbnail" in pp_keys(params)


def test_subtitles_srt_and_embed(tmp_path: Path) -> None:
    srt = params_for(tmp_path, subtitles=["en", "hi"], auto_subtitles=True)
    assert srt["writesubtitles"] and srt["writeautomaticsub"]
    assert srt["subtitleslangs"] == ["en", "hi"]
    assert "FFmpegSubtitlesConvertor" in pp_keys(srt)
    embedded = params_for(tmp_path, subtitles=["en"], subtitles_mode="embed", container="mkv")
    assert "FFmpegEmbedSubtitle" in pp_keys(embedded)


def test_webm_skips_thumbnail_embed(tmp_path: Path) -> None:
    params = params_for(tmp_path, container="webm")
    assert "EmbedThumbnail" not in pp_keys(params)


def test_output_template_escapes_and_numbers() -> None:
    assert output_template(MediaOptions(index=7)).startswith("007 - %(title).150B")
    assert output_template(MediaOptions()) == "%(title).150B [%(id)s].%(ext)s"


def test_options_validation() -> None:
    with pytest.raises(ValueError):
        MediaOptions(format_id="137; rm -rf /")
    with pytest.raises(ValueError):
        MediaOptions(archive="../../etc/passwd")
    assert MediaOptions(subtitles=["en", "bad lang!", "pt-BR"]).subtitles == ["en", "pt-BR"]


# ----- probe -----------------------------------------------------------------


async def test_probe_video(handler: YtDlpHandler, fake_ydl: type[FakeYDL]) -> None:
    probe = await handler.probe(VIDEO_URL)
    extra = probe.extra
    assert extra["kind"] == "video"
    assert probe.title.startswith("Big Buck Bunny")
    assert extra["presets"] == ["best", "1080", "720", "480", "360", "audio"]
    assert extra["subtitles"] == ["en"]  # live_chat is not a subtitle
    assert extra["auto_captions"] == ["ar", "en", "hi"]
    assert extra["chapters"] == 2
    assert extra["is_short"] is False
    assert extra["saved"] is False
    assert probe.thumbnail and "maxresdefault" in probe.thumbnail
    params = fake_ydl.instances[0].params
    assert params["extract_flat"] == "in_playlist" and params["geo_bypass"] is False


async def test_probe_short(handler: YtDlpHandler, fake_ydl: type[FakeYDL]) -> None:
    probe = await handler.probe("https://www.youtube.com/shorts/shortid0001")
    assert probe.extra["is_short"] is True


async def test_probe_playlist_marks_saved_items(
    handler: YtDlpHandler, fake_ydl: type[FakeYDL], settings: Settings
) -> None:
    key = archive_key("YoutubeTab", "PLexample123")
    archive_path(settings.data_dir, key).write_text(archive_id("Youtube", "eRsGyueVLvQ") + "\n")
    probe = await handler.probe("https://www.youtube.com/playlist?list=PLexample123")
    extra = probe.extra
    assert extra["kind"] == "playlist" and extra["count"] == 3 and extra["archive"] == key
    assert [e["index"] for e in extra["entries"]] == [1, 2, 3]
    assert [e["saved"] for e in extra["entries"]] == [False, True, False]
    assert extra["entries"][0]["thumbnail"].endswith("hqdefault.jpg")
    assert extra["entries"][0]["archive_id"] == "youtube aqz-KE-bpKQ"


async def test_probe_channel_defaults_to_videos_tab(
    handler: YtDlpHandler, fake_ydl: type[FakeYDL]
) -> None:
    probe = await handler.probe("https://www.youtube.com/@BlenderStudio")
    assert probe.extra["kind"] == "channel"
    assert probe.extra["tabs"] == ["videos", "shorts", "streams"]
    assert probe.extra["tab"] == "videos"
    assert fake_ydl.instances[0].extracted == [
        "https://www.youtube.com/@BlenderStudio",
        "https://www.youtube.com/@BlenderStudio/videos",
    ]


async def test_probe_channel_shorts_tab(handler: YtDlpHandler, fake_ydl: type[FakeYDL]) -> None:
    probe = await handler.probe("https://www.youtube.com/@BlenderStudio", {"tab": "shorts"})
    assert probe.extra["tab"] == "shorts"
    assert all(e["is_short"] for e in probe.extra["entries"])


async def test_probe_live_is_refused(handler: YtDlpHandler, fake_ydl: type[FakeYDL]) -> None:
    with pytest.raises(HandlerError) as info:
        await handler.probe("https://www.youtube.com/watch?v=live0000001")
    assert info.value.code == "live_not_finished"


# ----- errors ------------------------------------------------------------------


@pytest.mark.parametrize(("code", "message"), sorted(load("errors").items()))
def test_error_reasons(code: str, message: str) -> None:
    from yt_dlp.utils import DownloadError

    mapped = map_error(DownloadError(message))
    assert isinstance(mapped, HandlerError)
    assert mapped.code == code
    assert not mapped.message.startswith("ERROR")


def test_geo_restricted_class() -> None:
    from yt_dlp.utils import GeoRestrictedError

    mapped = map_error(GeoRestrictedError("blocked", countries=["DE"]))
    assert isinstance(mapped, HandlerError) and mapped.code == "geo_blocked"


def test_blocked_url_passes_through() -> None:
    from yt_dlp.utils import DownloadError

    inner = BlockedURLError("127.0.0.1 resolves to a private or reserved address")
    mapped = map_error(DownloadError("ERROR: Unable to download webpage: ...", (None, inner, None)))
    assert isinstance(mapped, BlockedURLError)


async def test_probe_maps_errors(handler: YtDlpHandler, fake_ydl: type[FakeYDL]) -> None:
    from yt_dlp.utils import DownloadError

    fake_ydl.error = DownloadError(load("errors")["members_only"])
    with pytest.raises(HandlerError) as info:
        await handler.probe(VIDEO_URL)
    assert info.value.code == "members_only"


# ----- download ----------------------------------------------------------------


def simulate_download(name: str = "Big Buck Bunny [aqz-KE-bpKQ]") -> Callable[..., dict[str, Any]]:
    def run(ydl: FakeYDL, info: dict[str, Any]) -> dict[str, Any]:
        home = Path(ydl.params["paths"]["home"])
        for hook in ydl.params["progress_hooks"]:
            hook(
                {
                    "status": "downloading",
                    "filename": "v.mp4",
                    "downloaded_bytes": 500,
                    "total_bytes": 1000,
                }
            )
            hook({"status": "finished", "filename": "v.mp4", "total_bytes": 1000})
            hook(
                {
                    "status": "downloading",
                    "filename": "a.m4a",
                    "downloaded_bytes": 100,
                    "total_bytes": 200,
                }
            )
            hook({"status": "finished", "filename": "a.m4a", "total_bytes": 200})
        for hook in ydl.params["postprocessor_hooks"]:
            hook({"status": "started", "postprocessor": "Merger"})
        final = home / f"{name}.mp4"
        final.write_bytes(b"video")
        (home / f"{name}.en.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n")
        Path(ydl.params["download_archive"]).write_text(f"youtube {info['id']}\n")
        return {**info, "requested_downloads": [{"filepath": str(final)}]}

    return run


async def collect_progress(
    handler: YtDlpHandler, job: JobContext, options: dict[str, Any]
) -> tuple[Any, list[Progress]]:
    seen: list[Progress] = []
    result = await handler.download(job, options, seen.append)
    await asyncio.sleep(0)  # let call_soon_threadsafe callbacks run
    return result, seen


async def test_download_reuses_probe_and_collects_extras(
    handler: YtDlpHandler, fake_ydl: type[FakeYDL], settings: Settings
) -> None:
    fake_ydl.on_download = simulate_download()
    await handler.probe(VIDEO_URL)
    job = JobContext(id="j1", url=VIDEO_URL, output_dir=settings.downloads_dir)
    result, seen = await collect_progress(
        handler, job, {"preset": "720", "container": "mp4", "subtitles": ["en"]}
    )
    assert [p.name for p in result.paths] == [
        "Big Buck Bunny [aqz-KE-bpKQ].mp4",
        "Big Buck Bunny [aqz-KE-bpKQ].en.srt",
    ]
    assert len(fake_ydl.instances) == 2  # probe + download, no second extraction
    assert fake_ydl.instances[1].extracted == []
    assert seen[-1].downloaded == 1200 and seen[-1].total == 1200
    assert seen[-1].message == "merging"
    assert not work_dir(settings.downloads_dir, "j1").exists()  # temp folder cleaned


async def test_download_skips_archived(
    handler: YtDlpHandler, fake_ydl: type[FakeYDL], settings: Settings
) -> None:
    key = archive_key("Youtube", None)
    archive_path(settings.data_dir, key).write_text("youtube aqz-KE-bpKQ\n")
    job = JobContext(id="j2", url=VIDEO_URL, output_dir=settings.downloads_dir)
    result = await handler.download(job, {}, lambda _p: None)
    assert result.paths == [] and result.note == "already_downloaded"


async def test_download_date_window(
    handler: YtDlpHandler, fake_ydl: type[FakeYDL], settings: Settings
) -> None:
    job = JobContext(id="j3", url=VIDEO_URL, output_dir=settings.downloads_dir)
    result = await handler.download(job, {"date_after": "20200101"}, lambda _p: None)
    assert result.note == "outside_date_range"


async def test_download_into_playlist_folder(
    handler: YtDlpHandler, fake_ydl: type[FakeYDL], settings: Settings
) -> None:
    fake_ydl.on_download = simulate_download("001 - Big Buck Bunny [aqz-KE-bpKQ]")
    job = JobContext(id="j4", url=VIDEO_URL, output_dir=settings.downloads_dir)
    result = await handler.download(
        job,
        {"folder": "Open Movies", "index": 1, "archive": "youtubetab-PLexample123"},
        lambda _p: None,
    )
    assert result.paths[0].parent.name == "Open Movies"
    params = fake_ydl.instances[-1].params
    assert params["outtmpl"]["default"].startswith("001 - ")
    assert params["download_archive"].endswith("youtubetab-PLexample123.txt")


async def test_download_refuses_playlist_url(
    handler: YtDlpHandler, fake_ydl: type[FakeYDL], settings: Settings
) -> None:
    url = "https://www.youtube.com/playlist?list=PLexample123"
    job = JobContext(id="j5", url=url, output_dir=settings.downloads_dir)
    with pytest.raises(HandlerError) as info:
        await handler.download(job, {}, lambda _p: None)
    assert info.value.code == "unsupported"


async def test_cancel_stops_the_worker_thread(
    handler: YtDlpHandler, fake_ydl: type[FakeYDL], settings: Settings
) -> None:
    started = threading.Event()
    stopped = threading.Event()

    def slow(ydl: FakeYDL, info: dict[str, Any]) -> dict[str, Any]:
        hook = ydl.params["progress_hooks"][0]
        try:
            for i in range(1000):
                started.set()
                hook(
                    {
                        "status": "downloading",
                        "filename": "v",
                        "downloaded_bytes": i,
                        "total_bytes": 1000,
                    }
                )
                time.sleep(0.01)
        finally:
            stopped.set()
        raise AssertionError("should have been cancelled")

    fake_ydl.on_download = slow
    job = JobContext(id="j6", url=VIDEO_URL, output_dir=settings.downloads_dir)
    task = asyncio.create_task(handler.download(job, {}, lambda _p: None))
    await asyncio.to_thread(started.wait, 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stopped.is_set()


async def test_cookies_are_copied_per_job(
    handler: YtDlpHandler, fake_ydl: type[FakeYDL], settings: Settings
) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "cookies.txt").write_text("# Netscape HTTP Cookie File\n")
    seen_mode: list[int] = []

    def run(ydl: FakeYDL, info: dict[str, Any]) -> dict[str, Any]:
        cookie = Path(ydl.params["cookiefile"])
        seen_mode.append(cookie.stat().st_mode & 0o777)
        return simulate_download()(ydl, info)

    fake_ydl.on_download = run
    job = JobContext(id="j7", url=VIDEO_URL, output_dir=settings.downloads_dir)
    await handler.download(job, {}, lambda _p: None)
    assert seen_mode == [0o600]
    assert fake_ydl.instances[-1].extracted == [VIDEO_URL]  # re-extracted with cookies
    assert not (work_dir(settings.downloads_dir, "j7") / "cookies.txt").exists()
