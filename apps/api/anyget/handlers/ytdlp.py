"""Video and audio sites through yt-dlp (YouTube, Vimeo, Bilibili, SoundCloud and 1,800+ more).

yt-dlp is blocking, so it runs in a worker thread. Its network access is guarded by
core.net_guard (installed in __init__), its safety options are fixed in
ytdlp_support.options, and anything it cannot legally download (DRM, members-only,
paid, private, age gate, region, unfinished live) is reported, never worked around.
"""

import asyncio
import contextlib
import logging
import re
import shutil
import tempfile
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from anyget.core import net_guard
from anyget.core.filenames import ensure_inside, safe_join
from anyget.core.net import BlockedURLError
from anyget.core.settings import Settings
from anyget.core.tools import deno_path
from anyget.handlers.base import (
    Choice,
    DownloadResult,
    HandlerError,
    JobRef,
    Probe,
    Progress,
    ProgressCallback,
    work_dir,
)
from anyget.handlers.ytdlp_support.archive import archive_id, archive_key, archive_path, contains
from anyget.handlers.ytdlp_support.errors import map_error
from anyget.handlers.ytdlp_support.formats import (
    available_presets,
    estimate_size,
    normalize_formats,
)
from anyget.handlers.ytdlp_support.options import MediaOptions, build_params, probe_params

log = logging.getLogger("anyget.ytdlp")

CACHE_TTL = 600.0
CACHE_SIZE = 64
CANCEL_WAIT = 30.0
TABS = ("videos", "shorts", "streams")
_TAB_URL = re.compile(r"/(videos|shorts|streams|live)/?$")
_UNFINISHED_LIVE = {"is_live", "is_upcoming", "post_live"}

# Post-processor name → note code shown while it runs.
POSTPROCESSOR_NOTES = {
    "Merger": "merging",
    "FFmpegMerger": "merging",
    "FFmpegExtractAudio": "extracting_audio",
    "FFmpegVideoRemuxer": "remuxing",
    "FFmpegEmbedSubtitle": "embedding_subtitles",
    "FFmpegSubtitlesConvertor": "converting_subtitles",
    "FFmpegMetadata": "adding_metadata",
    "EmbedThumbnail": "embedding_thumbnail",
    "FFmpegThumbnailsConvertor": "converting_thumbnail",
}


class ProbeOptions(BaseModel):
    tab: Literal["videos", "shorts", "streams"] | None = None
    max_entries: int = Field(default=200, ge=1, le=1000)


class YtDlpLogger:
    """Sends yt-dlp output to our logs. Warnings are also kept for tests and the live suite."""

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def debug(self, msg: str) -> None:
        if not msg.startswith("[debug] "):
            log.debug("%s", msg)

    def info(self, msg: str) -> None:
        log.debug("%s", msg)

    def warning(self, msg: str) -> None:
        self.warnings.append(msg)
        log.warning("%s", msg)

    def error(self, msg: str) -> None:
        log.error("%s", msg)


@lru_cache(maxsize=1)
def _extractors() -> tuple[Any, ...]:
    from yt_dlp.extractor import gen_extractor_classes

    return tuple(ie for ie in gen_extractor_classes() if ie.ie_key() != "Generic")


def _thumbnail(entry: dict[str, Any]) -> str | None:
    if entry.get("thumbnail"):
        return str(entry["thumbnail"])
    thumbs = [t for t in entry.get("thumbnails") or [] if t.get("url")]
    if not thumbs:
        return None
    best = max(thumbs, key=lambda t: (t.get("width") or 0) * (t.get("height") or 0))
    return str(best["url"])


def _is_tab_list(info: dict[str, Any]) -> bool:
    entries = [e for e in info.get("entries") or [] if e]
    return bool(entries) and all(
        e.get("_type") in ("url", "playlist") and _TAB_URL.search(str(e.get("url", "")))
        for e in entries
    )


def _tab_of(url: str) -> str | None:
    match = _TAB_URL.search(url)
    if not match:
        return None
    tab = match.group(1)
    return "streams" if tab == "live" else tab


