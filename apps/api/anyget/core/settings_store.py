"""Settings changed in the app, saved in SQLite. They override .env/environment.

Only the fields in EDITABLE can be changed this way. Secrets (API keys) are
write-only: the API reports whether one is set, never its value.
"""

import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel, select

from anyget.core.db import Database
from anyget.core.settings import Settings
from anyget.core.templates import TemplateError, validate
from anyget.handlers.torrent import load_libtorrent

SECRETS = (
    "github_token",
    "hf_token",
    "civitai_token",
    "kaggle_username",
    "kaggle_key",
    "europeana_key",
    "dpla_key",
    "trove_key",
    "digitalnz_key",
    "bhl_key",
    "ddb_key",
)
PLAIN = (
    "folder_template",
    "max_concurrent_downloads",
    "max_per_host",
    "host_limits",
    "rate_limit_kbps",
    "proxy",
    "contact_email",
    "watch_enabled",
    "torrent_enabled",
    "torrent_seed",
)
EDITABLE = PLAIN + SECRETS
# Read when the HTTP client is built: changing them needs a restart.
RESTART_NEEDED = ("proxy",)


class SettingRow(SQLModel, table=True):
    __tablename__ = "setting"

    key: str = SQLField(primary_key=True)
    value: str  # JSON


class SettingsUpdate(BaseModel):
    """Fields to change; omitted fields stay as they are. An empty secret clears it."""

    folder_template: str | None = Field(default=None, max_length=200)
    max_concurrent_downloads: int | None = Field(default=None, ge=1, le=16)
    max_per_host: int | None = Field(default=None, ge=1, le=16)
    host_limits: dict[str, int] | None = None
    rate_limit_kbps: int | None = Field(default=None, ge=0, le=10_000_000)
    proxy: str | None = Field(default=None, max_length=300)
    contact_email: str | None = Field(default=None, max_length=200)
    watch_enabled: bool | None = None
    torrent_enabled: bool | None = None
    torrent_seed: bool | None = None
    github_token: str | None = Field(default=None, max_length=500)
    hf_token: str | None = Field(default=None, max_length=500)
    civitai_token: str | None = Field(default=None, max_length=500)
    kaggle_username: str | None = Field(default=None, max_length=200)
    kaggle_key: str | None = Field(default=None, max_length=500)
    europeana_key: str | None = Field(default=None, max_length=500)
    dpla_key: str | None = Field(default=None, max_length=500)
    trove_key: str | None = Field(default=None, max_length=500)
    digitalnz_key: str | None = Field(default=None, max_length=500)
    bhl_key: str | None = Field(default=None, max_length=500)
    ddb_key: str | None = Field(default=None, max_length=500)

    @field_validator("folder_template")
    @classmethod
    def _template(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return validate(value)
        except TemplateError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("host_limits")
    @classmethod
    def _limits(cls, value: dict[str, int] | None) -> dict[str, int] | None:
        if value is None:
            return None
        clean = {}
        for host, limit in value.items():
            host = host.strip().lower()
            if not host or "/" in host or not 1 <= int(limit) <= 16:
                raise ValueError("host limits are host names with a limit from 1 to 16")
            clean[host] = int(limit)
        return clean

    @field_validator("proxy")
    @classmethod
    def _proxy(cls, value: str | None) -> str | None:
        if value and not value.startswith(("http://", "https://", "socks5://", "socks5h://")):
            raise ValueError("the proxy must start with http://, https:// or socks5://")
        return value


class SettingsView(BaseModel):
    downloads_dir: str
    folder_template: str
    max_concurrent_downloads: int
    max_per_host: int
    host_limits: dict[str, int]
    rate_limit_kbps: int
    proxy: str
    contact_email: str
    watch_enabled: bool
    torrent_enabled: bool
    torrent_seed: bool
    torrent_available: bool
    secrets: dict[str, bool]  # name → is it set
    restart_needed: list[str] = Field(default_factory=list)


class SettingsStore:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.pending_restart: set[str] = set()

    def load(self) -> None:
        """Apply saved values on top of the environment (call once at startup)."""
        with self.db.session() as session:
            rows = list(session.exec(select(SettingRow)).all())
        for row in rows:
            if row.key not in EDITABLE:
                continue
            try:
                value = json.loads(row.value)
                checked = SettingsUpdate.model_validate({row.key: value})
            except (ValueError, ValidationError):
                continue  # an old or broken row never stops the app
            setattr(self.settings, row.key, getattr(checked, row.key))

    def view(self) -> SettingsView:
        s = self.settings
        return SettingsView(
            downloads_dir=str(s.downloads_dir.resolve()),
            folder_template=s.folder_template,
            max_concurrent_downloads=s.max_concurrent_downloads,
            max_per_host=s.max_per_host,
            host_limits=dict(s.host_limits),
            rate_limit_kbps=s.rate_limit_kbps,
            proxy=s.proxy,
            contact_email=s.contact_email,
            watch_enabled=s.watch_enabled,
            torrent_enabled=s.torrent_enabled,
            torrent_seed=s.torrent_seed,
            torrent_available=load_libtorrent() is not None,
            secrets={name: bool(getattr(s, name)) for name in SECRETS},
            restart_needed=sorted(self.pending_restart),
        )

    def save(self, update: SettingsUpdate) -> list[str]:
        """Store and apply the given fields; returns the names that changed."""
        changes: dict[str, Any] = update.model_dump(exclude_unset=True)
        changed = []
        with self.db.session() as session:
            for key, value in changes.items():
                if value is None and key not in SECRETS:
                    continue
                value = "" if value is None else value
                if getattr(self.settings, key) == value:
                    continue
                row = session.get(SettingRow, key) or SettingRow(key=key, value="")
                row.value = json.dumps(value)
                session.add(row)
                setattr(self.settings, key, value)
                changed.append(key)
                if key in RESTART_NEEDED:
                    self.pending_restart.add(key)
            session.commit()
        return changed
