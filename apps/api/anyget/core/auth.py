"""Who may use the API, how often, and the security headers on every answer.

Requests reach the API in two ways:
- From this computer (the website on 127.0.0.1, the CLI, Tailscale `serve`): ports are
  bound to 127.0.0.1, so these are the owner's own requests.
- Through Cloudflare Tunnel: cloudflared adds Cf-Connecting-Ip / Cf-Ray, and Cloudflare
  Access adds a signed Cf-Access-Jwt-Assertion for signed-in users.

Who is asking, checked in this order:
1. A valid bearer token (ANYGET_API_TOKEN) is the owner; a wrong one is refused.
2. A valid owner session cookie (POST /api/auth/login, core/session.py). Writes made
   with the cookie must send `X-Requested-With: anyget` (CSRF).
3. A valid Cloudflare Access JWT: RS256, signed by a key from
   https://<team>/cdn-cgi/access/certs, with our AUD and issuer, not expired.
4. Otherwise the request is local and allowed only when no sign-in is required: no
   owner configured, auth_mode "auto", not hosted (ANYGET_PUBLIC / Railway…), and no
   Cloudflare headers. A hosted AnyGet without an owner refuses everything (fail closed).
/api/health and /api/auth/* answer anyone. Remote and hosted clients are rate limited.
"""

import hmac
import json
import logging
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable, MutableMapping
from http.cookies import CookieError, SimpleCookie
from typing import Any

import httpx
import jwt
from jwt import PyJWK

from anyget.core.net import BlockedURLError, Net
from anyget.core.session import COOKIE, CSRF_HEADER, CSRF_VALUE
from anyget.core.settings import Settings
from anyget.core.users import OWNER_ID

log = logging.getLogger("anyget.auth")

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

CLOUDFLARE_HEADERS = (b"cf-connecting-ip", b"cf-ray", b"cf-access-jwt-assertion")
JWKS_TTL = 3600.0
JWKS_RETRY = 60.0
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Answered without a signed-in user (the auth endpoints report who is signed in).
PUBLIC_PATHS = {"/api/health", "/api/auth/login", "/api/auth/logout", "/api/auth/me"}

SECURITY_HEADERS = {
    b"x-content-type-options": b"nosniff",
    b"referrer-policy": b"no-referrer",
    b"x-frame-options": b"DENY",
    b"cross-origin-opener-policy": b"same-origin",
    b"permissions-policy": b"camera=(), microphone=(), geolocation=(), payment=()",
}
API_CSP = b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
# Swagger UI (/api/docs) loads its script and styles from jsDelivr.
DOCS_CSP = (
    b"default-src 'none'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    b"style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: "
    b"https://fastapi.tiangolo.com; connect-src 'self'; frame-ancestors 'none'"
)


class AuthError(Exception):
    def __init__(self, code: str, message: str, status: int = 401) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


