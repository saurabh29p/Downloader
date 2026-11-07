"""Outgoing HTTP with an SSRF guard.

Two layers protect every request:

1. Pre-flight: before the first request and before every redirect hop, the URL
   must be http/https, carry no credentials, and every IP its host resolves to
   must be public.
2. Connect time: the connection pool uses a network backend that resolves the
   host again, checks the IPs, and connects to the vetted IP. This closes the
   DNS-rebinding gap between the check and the connection. TLS still uses the
   original hostname.

Redirects are followed manually so each hop goes through layer 1.
"""

import asyncio
import ipaddress
import re
import socket
from collections import defaultdict
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from typing import Any

import httpcore
import httpx
from httpcore._backends.auto import AutoBackend

from anyget.core.settings import Settings

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

MAX_REDIRECTS = 10
RETRY_STATUSES = {429, 503}
MAX_RETRY_AFTER = 30.0


class BlockedURLError(ValueError):
    """The URL points somewhere AnyGet must not fetch (private network, bad scheme…)."""


def is_public_ip(ip: IPAddress) -> bool:
    """True only for globally routable unicast addresses."""
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return is_public_ip(ip.ipv4_mapped)
        if ip.sixtofour is not None:
            return is_public_ip(ip.sixtofour)
        if ip.teredo is not None:
            return False
    return ip.is_global and not ip.is_multicast


async def resolve_host(host: str, port: int) -> list[str]:
    """Resolve a hostname to IP strings. Tests replace this function."""
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


_LEGACY_IPV4 = re.compile(r"^(0x[0-9a-f]+|[0-9]+)(\.(0x[0-9a-f]+|[0-9]+)){0,3}$", re.IGNORECASE)


def _ip_literal(host: str) -> IPAddress | None:
    """Parse IP literals, including legacy IPv4 forms like 2130706433 or 0x7f.1."""
    try:
        return ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        pass
    if _LEGACY_IPV4.match(host):
        try:
            return ipaddress.IPv4Address(socket.inet_aton(host))
        except OSError:
            return None
    return None


def resolve_host_sync(host: str, port: int) -> list[str]:
    """Blocking resolver for code running in worker threads (yt-dlp). Tests replace it."""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


def _vet(host: str, port: int, ips: list[str], allowlist: Iterable[str]) -> list[str]:
    if not ips:
        raise BlockedURLError(f"could not resolve host {host!r}")
    if f"{host}:{port}" not in set(allowlist):
        for raw in ips:
            if not is_public_ip(ipaddress.ip_address(raw)):
                raise BlockedURLError(f"{host} resolves to a private or reserved address")
    # IPv4 first: many hosts (CI runners, home routers) have no working IPv6 route,
    # and a dead IPv6 attempt can use up the whole connect timeout.
    return sorted(ips, key=lambda raw: ipaddress.ip_address(raw).version)


async def vetted_ips(host: str, port: int, allowlist: Iterable[str] = ()) -> list[str]:
    """Return the host's IPs if they are all public (or host:port is allowlisted)."""
    literal = _ip_literal(host)
    if literal is not None:
        return _vet(host, port, [str(literal)], allowlist)
    try:
        ips = await resolve_host(host, port)
    except OSError as exc:
        raise BlockedURLError(f"could not resolve host {host!r}") from exc
    return _vet(host, port, ips, allowlist)


def vetted_ips_sync(host: str, port: int, allowlist: Iterable[str] = ()) -> list[str]:
    """Blocking version of vetted_ips for worker threads."""
    literal = _ip_literal(host)
    if literal is not None:
        return _vet(host, port, [str(literal)], allowlist)
    try:
        ips = resolve_host_sync(host, port)
    except OSError as exc:
        raise BlockedURLError(f"could not resolve host {host!r}") from exc
    return _vet(host, port, ips, allowlist)


async def check_url(url: str | httpx.URL, allowlist: Iterable[str] = ()) -> httpx.URL:
    """Validate a URL for fetching; returns the parsed URL or raises BlockedURLError."""
    try:
        parsed = httpx.URL(str(url))
    except httpx.InvalidURL as exc:
        raise BlockedURLError("not a valid URL") from exc
    if parsed.scheme not in ("http", "https"):
        raise BlockedURLError("only http and https links are supported")
    if not parsed.host:
        raise BlockedURLError("the link has no host")
    if parsed.userinfo:
        raise BlockedURLError("links with embedded usernames or passwords are not allowed")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    await vetted_ips(parsed.host, port, allowlist)
    return parsed


