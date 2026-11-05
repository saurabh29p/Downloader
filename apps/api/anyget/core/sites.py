"""Which site to connect when a download failed for want of the user's own account."""

from urllib.parse import urlsplit

from anyget.connections.sites import Site, cookie_site_for_host

# Errors that signing in on the user's own account usually fixes.
CONNECT_CODES = frozenset({"login_required", "bot_check", "age_restricted", "forbidden"})


def connect_site(error_code: str | None, url: str) -> Site | None:
    """The site to connect when that would fix this error, else None."""
    if error_code not in CONNECT_CODES:
        return None
    return cookie_site_for_host(urlsplit(url).hostname or "")
