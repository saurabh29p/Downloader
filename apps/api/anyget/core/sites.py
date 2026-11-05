"""Sites where the user's own account can fix a failed download (v2 Connections)."""

from urllib.parse import urlsplit

# Errors that signing in on the user's own account usually fixes.
CONNECT_CODES = frozenset({"login_required", "bot_check", "age_restricted", "forbidden"})

# Host (or parent domain) → site name shown in "Connect your <site> account".
SITES: dict[str, str] = {
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "x.com": "X",
    "twitter.com": "X",
    "reddit.com": "Reddit",
    "vimeo.com": "Vimeo",
    "instagram.com": "Instagram",
    "facebook.com": "Facebook",
    "fb.watch": "Facebook",
    "patreon.com": "Patreon",
}


def site_of(url: str) -> str | None:
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    for domain, name in SITES.items():
        if host == domain or host.endswith(f".{domain}"):
            return name
    return host or None


def connect_site(error_code: str | None, url: str) -> str | None:
    """The site to connect when that would fix this error, else None."""
    return site_of(url) if error_code in CONNECT_CODES else None