class CookieSource(Protocol):
    """Connections (anyget/connections/store.py): the user's cookies and proxy per site."""

    def write_cookie_file(self, url_host: str, target: Path) -> bool: ...

    def proxy_for(self, url_host: str) -> str | None: ...


def _host_port(proxy: str) -> str | None:
    parts = urlsplit(proxy)
    return f"{parts.hostname}:{parts.port}" if parts.hostname and parts.port else None


class YtDlpHandler:
    name = "ytdlp"

    def __init__(self, settings: Settings, connections: CookieSource | None = None) -> None:
        self.settings = settings
        self.connections = connections
        self._allow = list(settings.net_allowlist)
        if settings.proxy and (hp := _host_port(settings.proxy)):
            self._allow.append(hp)
        net_guard.install(self._allow)
        self.cache_dir = settings.data_dir / "ytdlp-cache"
        self._cache: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=settings.max_concurrent_downloads + 2, thread_name_prefix="ytdlp"
        )

    # ----- routing ---------------------------------------------------------

    def can_handle(self, url: str) -> bool:
        if urlsplit(url).scheme not in ("http", "https"):
            return False
        return any(ie.suitable(url) for ie in _extractors())

    # ----- probe -----------------------------------------------------------

    async def probe(self, url: str, options: dict[str, Any] | None = None) -> Probe:
        opts = ProbeOptions.model_validate(options or {})
        loop = asyncio.get_running_loop()
        info, tabs = await loop.run_in_executor(self._executor, self._extract, url, opts)
        return self._to_probe(url, info, tabs, opts)

    async def search_videos(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """YouTube search results (flat, no formats), for the universal search."""
        opts = ProbeOptions(max_entries=limit)
        loop = asyncio.get_running_loop()
        info, _ = await loop.run_in_executor(
            self._executor, self._extract, f"ytsearch{limit}:{query}", opts
        )
        found = []
        for entry in info.get("entries") or []:
            if not entry or not entry.get("id"):
                continue
            found.append(
                {
                    "id": str(entry["id"]),
                    "title": str(entry.get("title") or entry["id"]),
                    "url": str(
                        entry.get("url") or f"https://www.youtube.com/watch?v={entry['id']}"
                    ),
                    "duration": entry.get("duration"),
                    "channel": entry.get("channel") or entry.get("uploader"),
                    "thumbnail": _thumbnail(entry),
                }
            )
        return found

    def _ydl(self, params: dict[str, Any]) -> Any:
        from yt_dlp import YoutubeDL

        return YoutubeDL({**params, "logger": params.get("logger") or YtDlpLogger()})

    def _proxy(self, url: str) -> str | None:
        """The connected site's own proxy, else the global one."""
        host = urlsplit(url).hostname or ""
        proxy = self.connections.proxy_for(host) if self.connections else None
        if proxy and (hp := _host_port(proxy)) and hp not in self._allow:
            self._allow.append(hp)  # the owner chose this proxy for the site
            net_guard.install(self._allow)
        return proxy or self.settings.proxy or None

    def _extract(self, url: str, opts: ProbeOptions) -> tuple[dict[str, Any], list[str]]:
        params = probe_params(
            max_entries=opts.max_entries,
            cache_dir=self.cache_dir,
            deno=deno_path(),
            proxy=self._proxy(url),
        )
        with tempfile.TemporaryDirectory(prefix="anyget-probe-") as tmp:
            # A connected account (cookies) can see what it is allowed to see.
            cookies = Path(tmp) / "cookies.txt"
            if self.connections and self.connections.write_cookie_file(
                urlsplit(url).hostname or "", cookies
            ):
                params["cookiefile"] = str(cookies)
            return self._extract_with(url, opts, params)

    def _extract_with(
        self, url: str, opts: ProbeOptions, params: dict[str, Any]
    ) -> tuple[dict[str, Any], list[str]]:
        try:
            with self._ydl(params) as ydl:
                info: dict[str, Any] = ydl.extract_info(url, download=False)
                tabs: list[str] = []
                if _is_tab_list(info):
                    # A channel's home page: choose a tab (Videos by default).
                    available = {
                        _tab_of(str(e["url"])): str(e["url"]) for e in info["entries"] if e
                    }
                    tabs = [t for t in TABS if t in available]
                    wanted = opts.tab if opts.tab in available else (tabs[0] if tabs else None)
                    if wanted:
                        info = ydl.extract_info(available[wanted], download=False)
                        info["_anyget_tab"] = wanted
                elif _tab_of(url):
                    info["_anyget_tab"] = _tab_of(url)
                    tabs = list(TABS)
                info = ydl.sanitize_info(info)
        except BlockedURLError:
            raise
        except Exception as exc:  # yt-dlp raises many types; map them all
            raise map_error(exc) from exc
        if info.get("_type") not in ("playlist", "multi_video"):
            self._remember(url, info)
        return info, tabs

    def _remember(self, url: str, info: dict[str, Any]) -> None:
        with self._lock:
            for key in {url, str(info.get("webpage_url") or url)}:
                self._cache[key] = (time.monotonic(), info)
                self._cache.move_to_end(key)
            while len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)

    def _recall(self, url: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._cache.get(url)
            if item and time.monotonic() - item[0] < CACHE_TTL:
                return item[1]
        return None

    def _to_probe(
        self, url: str, info: dict[str, Any], tabs: list[str], opts: ProbeOptions
    ) -> Probe:
        extractor = str(info.get("extractor_key") or info.get("ie_key") or "generic")
        if info.get("_type") in ("playlist", "multi_video"):
            return self._playlist_probe(url, info, tabs, extractor)

        if info.get("live_status") in _UNFINISHED_LIVE:
            raise HandlerError(
                "live_not_finished",
                "this is a live or upcoming stream; it can be downloaded after it ends",
            )
        formats = normalize_formats(info)
        if not formats:
            raise HandlerError("unavailable", "no downloadable formats were found")
        presets = available_presets(formats)
        sizes = {preset: estimate_size(formats, preset) for preset in presets}
        width, height = info.get("width"), info.get("height")
        webpage = str(info.get("webpage_url") or url)
        is_short = "/shorts/" in webpage or bool(width and height and height > width)
        video_id = str(info.get("id") or "")
        subtitles = sorted(k for k in (info.get("subtitles") or {}) if k != "live_chat")
        auto = sorted(k for k in (info.get("automatic_captions") or {}) if k != "live_chat")
        key = archive_key(extractor, None)
        return Probe(
            url=url,
            handler=self.name,
            title=str(info.get("title") or video_id or url),
            size=sizes.get("best"),
            thumbnail=_thumbnail(info),
            choices=[
                Choice(id=f.id, label=f.label, kind=f.kind, size=f.size, ext=f.ext) for f in formats
            ],
            extra={
                "kind": "video",
                "extractor": extractor,
                "id": video_id,
                "webpage_url": webpage,
                "duration": info.get("duration"),
                "uploader": info.get("uploader") or info.get("channel"),
                "upload_date": info.get("upload_date"),
                "is_short": is_short,
                "formats": [f.model_dump() for f in formats],
                "presets": presets,
                "preset_sizes": sizes,
                "subtitles": subtitles,
                "auto_captions": auto,
                "chapters": len(info.get("chapters") or []),
                "archive": key,
                "saved": contains(
                    archive_path(self.settings.data_dir, key), archive_id(extractor, video_id)
                ),
            },
        )

    def _playlist_probe(
        self, url: str, info: dict[str, Any], tabs: list[str], extractor: str
    ) -> Probe:
        tab = info.get("_anyget_tab")
        kind = "channel" if tab or tabs else "playlist"
        key = archive_key(extractor, str(info.get("id") or "") or None)
        archive_file = archive_path(self.settings.data_dir, key)
        entries: list[dict[str, Any]] = []
        for index, entry in enumerate(info.get("entries") or [], start=1):
            if not entry:
                continue
            entry_url = str(entry.get("url") or entry.get("webpage_url") or "")
            entry_id = str(entry.get("id") or "")
            if not entry_url or not entry_id:
                continue
            entry_ie = str(entry.get("ie_key") or extractor)
            aid = archive_id(entry_ie, entry_id)
            entries.append(
                {
                    "index": index,
                    "id": entry_id,
                    "url": entry_url,
                    "title": entry.get("title") or entry_id,
                    "duration": entry.get("duration"),
                    "thumbnail": _thumbnail(entry),
                    "is_short": "/shorts/" in entry_url or tab == "shorts",
                    "live": entry.get("live_status") in _UNFINISHED_LIVE,
                    "archive_id": aid,
                    "saved": contains(archive_file, aid),
                }
            )
        return Probe(
            url=url,
            handler=self.name,
            title=str(info.get("title") or info.get("id") or url),
            size=None,
            thumbnail=_thumbnail(info),
            choices=[Choice(id=e["id"], label=str(e["title"]), kind="item") for e in entries],
            extra={
                "kind": kind,
                "extractor": extractor,
                "id": info.get("id"),
                "webpage_url": info.get("webpage_url") or url,
                "uploader": info.get("uploader") or info.get("channel"),
                "count": info.get("playlist_count") or len(entries),
                "entries": entries,
                "tabs": tabs,
                "tab": tab,
                "archive": key,
            },
        )

    # ----- download --------------------------------------------------------

    async def download(
        self, job: JobRef, options: dict[str, Any], progress_cb: ProgressCallback
    ) -> DownloadResult:
        fields = MediaOptions.model_fields
        opts = MediaOptions.model_validate({k: v for k, v in options.items() if k in fields})
        probe_data = options.get("probe") or {}
        estimate = (probe_data.get("extra") or {}).get("preset_sizes", {}).get(opts.preset)
        loop = asyncio.get_running_loop()
        cancel = threading.Event()

        def report(progress: Progress) -> None:
            loop.call_soon_threadsafe(progress_cb, progress)

        future = asyncio.wrap_future(
            self._executor.submit(self._download_sync, job, opts, report, cancel, estimate)
        )
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            cancel.set()  # the next progress hook stops yt-dlp; partial files stay for resume
            with contextlib.suppress(BaseException):
                await asyncio.wait_for(asyncio.shield(future), CANCEL_WAIT)
            raise

    def _download_sync(
        self,
        job: JobRef,
        opts: MediaOptions,
        report: Callable[[Progress], None],
        cancel: threading.Event,
        estimate: int | None,
    ) -> DownloadResult:
        from yt_dlp.utils import DownloadCancelled

        root = job.output_dir
        home = safe_join(root, opts.folder) if opts.folder else root.resolve()
        temp = work_dir(root, job.id)
        temp.mkdir(parents=True, exist_ok=True)
        home.mkdir(parents=True, exist_ok=True)

        info = self._recall(job.url)
        try:
            if info is None:
                info, _ = self._extract(job.url, ProbeOptions())
            if info.get("_type") in ("playlist", "multi_video"):
                raise HandlerError(
                    "unsupported",
                    "this link is a playlist or channel; pick the videos on the YouTube page",
                )
            if info.get("live_status") in _UNFINISHED_LIVE:
                raise HandlerError("live_not_finished", "the live stream has not finished yet")

            extractor = str(info.get("extractor_key") or "generic")
            key = opts.archive or archive_key(extractor, None)
            archive_file = archive_path(self.settings.data_dir, key)
            if contains(archive_file, archive_id(extractor, str(info.get("id")))):
                return DownloadResult(paths=[], note="already_downloaded")
            upload_date = info.get("upload_date")
            if upload_date and (
                (opts.date_after and upload_date < opts.date_after)
                or (opts.date_before and upload_date > opts.date_before)
            ):
                return DownloadResult(paths=[], note="outside_date_range")

            cookie_file = self._job_cookies(temp, job.url) if opts.use_cookies else None
            params = build_params(
                opts,
                home=home,
                temp=temp,
                cache_dir=self.cache_dir,
                archive_file=archive_file,
                cookie_file=cookie_file,
                deno=deno_path(),
                proxy=self._proxy(job.url),
            )
            if self.settings.rate_limit_kbps:
                params["ratelimit"] = self.settings.rate_limit_kbps * 1024
            tracker = _StreamProgress(report, cancel, estimate)
            params["progress_hooks"] = [tracker.on_progress]
            params["postprocessor_hooks"] = [tracker.on_postprocess]

            with self._ydl(params) as ydl:
                if cookie_file is not None:
                    # Formats may differ for a signed-in account: extract again with cookies.
                    result = ydl.extract_info(job.url, download=True)
                else:
                    result = ydl.process_ie_result(dict(info), download=True)
        except DownloadCancelled:
            raise
        except (HandlerError, BlockedURLError):
            raise
        except Exception as exc:
            if cancel.is_set():
                raise DownloadCancelled() from exc
            raise map_error(exc) from exc
        finally:
            with contextlib.suppress(FileNotFoundError):
                (temp / "cookies.txt").unlink()

        downloads = (result or {}).get("requested_downloads") or []
        main = next((Path(d["filepath"]) for d in downloads if d.get("filepath")), None)
        if main is None or not main.exists():
            return DownloadResult(paths=[], note="already_downloaded")
        main = ensure_inside(root, main)
        extras = sorted(
            ensure_inside(root, p)
            for p in main.parent.glob(f"{glob_escape(main.stem)}.*")
            if p != main and p.is_file() and p.suffix in (".srt", ".vtt", ".ass", ".json")
        )
        shutil.rmtree(temp, ignore_errors=True)
        return DownloadResult(paths=[main, *extras])

    def _job_cookies(self, temp: Path, url: str) -> Path | None:
        """This site's cookies for this job only (yt-dlp rewrites cookie files)."""
        target = temp / "cookies.txt"
        host = urlsplit(url).hostname or ""
        if self.connections is not None and self.connections.write_cookie_file(host, target):
            return target
        source = cookies_path(self.settings)  # v1 file, until the start-up migration
        if not source.is_file():
            return None
        target = temp / "cookies.txt"
        shutil.copyfile(source, target)
        target.chmod(0o600)
        return target


def glob_escape(text: str) -> str:
    return re.sub(r"([*?\[\]])", r"[\1]", text)


def cookies_path(settings: Settings) -> Path:
    return settings.data_dir / "cookies.txt"


class _StreamProgress:
    """Adds up progress over the separate video and audio downloads of one job."""

    def __init__(
        self, report: Callable[[Progress], None], cancel: threading.Event, estimate: int | None
    ) -> None:
        self.report = report
        self.cancel = cancel
        self.estimate = estimate
        self.streams: dict[str, tuple[int, int | None]] = {}
        self.note: str | None = None

    def _check_cancel(self) -> None:
        if self.cancel.is_set():
            from yt_dlp.utils import DownloadCancelled

            raise DownloadCancelled()

    def totals(self) -> tuple[int, int | None]:
        downloaded = sum(done for done, _ in self.streams.values())
        known = [total for _, total in self.streams.values() if total]
        total = sum(known) if known else None
        if self.estimate and (total is None or total < self.estimate):
            total = max(self.estimate, downloaded)
        return downloaded, total

    def on_progress(self, d: dict[str, Any]) -> None:
        self._check_cancel()
        name = str(d.get("filename") or d.get("tmpfilename") or "stream")
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        if d.get("status") == "downloading":
            self.streams[name] = (
                int(d.get("downloaded_bytes") or 0),
                int(total) if total else None,
            )
        elif d.get("status") == "finished":
            size = int(d.get("total_bytes") or d.get("downloaded_bytes") or 0)
            self.streams[name] = (size, size or None)
        downloaded, overall = self.totals()
        self.report(Progress(downloaded=downloaded, total=overall, message=self.note))

    def on_postprocess(self, d: dict[str, Any]) -> None:
        self._check_cancel()
        if d.get("status") != "started":
            return
        note = POSTPROCESSOR_NOTES.get(str(d.get("postprocessor")))
        if note:
            self.note = note
            downloaded, overall = self.totals()
            self.report(Progress(downloaded=downloaded, total=overall, message=note))
