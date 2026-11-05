"""Settings changed in the app, saved in SQLite. They override .env/environment.

Only the fields in EDITABLE can be changed this way. API keys are not settings any
more: they live in Connections (encrypted, v2). Rows saved by v1 are moved there once
(`pop_legacy_secrets`).
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

# v1 saved these here in plain text; Services.build moves them into Connections.
LEGACY_SECRETS = (
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
EDITABLE = PLAIN
# Read when the HTTP client is built: changing them needs a restart.
RESTART_NEEDED = ("proxy",)


class SettingRow(SQLModel, table=True):
    __tablename__ = "setting"

    key: str = SQLField(primary_key=True)
    value: str  # JSON


class SettingsUpdate(BaseModel):
    """Fields to change; omitted fields stay as they are."""

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

    def pop_legacy_secrets(self) -> dict[str, str]:
        """API keys saved by v1 (plain text): returned once, then deleted here."""
        found: dict[str, str] = {}
        with self.db.session() as session:
            for row in session.exec(select(SettingRow)).all():
                if row.key not in LEGACY_SECRETS:
                    continue
                try:
                    value = json.loads(row.value)
                except ValueError:
                    value = ""
                if isinstance(value, str) and value:
                    found[row.key] = value
                session.delete(row)
            session.commit()
        return found

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
            restart_needed=sorted(self.pending_restart),
        )

    def save(self, update: SettingsUpdate) -> list[str]:
        """Store and apply the given fields; returns the names that changed."""
        changes: dict[str, Any] = update.model_dump(exclude_unset=True)
        changed = []
        with self.db.session() as session:
            for key, value in changes.items():
                if value is None:
                    continue
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
