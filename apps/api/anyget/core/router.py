"""Normalize links and pick the handler for each one (routing order in CLAUDE.md)."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from anyget.core.net import BlockedURLError, Net
from anyget.handlers.base import Handler, HandlerError
from anyget.handlers.registry import Registry

TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "dclid",
    "gbraid",
    "wbraid",
    "msclkid",
    "yclid",
    "igshid",
    "mkt_tok",
    "_hsenc",
    "_hsmi",
    "ref_src",
    "spm",
}
TRACKING_PREFIXES = ("utm_", "mc_", "pk_")
# "si" is a share-tracking id on these hosts; elsewhere it may be meaningful.
SI_HOSTS = ("youtube.com", "youtu.be", "open.spotify.com", "music.youtube.com")

SHORTENERS = {
    "bit.ly",
    "t.co",
    "tinyurl.com",
    "is.gd",
    "ow.ly",
    "buff.ly",
    "lnkd.in",
    "rebrand.ly",
    "cutt.ly",
    "shorturl.at",
}


def _host_matches(host: str, domains: tuple[str, ...] | set[str]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def normalize(url: str) -> str:
    """Trim, add a scheme if missing, lowercase scheme/host, strip tracking params."""
    text = url.strip().strip("<>\"'").strip()
    if not text:
        raise BlockedURLError("empty link")
    if text.lower().startswith("magnet:"):
        return text
    if "://" not in text:
        text = "https://" + text
    parts = urlsplit(text)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    netloc = parts.netloc
    if parts.hostname:
        netloc = netloc.replace(parts.hostname, host, 1) if parts.hostname != host else netloc
        if "@" not in netloc:
            netloc = netloc.lower()
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
        and not key.lower().startswith(TRACKING_PREFIXES)
        and not (key == "si" and _host_matches(host, SI_HOSTS))
    ]
    path = parts.path or ("/" if scheme in ("http", "https") else "")
    return urlunsplit((scheme, netloc, path, urlencode(query, doseq=True), parts.fragment))


class Router:
    def __init__(self, registry: Registry, net: Net) -> None:
        self.registry = registry
        self.net = net

    async def expand(self, url: str) -> str:
        """Follow short links (bit.ly…) through the SSRF guard; keep the URL on failure."""
        host = (urlsplit(url).hostname or "").lower()
        if not _host_matches(host, SHORTENERS):
            return url
        try:
            response = await self.net.request("HEAD", url)
        except httpx.HTTPError:
            return url
        return normalize(str(response.url))

    def _torrent(self) -> Handler:
        handler = self.registry.get("torrent")
        if handler is None:
            raise HandlerError("unsupported", "torrent links are not supported")
        return handler

    async def resolve(self, url: str) -> tuple[str, Handler]:
        """Return the normalized (and expanded) URL and the handler for it."""
        internal = url.strip()
        if internal.startswith("anyget:"):  # local work such as conversions; no network
            handler = self.registry.find(internal)
            if handler is None:
                raise HandlerError("unsupported", "unknown AnyGet task link")
            return internal, handler
        normalized = normalize(url)
        if normalized.startswith("magnet:"):
            return normalized, self._torrent()
        await self.net.check(normalized)
        normalized = await self.expand(normalized)
        if urlsplit(normalized).path.lower().endswith(".torrent"):
            return normalized, self._torrent()
        handler = self.registry.find(normalized)
        if handler is None:
            raise HandlerError("unsupported", "no handler can download this link")
        return normalized, handler
