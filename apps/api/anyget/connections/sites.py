"""Sites the user can connect: cookies from their own browser, or an API key/token.

Cookie sites give yt-dlp (and file downloads from that site) what the user's own
account can see, such as age-checked or sign-in-only videos. They never get around
DRM, paywalls, members-only content or region blocks (CLAUDE.md legal rules).
"""

from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["cookies", "key"]


@dataclass(frozen=True)
class Site:
    id: str
    label: str
    kind: Kind
    # Cookie sites: domains whose cookies belong to this connection.
    domains: tuple[str, ...] = ()
    # Cookie names that only exist when signed in (to tell "connected" from "expired").
    auth_cookies: tuple[str, ...] = ()
    # Key sites: the form fields and the Settings attributes they fill, in order.
    fields: tuple[str, ...] = ("token",)
    settings: tuple[str, ...] = ()
    # Where to get the key, or how to export cookies.
    help_url: str | None = None
    # Shown as the "Connect your <label> account" link for these hosts too.
    extra_hosts: tuple[str, ...] = field(default=())


COOKIE_HELP = "https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp"

SITES: tuple[Site, ...] = (
    Site(
        "youtube",
        "YouTube",
        "cookies",
        ("youtube.com", "youtu.be", "google.com"),
        ("SID", "__Secure-1PSID", "__Secure-3PSID", "LOGIN_INFO"),
        help_url=COOKIE_HELP,
    ),
    Site(
        "instagram",
        "Instagram",
        "cookies",
        ("instagram.com",),
        ("sessionid",),
        help_url=COOKIE_HELP,
    ),
    Site("x", "X", "cookies", ("x.com", "twitter.com"), ("auth_token",), help_url=COOKIE_HELP),
    Site(
        "facebook",
        "Facebook",
        "cookies",
        ("facebook.com", "fb.watch"),
        ("c_user", "xs"),
        help_url=COOKIE_HELP,
    ),
    Site(
        "reddit",
        "Reddit",
        "cookies",
        ("reddit.com",),
        ("reddit_session", "token_v2"),
        help_url=COOKIE_HELP,
    ),
    Site("vimeo", "Vimeo", "cookies", ("vimeo.com",), ("vimeo",), help_url=COOKIE_HELP),
    Site("patreon", "Patreon", "cookies", ("patreon.com",), ("session_id",), help_url=COOKIE_HELP),
    Site(
        "archive_org",
        "archive.org",
        "cookies",
        ("archive.org",),
        ("logged-in-user", "logged-in-sig"),
        help_url=COOKIE_HELP,
    ),
    Site(
        "github",
        "GitHub",
        "key",
        settings=("github_token",),
        help_url="https://github.com/settings/personal-access-tokens",
    ),
    Site(
        "huggingface",
        "Hugging Face",
        "key",
        settings=("hf_token",),
        help_url="https://huggingface.co/settings/tokens",
    ),
    Site(
        "civitai",
        "Civitai",
        "key",
        settings=("civitai_token",),
        help_url="https://civitai.com/user/account",
    ),
    Site(
        "kaggle",
        "Kaggle",
        "key",
        fields=("username", "key"),
        settings=("kaggle_username", "kaggle_key"),
        help_url="https://www.kaggle.com/settings",
    ),
    Site(
        "tmdb",
        "TMDB",
        "key",
        settings=("tmdb_key",),
        help_url="https://www.themoviedb.org/settings/api",
    ),
    Site(
        "openrouter",
        "OpenRouter",
        "key",
        settings=("openrouter_key",),
        help_url="https://openrouter.ai/settings/keys",
    ),
    Site(
        "europeana",
        "Europeana",
        "key",
        settings=("europeana_key",),
        help_url="https://pro.europeana.eu/pages/get-api",
    ),
    Site(
        "dpla",
        "DPLA",
        "key",
        settings=("dpla_key",),
        help_url="https://pro.dp.la/developers/api-codex",
    ),
    Site(
        "trove",
        "Trove",
        "key",
        settings=("trove_key",),
        help_url="https://trove.nla.gov.au/about/create-something/using-api",
    ),
    Site(
        "digitalnz",
        "DigitalNZ",
        "key",
        settings=("digitalnz_key",),
        help_url="https://digitalnz.org/developers",
    ),
    Site(
        "bhl",
        "Biodiversity Heritage Library",
        "key",
        settings=("bhl_key",),
        help_url="https://www.biodiversitylibrary.org/getapikey",
    ),
    Site(
        "ddb",
        "Deutsche Digitale Bibliothek",
        "key",
        settings=("ddb_key",),
        help_url="https://api.deutsche-digitale-bibliothek.de/",
    ),
)
BY_ID: dict[str, Site] = {s.id: s for s in SITES}
COOKIE_SITES = tuple(s for s in SITES if s.kind == "cookies")
# Every Settings attribute that a key connection can fill.
KEY_SETTINGS = tuple(name for s in SITES for name in s.settings)


def host_matches(host: str, domain: str) -> bool:
    host = host.lower().lstrip(".")
    return host == domain or host.endswith(f".{domain}")


def cookie_site_for_host(host: str) -> Site | None:
    for site in COOKIE_SITES:
        if any(host_matches(host, d) for d in site.domains):
            return site
    return None