class GuardedBackend(httpcore.AsyncNetworkBackend):
    """Network backend that only connects to vetted public IPs."""

    def __init__(self, allowlist: Iterable[str] = ()) -> None:
        self._inner = AutoBackend()
        self._allowlist = tuple(allowlist)

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,  # noqa: ASYNC109 (httpcore interface)
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        ips = await vetted_ips(host, port, self._allowlist)
        last_error: Exception | None = None
        for ip in ips:
            try:
                return await self._inner.connect_tcp(
                    ip, port, timeout, local_address, socket_options
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last_error = exc
        raise last_error or BlockedURLError(f"could not connect to {host}")

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,  # noqa: ASYNC109 (httpcore interface)
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        raise BlockedURLError("unix sockets are not allowed")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


class GuardedTransport(httpx.AsyncHTTPTransport):
    """httpx transport whose connection pool uses GuardedBackend."""

    def __init__(self, allowlist: Iterable[str] = (), **kwargs: Any) -> None:
        super().__init__(**kwargs)
        pool = self._pool
        if not hasattr(pool, "_network_backend"):  # pragma: no cover - httpcore changed
            raise RuntimeError("unsupported httpcore version for the SSRF guard")
        pool._network_backend = GuardedBackend(allowlist)


class HostLimiter:
    """Per-host concurrency limits (e.g. archive.org: 2)."""

    def __init__(self, default: int, overrides: dict[str, int] | None = None) -> None:
        self._default = default
        self._overrides = overrides or {}
        self._semaphores: dict[str, asyncio.Semaphore] = defaultdict(self._new_default)

    def _new_default(self) -> asyncio.Semaphore:
        return asyncio.Semaphore(self._default)

    def _key(self, host: str) -> str:
        host = host.lower()
        for domain in self._overrides:
            if host == domain or host.endswith("." + domain):
                return domain
        return host

    def limit_for(self, host: str) -> int:
        return self._overrides.get(self._key(host), self._default)

    def semaphore(self, host: str) -> asyncio.Semaphore:
        key = self._key(host)
        if key not in self._semaphores:
            self._semaphores[key] = asyncio.Semaphore(self.limit_for(host))
        return self._semaphores[key]


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    header = response.headers.get("retry-after", "")
    if header.isdigit():
        return min(float(header), MAX_RETRY_AFTER)
    return min(2.0**attempt, MAX_RETRY_AFTER)


async def _sleep(seconds: float) -> None:
    """Indirection so tests can skip backoff waits."""
    await asyncio.sleep(seconds)


class Net:
    """The one way AnyGet talks to the internet."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.allowlist = tuple(settings.net_allowlist)
        self.client = client or self._build_client(settings)

    def _build_client(self, settings: Settings) -> httpx.AsyncClient:
        transport: httpx.AsyncBaseTransport
        if settings.proxy:
            transport = httpx.AsyncHTTPTransport(proxy=settings.proxy, retries=1)
        else:
            transport = GuardedTransport(self.allowlist, retries=1)
        return httpx.AsyncClient(
            transport=transport,
            headers={"User-Agent": settings.user_agent},
            timeout=httpx.Timeout(settings.request_timeout, connect=15.0),
            follow_redirects=False,
            trust_env=False,
        )

    async def check(self, url: str | httpx.URL) -> httpx.URL:
        return await check_url(url, self.allowlist)

    async def _send(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None,
        stream: bool,
        retries: int = 3,
        content: bytes | None = None,
    ) -> httpx.Response:
        current = url
        hops = 0
        attempt = 0
        while True:
            await self.check(current)
            request = self.client.build_request(method, current, headers=headers, content=content)
            response = await self.client.send(request, stream=stream)
            if response.is_redirect and "location" in response.headers:
                await response.aclose()
                hops += 1
                if hops > MAX_REDIRECTS:
                    raise httpx.TooManyRedirects("too many redirects", request=request)
                current = str(response.url.join(response.headers["location"]))
                if response.status_code not in (307, 308):
                    content = None  # only 307/308 resend the body
                    if method not in ("GET", "HEAD"):
                        method = "GET"
                continue
            if response.status_code in RETRY_STATUSES and attempt < retries:
                attempt += 1
                delay = _retry_delay(response, attempt)
                await response.aclose()
                await _sleep(delay)
                continue
            return response

    async def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        retries: int = 3,
    ) -> httpx.Response:
        """Send a request (following redirects safely) and read the whole body.
        `retries` is how often a 429/503 answer is retried after a back-off."""
        response = await self._send(
            method, url, headers, stream=False, retries=retries, content=content
        )
        return response

    @asynccontextmanager
    async def stream(
        self, method: str, url: str, headers: dict[str, str] | None = None
    ) -> AsyncIterator[httpx.Response]:
        """Like request(), but the body is streamed. Always closes the response."""
        response = await self._send(method, url, headers, stream=True)
        try:
            yield response
        finally:
            await response.aclose()

    async def aclose(self) -> None:
        await self.client.aclose()
