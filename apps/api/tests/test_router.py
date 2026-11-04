import httpx
import pytest
import respx

from anyget.core.net import BlockedURLError, Net
from anyget.core.router import Router, normalize
from anyget.core.services import build_registry
from anyget.core.settings import Settings
from anyget.handlers.base import HandlerError


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  https://Example.COM/a.pdf  ", "https://example.com/a.pdf"),
        ("example.com/file.zip", "https://example.com/file.zip"),
        ("<https://example.com/x>", "https://example.com/x"),
        (
            "https://example.com/a?utm_source=x&id=5&fbclid=abc&gclid=1&mc_eid=2",
            "https://example.com/a?id=5",
        ),
        ("https://youtu.be/abc?si=track&t=10", "https://youtu.be/abc?t=10"),
        ("https://other.example/a?si=keep", "https://other.example/a?si=keep"),
        ("https://mega.nz/file/x#key", "https://mega.nz/file/x#key"),
        ("https://example.com", "https://example.com/"),
        ("magnet:?xt=urn:btih:abc", "magnet:?xt=urn:btih:abc"),
    ],
)
def test_normalize(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


def test_normalize_empty() -> None:
    with pytest.raises(BlockedURLError):
        normalize("   ")


@pytest.fixture
async def router(settings: Settings) -> Router:
    net = Net(settings)
    return Router(build_registry(net), net)


@respx.mock
async def test_short_link_is_expanded(router: Router) -> None:
    respx.head("https://bit.ly/abc").mock(
        return_value=httpx.Response(301, headers={"Location": "https://files.test/a.zip?utm_x=1"})
    )
    respx.head("https://files.test/a.zip?utm_x=1").mock(return_value=httpx.Response(200))
    url, handler = await router.resolve("bit.ly/abc")
    assert url == "https://files.test/a.zip"
    assert handler.name == "http"


async def test_routes_to_http_fallback(router: Router) -> None:
    _url, handler = await router.resolve("https://files.test/a.zip")
    assert handler.name == "http"


@pytest.mark.parametrize("url", ["magnet:?xt=urn:btih:abc", "https://files.test/x.torrent"])
async def test_torrents_not_supported_yet(router: Router, url: str) -> None:
    with pytest.raises(HandlerError) as info:
        await router.resolve(url)
    assert info.value.code == "unsupported"


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://127.0.0.1/", "ftp://x.test/a"])
async def test_blocked_before_routing(router: Router, url: str) -> None:
    with pytest.raises(BlockedURLError):
        await router.resolve(url)
