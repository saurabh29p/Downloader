"""App settings, read from environment variables prefixed with ANYGET_ (and .env)."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from anyget import __version__

# Env vars set by hosting platforms: their presence means AnyGet is on the internet.
HOSTED_ENV = (
    "RAILWAY_ENVIRONMENT",
    "RAILWAY_PROJECT_ID",
    "RENDER",
    "FLY_APP_NAME",
    "K_SERVICE",  # Google Cloud Run
    "DYNO",  # Heroku
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ANYGET_", env_file=".env", extra="ignore")

    downloads_dir: Path = Path("./downloads")
    data_dir: Path = Path("./data")
    host: str = "127.0.0.1"
    port: int = 8000

    # Queue
    max_concurrent_downloads: int = Field(default=3, ge=1, le=16)
    max_per_host: int = Field(default=4, ge=1, le=16)
    host_limits: dict[str, int] = Field(
        default_factory=lambda: {
            "archive.org": 2,
            "gallica.bnf.fr": 2,
            "dl.ndl.go.jp": 2,
            "loc.gov": 2,
            "qdl.qa": 2,
        }
    )

    # Download speed limit in KiB/s for each download (0 = no limit).
    rate_limit_kbps: int = Field(default=0, ge=0, le=10_000_000)
    # Where new downloads go inside the downloads folder, e.g. "{type}/{source}".
    folder_template: str = ""
    # Watches (scheduled checks for new items) run only in the API server.
    watch_enabled: bool = True
    # Plugins (extra handlers from installed packages) to load; "*" loads all.
    plugins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    # Torrents (magnet links, .torrent files) need the optional libtorrent and are off
    # by default: peers are arbitrary addresses outside the SSRF guard.
    torrent_enabled: bool = False
    torrent_seed: bool = False
    # Optional AI helper (OpenRouter, v2 Phase 5). Free mode uses only ":free" models.
    llm_free_mode: bool = False
    llm_daily_limit: int = Field(default=500, ge=0, le=100_000)
    # Model lists override llm/models.py, comma separated (most preferred first).
    llm_router_models: Annotated[list[str], NoDecode] = Field(default_factory=list)
    llm_summary_models: Annotated[list[str], NoDecode] = Field(default_factory=list)
    # Sent to OpenRouter as HTTP-Referer (it identifies the app, not the user).
    app_url: str = "https://github.com/saurabh29p/Downloader"

    # Outgoing HTTP
    contact_email: str = ""
    request_timeout: float = 30.0
    # Explicit outgoing proxy (env HTTP(S)_PROXY is ignored on purpose). When set, the
    # connect-time SSRF check cannot see the final IP; the pre-flight DNS check still runs.
    proxy: str = ""
    # host:port pairs allowed even if they resolve to private IPs. Only for tests and
    # local fixture servers; leave empty in normal use.
    net_allowlist: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # ----- access control (see docs/deploy.md) ---------------------------------------
    # Bearer token for the CLI, the extension and scripts: "Authorization: Bearer <token>".
    api_token: str = Field(default="", repr=False)
    # Cloudflare Access: team domain (e.g. "myteam.cloudflareaccess.com") and the
    # application's AUD tag. When set, requests that come through Cloudflare must carry
    # a valid Cf-Access-Jwt-Assertion (or the bearer token).
    access_team_domain: str = ""
    access_aud: str = Field(default="", repr=False)
    # "auto": requests from this computer are allowed, requests through Cloudflare need
    # Access or the token. "always": every request needs Access or the token.
    auth_mode: Literal["auto", "always"] = "auto"
    # Owner sign-in (v2). When an owner is set, every /api request except /api/health
    # and the sign-in itself needs the session cookie, the bearer token or Access.
    # Make the hash with `anyget hash-password` (argon2id).
    owner_email: str = ""
    owner_password_hash: str = Field(default="", repr=False)
    # Signs the session cookie. Empty: a random key is made once in data/session.key.
    session_secret: str = Field(default="", repr=False)
    session_days: int = Field(default=30, ge=1, le=365)
    # Set to true when AnyGet is reachable from the internet (Railway, Fly, a VPS…).
    # Hosting platforms are also detected from their env vars. A public AnyGet without
    # an owner refuses every request (fails closed).
    public: bool = False
    # Requests per minute per client from outside (writes are limited separately).
    rate_limit_per_minute: int = Field(default=600, ge=10, le=100_000)
    rate_limit_writes_per_minute: int = Field(default=60, ge=1, le=100_000)

    # Optional keys for sources that need them. Never logged or returned by the API.
    github_token: str = Field(default="", repr=False)
    hf_token: str = Field(default="", repr=False)
    civitai_token: str = Field(default="", repr=False)
    kaggle_username: str = Field(default="", repr=False)
    kaggle_key: str = Field(default="", repr=False)
    # Free keys for library and book APIs.
    europeana_key: str = Field(default="", repr=False)
    dpla_key: str = Field(default="", repr=False)
    trove_key: str = Field(default="", repr=False)
    digitalnz_key: str = Field(default="", repr=False)
    bhl_key: str = Field(default="", repr=False)
    ddb_key: str = Field(default="", repr=False)

    # Movies (TMDB "where to watch") and the optional AI helper (OpenRouter). Both also
    # read their usual names, TMDB_API_KEY and OPENROUTER_API_KEY.
    tmdb_key: str = Field(
        default="", repr=False, validation_alias=AliasChoices("anyget_tmdb_key", "tmdb_api_key")
    )
    openrouter_key: str = Field(
        default="",
        repr=False,
        validation_alias=AliasChoices("anyget_openrouter_key", "openrouter_api_key"),
    )

    # Encrypts saved Connections (cookies, keys) at rest: a Fernet key from
    # `anyget gen-key`. Empty: a key is made once in data/secrets.key.
    secrets_key: str = Field(default="", repr=False)

    # Books: limit which sources are asked (empty = all), and Gutendex's address
    # (it is open source and can be self-hosted).
    book_sources: Annotated[list[str], NoDecode] = Field(default_factory=list)
    # Universal search: limit the sources asked (archive, books, videos, libraries).
    universal_sources: Annotated[list[str], NoDecode] = Field(default_factory=list)
    gutendex_url: str = "https://gutendex.com"

    @field_validator("net_allowlist", "book_sources", "universal_sources", "plugins", mode="before")
    @classmethod
    def _split_csv(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'anyget.db'}"

    @property
    def owner_configured(self) -> bool:
        return bool(self.owner_email.strip() and self.owner_password_hash.strip())

    @property
    def hosted(self) -> bool:
        """Reachable from the internet: set by ANYGET_PUBLIC or a hosting platform."""
        return self.public or any(os.environ.get(name) for name in HOSTED_ENV)

    @property
    def login_required(self) -> bool:
        return self.auth_mode == "always" or self.owner_configured or self.hosted

    @property
    def user_agent(self) -> str:
        contact = f"; +mailto:{self.contact_email}" if self.contact_email else ""
        return f"AnyGet/{__version__} (personal downloader{contact})"


@lru_cache
def get_settings() -> Settings:
    return Settings()
