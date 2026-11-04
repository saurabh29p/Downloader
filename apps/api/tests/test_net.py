import asyncio
import ipaddress
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
import respx

from anyget.core.net import (
    BlockedURLError,
    GuardedBackend,
    HostLimiter,
    Net,
    check_url,
    is_public_ip,
)
from anyget.core.settings import Settings
from tests.conftest import PUBLIC_IP, FakeDNS


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.1.2.3",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",  # cloud metadata
        "100.64.0.1",  # CGNAT
        "0.0.0.0",
        "224.0.0.1",  # multicast
        "255.255.255.255",
        "::1",
        "fe80::1",
        "fc00::1",
        "fd00:ec2::254",  # AWS metadata over IPv6
        "::ffff:127.0.0.1",  # IPv4-mapped
        "::ffff:169.254.169.254",
        "2002:7f00:0001::",  # 6to4 wrapping 127.0.0.1
        "2001:0000:4136:e378:8000:63bf:3fff:fdd2",  # Teredo
        "ff02::1",
    ],
)
def test_private_ips_are_blocked(ip: str) -> None:
    assert not is_public_ip(ipaddress.ip_address(ip))


@pytest.mark.parametrize("ip", ["93.184.215.14", "1.1.1.1", "2606:4700:4700::1111"])
def test_public_ips_are_allowed(ip: str) -> None:
    assert is_public_ip(ipaddress.ip_address(ip))


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/x",
        "gopher://example.com/",
        "javascript:alert(1)",
        "http://user:pass@example.com/",
        "http:///nohost",
        "http://127.0.0.1/",
        "http://[::1]:8000/",
        "http://169.254.169.254/latest/meta-data/",
        "http://2130706433/",  # 127.0.0.1 as an integer
        "http://0x7f.1/",  # 127.0.0.1 in hex shorthand
        "http://017700000001/",  # 127.0.0.1 in octal
    ],
)
async def test_check_url_blocks(url: str) -> None:
    with pytest.raises(BlockedURLError):
        await check_url(url)


async def test_hostname_resolving_to_private_is_blocked(fake_dns: FakeDNS) -> None:
    fake_dns.set("internal.test", "10.0.0.5")
    with pytest.raises(BlockedURLError):
        await check_url("https://internal.test/file")


async def test_any_private_answer_blocks(fake_dns: FakeDNS) -> None:
    fake_dns.set("mixed.test", PUBLIC_IP, "127.0.0.1")
    with pytest.raises(BlockedURLError):
        await check_url("https://mixed.test/")


async def test_unresolvable_is_blocked(fake_dns: FakeDNS) -> None:
    fake_dns.set("nothing.test")
    with pytest.raises(BlockedURLError):
        await check_url("https://nothing.test/")


async def test_public_host_passes() -> None:
    parsed = await check_url("https://files.example.com/a.zip")
    assert parsed.host == "files.example.com"


async def test_allowlist(fake_dns: FakeDNS) -> None:
    fake_dns.set("localhost", "127.0.0.1")
    await check_url("http://localhost:8200/x", allowlist=["localhost:8200"])
    with pytest.raises(BlockedURLError):
        await check_url("http://localhost:8201/x", allowlist=["localhost:8200"])


@respx.mock
async def test_redirect_to_private_is_blocked(settings: Settings, fake_dns: FakeDNS) -> None:
    fake_dns.set("evil.test", PUBLIC_IP)
    respx.get("https://evil.test/start").mock(
        return_value=httpx.Response(302, headers={"Location": "http://169.254.169.254/latest"})
    )
    metadata = respx.get("http://169.254.169.254/latest").mock(return_value=httpx.Response(200))
    net = Net(settings)
    with pytest.raises(BlockedURLError):
        await net.request("GET", "https://evil.test/start")
    assert not metadata.called
    await net.aclose()


@respx.mock
async def test_redirect_chain_is_followed(settings: Settings) -> None:
    respx.get("https://a.test/1").mock(return_value=httpx.Response(301, headers={"Location": "/2"}))
    respx.get("https://a.test/2").mock(
        return_value=httpx.Response(302, headers={"Location": "https://b.test/file"})
    )
    respx.get("https://b.test/file").mock(return_value=httpx.Response(200, text="ok"))
    net = Net(settings)
    response = await net.request("GET", "https://a.test/1")
    assert response.text == "ok"
    assert str(response.url) == "https://b.test/file"
    await net.aclose()


@respx.mock
async def test_too_many_redirects(settings: Settings) -> None:
    respx.get("https://loop.test/").mock(
        return_value=httpx.Response(302, headers={"Location": "https://loop.test/"})
    )
    net = Net(settings)
    with pytest.raises(httpx.TooManyRedirects):
        await net.request("GET", "https://loop.test/")
    await net.aclose()


@respx.mock
async def test_backoff_on_429(settings: Settings, no_backoff_sleep: list[float]) -> None:
    route = respx.get("https://busy.test/").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(503),
            httpx.Response(200, text="finally"),
        ]
    )
    net = Net(settings)
    response = await net.request("GET", "https://busy.test/")
    assert response.text == "finally"
    assert route.call_count == 3
    assert no_backoff_sleep == [7.0, 4.0]
    await net.aclose()


@respx.mock
async def test_user_agent(settings: Settings) -> None:
    settings.contact_email = "me@example.org"
    route = respx.get("https://ua.test/").mock(return_value=httpx.Response(200))
    net = Net(settings)
    await net.request("GET", "https://ua.test/")
    agent = route.calls[0].request.headers["user-agent"]
    assert agent.startswith("AnyGet/") and "me@example.org" in agent
    await net.aclose()


# ---- connect-time guard (real sockets, no respx) ------------------------------


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
def local_server() -> Iterator[int]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Hello)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()


async def test_backend_refuses_private_ip(fake_dns: FakeDNS) -> None:
    fake_dns.set("sneaky.test", "127.0.0.1")
    with pytest.raises(BlockedURLError):
        await GuardedBackend().connect_tcp("sneaky.test", 80)


async def test_dns_rebinding_is_caught_at_connect_time(
    settings: Settings, fake_dns: FakeDNS, local_server: int
) -> None:
    answers = iter([[PUBLIC_IP], ["127.0.0.1"]])  # pre-flight sees public, connect sees local
    fake_dns.records["rebind.test"] = lambda: next(answers)
    net = Net(settings)
    with pytest.raises(BlockedURLError):
        await net.request("GET", f"http://rebind.test:{local_server}/")
    await net.aclose()


async def test_allowlisted_local_server_works(fake_dns: FakeDNS, local_server: int) -> None:
    fake_dns.set("fixture.test", "127.0.0.1")
    settings = Settings(net_allowlist=f"fixture.test:{local_server}", _env_file=None)
    net = Net(settings)
    response = await net.request("GET", f"http://fixture.test:{local_server}/")
    assert response.text == "hello"
    await net.aclose()
    blocked = Net(Settings(_env_file=None))
    with pytest.raises(BlockedURLError):
        await blocked.request("GET", f"http://fixture.test:{local_server}/")
    await blocked.aclose()


async def test_host_limiter() -> None:
    limiter = HostLimiter(4, {"archive.org": 2})
    assert limiter.limit_for("ia800.us.archive.org") == 2
    assert limiter.limit_for("example.com") == 4
    assert limiter.semaphore("archive.org") is limiter.semaphore("www.archive.org")
    sem = limiter.semaphore("archive.org")
    await sem.acquire()
    await sem.acquire()
    assert sem.locked()
    sem.release()
    sem.release()
    await asyncio.sleep(0)