class AccessVerifier:
    """Checks Cloudflare Access JWTs against the team's published keys (cached)."""

    def __init__(self, net: Net, settings: Settings) -> None:
        self.net = net
        self.settings = settings
        self._keys: dict[str, PyJWK] = {}
        self._fetched = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.settings.access_team_domain and self.settings.access_aud)

    @property
    def issuer(self) -> str:
        domain = self.settings.access_team_domain.strip().removeprefix("https://").rstrip("/")
        return f"https://{domain}"

    async def _load(self, force: bool = False) -> None:
        now = time.monotonic()
        fresh = now - self._fetched < (JWKS_RETRY if force else JWKS_TTL)
        if self._keys and fresh:
            return
        try:
            response = await self.net.request("GET", f"{self.issuer}/cdn-cgi/access/certs")
            response.raise_for_status()
            keys = response.json().get("keys") or []
        except (httpx.HTTPError, BlockedURLError, ValueError) as exc:
            log.warning("could not fetch Cloudflare Access keys: %s", exc)
            if not self._keys:
                raise AuthError("auth_unavailable", "cannot check sign-in right now", 503) from exc
            return
        self._keys = {k["kid"]: PyJWK(k) for k in keys if k.get("kid")}
        self._fetched = now

    async def verify(self, token: str) -> dict[str, Any]:
        try:
            kid = jwt.get_unverified_header(token).get("kid")
        except jwt.PyJWTError as exc:
            raise AuthError("auth_invalid", "the sign-in token is malformed") from exc
        await self._load()
        if kid not in self._keys:
            await self._load(force=True)  # keys rotate; look once more
        key = self._keys.get(str(kid))
        if key is None:
            raise AuthError("auth_invalid", "the sign-in token was not signed by your team")
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key=key.key,
                algorithms=["RS256"],
                audience=self.settings.access_aud,
                issuer=self.issuer,
                leeway=60,
                options={"require": ["exp", "iat", "aud", "iss"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("auth_expired", "your sign-in has expired; reload the page") from exc
        except jwt.PyJWTError as exc:
            raise AuthError("auth_invalid", f"the sign-in token is not valid: {exc}") from exc
        return claims


class RateLimiter:
    """Sliding one-minute window per client and kind (all requests / writes)."""

    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def hit(self, client: str, kind: str, limit: int, now: float | None = None) -> float | None:
        """None if allowed, else the seconds to wait."""
        now = time.monotonic() if now is None else now
        window = self._hits[(client, kind)]
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) >= limit:
            return max(1.0, 60 - (now - window[0]))
        window.append(now)
        if len(self._hits) > 50_000:  # forget idle clients
            for key in [k for k, v in self._hits.items() if not v or now - v[-1] > 60]:
                del self._hits[key]
        return None


def session_cookie(headers: dict[bytes, bytes]) -> str:
    raw = headers.get(b"cookie", b"").decode(errors="replace")
    if not raw:
        return ""
    jar = SimpleCookie()
    try:
        jar.load(raw)
    except CookieError:
        return ""
    morsel = jar.get(COOKIE)
    return morsel.value if morsel else ""


def _headers(scope: Scope) -> dict[bytes, bytes]:
    return {k.lower(): v for k, v in scope.get("headers") or []}


def client_ip(headers: dict[bytes, bytes], scope: Scope, settings: Settings | None = None) -> str:
    if b"cf-connecting-ip" in headers:
        return headers[b"cf-connecting-ip"].decode(errors="replace").strip()
    if settings is not None and settings.hosted and b"x-forwarded-for" in headers:
        # Behind the platform's proxy (and Vercel's rewrite) the first hop is the browser.
        first = headers[b"x-forwarded-for"].decode(errors="replace").split(",")[0].strip()
        if first:
            return first
    client = scope.get("client")
    return str(client[0]) if client else "unknown"


class SecurityMiddleware:
    """Access control, rate limits and security headers for the API."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.limiter = RateLimiter()

    @staticmethod
    def _services(scope: Scope) -> Any:
        app = scope.get("app")
        return getattr(getattr(app, "state", None), "services", None)

    async def _identify(
        self, scope: Scope, services: Any, headers: dict[bytes, bytes]
    ) -> tuple[str | None, str]:
        """Who is asking: (user id or None, how). Raises AuthError for bad credentials."""
        settings: Settings = services.settings
        token = settings.api_token
        auth = headers.get(b"authorization", b"").decode(errors="replace")
        if auth.lower().startswith("bearer "):
            if token and hmac.compare_digest(auth[7:].strip().encode(), token.encode()):
                return OWNER_ID, "token"
            raise AuthError("auth_invalid", "the access token is wrong")
        cookie = session_cookie(headers)
        if cookie:
            user = services.sessions.verify(cookie)
            if user is not None:
                return user, "session"
        assertion = headers.get(b"cf-access-jwt-assertion", b"").decode(errors="replace")
        verifier: AccessVerifier = services.access
        if assertion and verifier.configured:
            await verifier.verify(assertion)
            return OWNER_ID, "access"
        remote = any(h in headers for h in CLOUDFLARE_HEADERS)
        if not remote and not settings.login_required:
            return OWNER_ID, "local"
        return None, ""

    @staticmethod
    def _refusal(
        settings: Settings, verifier: AccessVerifier, headers: dict[bytes, bytes]
    ) -> AuthError:
        if settings.hosted and not settings.owner_configured and not settings.api_token:
            return AuthError(
                "owner_required",
                "AnyGet is on the internet without an owner: set ANYGET_OWNER_EMAIL and "
                "ANYGET_OWNER_PASSWORD_HASH (anyget hash-password), then restart",
            )
        remote = any(h in headers for h in CLOUDFLARE_HEADERS)
        if remote and not settings.owner_configured and not verifier.configured:
            return AuthError(
                "auth_required",
                "set up Cloudflare Access (ANYGET_ACCESS_TEAM_DOMAIN, ANYGET_ACCESS_AUD), "
                "an owner sign-in or an access token",
            )
        if settings.owner_configured:
            return AuthError("auth_required", "sign in first")
        return AuthError("auth_required", "sign in through Cloudflare Access first")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = _headers(scope)
        path = str(scope.get("path", ""))
        remote = any(h in headers for h in CLOUDFLARE_HEADERS)
        try:
            services = self._services(scope)
            if services is None:  # not started yet: never answer unchecked
                raise AuthError("starting", "AnyGet is starting", 503)
            settings: Settings = services.settings
            if remote or settings.login_required:
                client = client_ip(headers, scope, settings)
                wait = self.limiter.hit(client, "all", settings.rate_limit_per_minute)
                if wait is None and scope.get("method") in WRITE_METHODS:
                    wait = self.limiter.hit(client, "write", settings.rate_limit_writes_per_minute)
                if wait is not None:
                    raise AuthError("rate_limited", "too many requests; slow down", 429)
            public = path in PUBLIC_PATHS
            try:
                user, how = await self._identify(scope, services, headers)
            except AuthError:
                if not public:
                    raise
                user, how = None, ""
            if user is None and not public:
                raise self._refusal(settings, services.access, headers)
            if how == "session" and scope.get("method") in WRITE_METHODS:
                sent = headers.get(CSRF_HEADER.encode(), b"").decode(errors="replace")
                if sent.lower() != CSRF_VALUE:
                    raise AuthError("csrf", "this request must come from the AnyGet website", 403)
            state = scope.setdefault("state", {})
            state["user"] = user
            state["auth"] = how
        except AuthError as exc:
            extra = []
            if exc.status == 429:
                extra = [(b"retry-after", b"60")]
            elif exc.status == 401:
                extra = [(b"www-authenticate", b'Bearer realm="anyget"')]
            await self._deny(send, exc, extra)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                existing = {k.lower() for k, _ in message.get("headers", [])}
                added = [(k, v) for k, v in SECURITY_HEADERS.items() if k not in existing]
                if b"content-security-policy" not in existing:
                    csp = DOCS_CSP if path.startswith("/api/docs") else API_CSP
                    added.append((b"content-security-policy", csp))
                message["headers"] = [*message.get("headers", []), *added]
            await send(message)

        await self.app(scope, receive, send_with_headers)

    async def _deny(self, send: Send, exc: AuthError, extra: list[tuple[bytes, bytes]]) -> None:
        body = json.dumps({"code": exc.code, "message": exc.message}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": exc.status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    *SECURITY_HEADERS.items(),
                    (b"content-security-policy", API_CSP),
                    *extra,
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
