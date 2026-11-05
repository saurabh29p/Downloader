"""SSRF guard for third-party HTTP stacks that do not go through core.net.Net.

yt-dlp opens its own connections (urllib, requests/urllib3, websockets). We
replace the functions they use to open sockets with a wrapper that resolves the
host once, refuses private/reserved IPs (same rules and allowlist as
core.net), and connects to the vetted IP literal, so there is no second DNS
lookup to race. This covers every request and every redirect at connect time.

The patch is process-wide and idempotent. tests/test_net_guard.py runs real
yt-dlp against a local server to prove it holds for the pinned versions.
"""

import importlib
import inspect
from collections.abc import Callable, Iterable
from typing import Any
from urllib.parse import urlsplit

from anyget.core import net

_allowlist: tuple[str, ...] = ()


class BlockedConnectionError(ConnectionRefusedError):
    """Raised instead of connecting. An OSError, so HTTP stacks report it as a normal
    connection failure; the message keeps "private or reserved address" for mapping."""


_installed = False

YTDLP_MODULES = (
    "yt_dlp.networking._helper",
    "yt_dlp.networking._urllib",
    "yt_dlp.networking._requests",
    "yt_dlp.networking._websockets",
)


def _guard(original: Callable[..., Any]) -> Callable[..., Any]:
    def create_connection(address: tuple[Any, ...], *args: Any, **kwargs: Any) -> Any:
        host, port = str(address[0]), int(address[1])
        try:
            ips = net.vetted_ips_sync(host, port, _allowlist)
        except net.BlockedURLError as exc:
            raise BlockedConnectionError(str(exc)) from exc
        last_error: OSError | None = None
        for ip in ips:
            try:
                return original((ip, port), *args, **kwargs)
            except OSError as exc:
                last_error = exc
        raise last_error or OSError(f"could not connect to {host}")

    create_connection.__wrapped__ = original  # type: ignore[attr-defined]
    create_connection._anyget_guard = True  # type: ignore[attr-defined]
    return create_connection


def _replace_everywhere(module: Any, original: Any, replacement: Any) -> None:
    if getattr(module, "create_connection", None) is original:
        module.create_connection = replacement
    for _name, cls in inspect.getmembers(module, inspect.isclass):
        for attr, value in list(vars(cls).items()):
            if value is original:
                setattr(cls, attr, replacement)


def install(allowlist: Iterable[str] = ()) -> None:
    """Install (or update the allowlist of) the guard. Safe to call many times."""
    global _allowlist, _installed
    _allowlist = tuple(allowlist)
    if _installed:
        return

    helper = importlib.import_module("yt_dlp.networking._helper")
    original = helper.create_connection
    guarded = _guard(original)
    for name in YTDLP_MODULES:
        try:
            module = importlib.import_module(name)
        except ImportError:  # optional handler dependency not installed
            continue
        _replace_everywhere(module, original, guarded)

    import urllib3.util.connection as urllib3_connection

    urllib3_connection.create_connection = _guard(urllib3_connection.create_connection)
    _guard_ffmpeg_downloads()
    _installed = True


def check_remote_input(url: str) -> None:
    """Refuse a URL whose host is private/reserved (used before ffmpeg may fetch it)."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise net.BlockedURLError(f"refusing to let ffmpeg open a {parts.scheme or 'local'} input")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    net.vetted_ips_sync(parts.hostname or "", port, _allowlist)


def _guard_ffmpeg_downloads() -> None:
    """yt-dlp hands some streams to ffmpeg, which opens its own connections.

    We force native downloads, but as a second layer every remote input ffmpeg
    would fetch is checked first (pre-flight; ffmpeg does its own DNS).
    """
    from yt_dlp.downloader.external import FFmpegFD

    original = FFmpegFD._call_downloader

    def guarded_call(self: Any, tmpfilename: str, info_dict: dict[str, Any]) -> Any:
        formats = info_dict.get("requested_formats") or [info_dict]
        for fmt in formats:
            check_remote_input(str(fmt.get("url", "")))
        return original(self, tmpfilename, info_dict)

    FFmpegFD._call_downloader = guarded_call


def is_installed() -> bool:
    return _installed
