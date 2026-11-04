"""The yt-dlp/urllib3 connection guard, tested with real yt-dlp and a real local server."""

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from anyget.core import net_guard
from anyget.core.net import BlockedURLError
from tests.conftest import FakeDNS


class _Hello(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = b"hello"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def local_port() -> Iterator[int]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Hello)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()


@pytest.fixture(autouse=True)
def guard() -> Iterator[None]:
    net_guard.install([])
    yield
    net_guard.install([])


def ydl_get(url: str, handler: str | None = None) -> bytes:
    from yt_dlp import YoutubeDL
    from yt_dlp.networking import Request

    with YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        if handler:
            director = ydl._request_director
            for key in list(director.handlers):
                if key != handler:
                    director.handlers.pop(key)
        with ydl.urlopen(Request(url)) as response:
            data: bytes = response.read()
            return data


def is_blocked(exc: BaseException) -> bool:
    text = f"{exc} {exc.__cause__} {getattr(exc, 'cause', '')}"
    return isinstance(exc, BlockedURLError) or "private or reserved address" in text


@pytest.mark.parametrize("handler", ["Requests", "Urllib"])
def test_ytdlp_cannot_reach_loopback(local_port: int, handler: str) -> None:
    with pytest.raises(Exception) as info:
        ydl_get(f"http://127.0.0.1:{local_port}/", handler)
    assert is_blocked(info.value), info.value


@pytest.mark.parametrize("handler", ["Requests", "Urllib"])
def test_hostname_resolving_to_loopback_is_blocked(
    local_port: int, handler: str, fake_dns: FakeDNS
) -> None:
    fake_dns.set("rebind.test", "127.0.0.1")
    with pytest.raises(Exception) as info:
        ydl_get(f"http://rebind.test:{local_port}/", handler)
    assert is_blocked(info.value), info.value


@pytest.mark.parametrize("handler", ["Requests", "Urllib"])
def test_allowlisted_local_server_works(local_port: int, handler: str) -> None:
    net_guard.install([f"127.0.0.1:{local_port}"])
    assert ydl_get(f"http://127.0.0.1:{local_port}/", handler) == b"hello"


def test_metadata_address_is_blocked() -> None:
    with pytest.raises(Exception) as info:
        ydl_get("http://169.254.169.254/latest/meta-data/")
    assert is_blocked(info.value)


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1/x.m3u8", "file:///etc/passwd", "rtmp://10.0.0.1/live", "http://[::1]/a"],
)
def test_ffmpeg_inputs_are_checked(url: str) -> None:
    with pytest.raises(BlockedURLError):
        net_guard.check_remote_input(url)


def test_ffmpeg_public_input_allowed() -> None:
    net_guard.check_remote_input("https://media.example.com/stream.m3u8")


def test_guard_installed_everywhere() -> None:
    import urllib3.util.connection as uc
    import yt_dlp.networking._helper as helper
    import yt_dlp.networking._requests as req
    import yt_dlp.networking._urllib as ul

    for module in (helper, req, ul, uc):
        assert getattr(module.create_connection, "_anyget_guard", False), module
