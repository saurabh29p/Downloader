"""Map yt-dlp errors to clear, stable reasons. We report these; we never work around them."""

import re

from anyget.core.net import BlockedURLError
from anyget.handlers.base import HandlerError

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_PREFIX = re.compile(r"^(ERROR:\s*)?(\[[^\]]+\]\s*)?([\w-]+:\s+)?", re.IGNORECASE)

# Order matters: the first match wins.
_RULES: tuple[tuple[str, str], ...] = (
    ("blocked_url", r"private or reserved address"),
    ("drm", r"\bdrm\b"),
    (
        "members_only",
        r"members[- ]only|join this channel|available to this channel's members|membership",
    ),
    ("paid", r"requires payment|purchase|rent this|paid content|buy this"),
    (
        "geo_blocked",
        r"available in your country|from your location|geo[- ]?restrict|in your region",
    ),
    ("private", r"private video|this video is private|video is private"),
    ("age_restricted", r"confirm your age|age[- ]restricted|inappropriate for some users"),
    ("bot_check", r"not a bot"),
    (
        "live_not_finished",
        r"premieres in|will begin|live event|is (currently )?live|this live stream|upcoming",
    ),
    (
        "login_required",
        r"sign in|log in|logged in|login required|registered users|requires authentication"
        r"|authentication is required|use --cookies|cookies are needed",
    ),
    # Often YouTube refusing anonymous downloads: the user's own cookies usually fix it.
    ("forbidden", r"http error 403|403: forbidden|\bforbidden\b"),
    ("unsupported", r"unsupported url"),
    (
        "unavailable",
        r"video unavailable|has been removed|no longer available|terminated"
        r"|does not exist|not found|\b404\b",
    ),
)


def clean_message(message: str) -> str:
    text = _ANSI.sub("", message).strip().splitlines()[0] if message.strip() else ""
    return _PREFIX.sub("", text, count=1).strip()[:300] or "unknown error"


def map_error(exc: BaseException) -> Exception:
    """Return a HandlerError (or BlockedURLError) describing why yt-dlp failed."""
    chain: list[BaseException] = [exc]
    inner = getattr(exc, "exc_info", None)
    if inner and len(inner) > 1 and isinstance(inner[1], BaseException):
        chain.append(inner[1])
    if exc.__cause__ is not None:
        chain.append(exc.__cause__)

    for item in chain:
        if isinstance(item, BlockedURLError):
            return item
        if type(item).__name__ == "GeoRestrictedError":
            return HandlerError("geo_blocked", clean_message(str(item)))

    text = " ".join(str(item) for item in chain)
    for code, pattern in _RULES:
        if re.search(pattern, text, re.IGNORECASE):
            if code == "blocked_url":
                return BlockedURLError(clean_message(str(exc)))
            return HandlerError(code, clean_message(str(exc)))
    return HandlerError("upstream", clean_message(str(exc)))
