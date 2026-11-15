"""Saved connections, encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256).

The key is ANYGET_SECRETS_KEY, or a random key kept in data/secrets.key (0600) when it
is not set. Values are never logged and never returned by the API: views say only
whether a site is connected, since when, and until when its cookies last.

Key connections fill the matching Settings attributes (github_token, tmdb_key…), so
every adapter keeps reading settings as before. Removing a connection brings back the
value from the environment, if there was one.
"""

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel, select

from anyget.connections.sites import BY_ID, COOKIE_SITES, KEY_SETTINGS, SITES, Site, host_matches
from anyget.core.db import Database
from anyget.core.settings import Settings
from anyget.core.users import OWNER_ID

log = logging.getLogger("anyget.connections")

Status = Literal["connected", "not_connected", "expired", "server"]


def _now() -> datetime:
    return datetime.now(UTC)


class Connection(SQLModel, table=True):
    __tablename__ = "connection"
    __table_args__ = (UniqueConstraint("user_id", "site"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    site: str = Field(index=True)
    # Fernet token of {"cookies": "...", "fields": {...}, "proxy": "..."}.
    ciphertext: str
    cookie_count: int = 0
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    last_test_at: datetime | None = None
    last_test_ok: bool | None = None


class ConnectionView(BaseModel):
    id: str
    label: str
    kind: Literal["cookies", "key"]
    fields: list[str]
    status: Status
    connected_on: datetime | None = None
    expires_on: datetime | None = None
    cookie_count: int | None = None
    proxy: bool = False
    last_test_ok: bool | None = None
    last_test_at: datetime | None = None
    help_url: str | None = None


class ConnectionsView(BaseModel):
    # "env": ANYGET_SECRETS_KEY is set; "file": the key is in data/secrets.key.
    key_source: Literal["env", "file"]
    sites: list[ConnectionView]


class ConnectionValueError(ValueError):
    """A connection value that can't be used (bad cookies file, missing field…).

    `code` is the API error code; each one has a plain-words message in the web app.
    """

    def __init__(self, message: str, code: str = "invalid_connection") -> None:
        super().__init__(message)
        self.code = code


# ----- cookies.txt ---------------------------------------------------------------


def parse_cookies(text: str) -> list[list[str]]:
    """Cookie lines of a Netscape cookies.txt as 7 fields each (#HttpOnly_ kept)."""
    rows = []
    for raw in text.splitlines():
        line = raw.rstrip("\r\n")
        if not line.strip() or (line.startswith("#") and not line.startswith("#HttpOnly_")):
            continue
        parts = line.split("\t")
        if len(parts) != 7:
            raise ConnectionValueError("this is not a Netscape cookies.txt file", "not_cookies_txt")
        rows.append(parts)
    if not rows:
        raise ConnectionValueError("this cookies.txt file has no cookies", "no_cookies")
    return rows


def _domain(row: list[str]) -> str:
    return row[0].removeprefix("#HttpOnly_").lstrip(".").lower()


def rows_for(site: Site, rows: list[list[str]]) -> list[list[str]]:
    return [r for r in rows if any(host_matches(_domain(r), d) for d in site.domains)]


def _expiry(row: list[str]) -> int:
    try:
        return int(row[4])
    except ValueError:
        return 0


def cookie_expiry(site: Site, rows: list[list[str]]) -> datetime | None:
    """When the sign-in cookies stop working (None: session cookies or unknown)."""
    auth = [r for r in rows if r[5] in site.auth_cookies] or rows
    stamps = [_expiry(r) for r in auth if _expiry(r) > 0]
    return datetime.fromtimestamp(max(stamps), UTC) if stamps else None


def to_text(rows: list[list[str]]) -> str:
    return "# Netscape HTTP Cookie File\n" + "".join("\t".join(r) + "\n" for r in rows)


# ----- the store -----------------------------------------------------------------


def _key_file(settings: Settings) -> Path:
    return settings.data_dir / "secrets.key"


def load_key(settings: Settings) -> bytes:
    if settings.secrets_key:
        key = settings.secrets_key.strip().encode()
        try:
            Fernet(key)
        except ValueError as exc:
            raise RuntimeError("ANYGET_SECRETS_KEY is not a Fernet key (anyget gen-key)") from exc
        return key
    path = _key_file(settings)
    if path.is_file():
        return path.read_bytes().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path.read_bytes().strip()
    with os.fdopen(fd, "wb") as handle:
        handle.write(key)
    return key


def new_key() -> str:
    return Fernet.generate_key().decode()


class ConnectionStore:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self._fernet = Fernet(load_key(settings))
        # Values from .env/environment, restored when a key connection is removed.
        self._env = {name: getattr(settings, name) for name in KEY_SETTINGS}

    @property
    def key_source(self) -> Literal["env", "file"]:
        return "env" if self.settings.secrets_key else "file"

    # ----- encryption ----------------------------------------------------------

    def _seal(self, payload: dict[str, Any]) -> str:
        return self._fernet.encrypt(json.dumps(payload).encode()).decode()

    def _open(self, row: Connection) -> dict[str, Any]:
        try:
            data: dict[str, Any] = json.loads(self._fernet.decrypt(row.ciphertext.encode()))
        except (InvalidToken, ValueError):
            log.warning("connection %s can't be decrypted (was the key changed?)", row.site)
            return {}
        return data

    # ----- rows ----------------------------------------------------------------

    def _row(self, user_id: str, site: str) -> Connection | None:
        with self.db.session() as session:
            query = select(Connection).where(Connection.user_id == user_id, Connection.site == site)
            return session.exec(query).first()

    def _put(
        self,
        user_id: str,
        site: Site,
        payload: dict[str, Any],
        *,
        cookie_count: int = 0,
        expires_at: datetime | None = None,
    ) -> None:
        with self.db.session() as session:
            query = select(Connection).where(
                Connection.user_id == user_id, Connection.site == site.id
            )
            row = session.exec(query).first() or Connection(
                user_id=user_id, site=site.id, ciphertext=""
            )
            row.ciphertext = self._seal(payload)
            row.cookie_count = cookie_count
            row.expires_at = expires_at
            row.updated_at = _now()
            row.last_test_at = None
            row.last_test_ok = None
            session.add(row)
            session.commit()
        log.info("connection saved: %s", site.id)  # names only, never values

    def payload(self, user_id: str, site_id: str) -> dict[str, Any]:
        row = self._row(user_id, site_id)
        return self._open(row) if row else {}

    # ----- saving --------------------------------------------------------------

    def save_cookies(self, user_id: str, site: Site, text: str, proxy: str | None = None) -> int:
        rows = rows_for(site, parse_cookies(text))
        if not rows:
            raise ConnectionValueError(
                f"this file has no cookies for {site.domains[0]}", "cookies_wrong_site"
            )
        self._put(
            user_id,
            site,
            {"cookies": to_text(rows), "proxy": proxy or None},
            cookie_count=len(rows),
            expires_at=cookie_expiry(site, rows),
        )
        return len(rows)

    def import_cookies(self, user_id: str, text: str) -> list[str]:
        """Split one cookies.txt into a connection per site it has cookies for."""
        rows = parse_cookies(text)
        saved = []
        for site in COOKIE_SITES:
            mine = rows_for(site, rows)
            if mine:
                old = self.payload(user_id, site.id)
                self._put(
                    user_id,
                    site,
                    {"cookies": to_text(mine), "proxy": old.get("proxy")},
                    cookie_count=len(mine),
                    expires_at=cookie_expiry(site, mine),
                )
                saved.append(site.id)
        return saved

    def save_fields(
        self, user_id: str, site: Site, values: dict[str, str], proxy: str | None = None
    ) -> None:
        clean = {name: (values.get(name) or "").strip() for name in site.fields}
        missing = [name for name, value in clean.items() if not value]
        if missing:
            raise ConnectionValueError(f"fill in: {', '.join(missing)}", "missing_fields")
        self._put(user_id, site, {"fields": clean, "proxy": proxy or None})
        self.apply()

    def set_proxy(self, user_id: str, site: Site, proxy: str | None) -> bool:
        row = self._row(user_id, site.id)
        if row is None:
            return False
        payload = {**self._open(row), "proxy": proxy or None}
        with self.db.session() as session:
            stored = session.get(Connection, row.id)
            if stored is None:
                return False
            stored.ciphertext = self._seal(payload)
            stored.updated_at = _now()
            session.add(stored)
            session.commit()
        return True

    def delete(self, user_id: str, site_id: str) -> bool:
        row = self._row(user_id, site_id)
        if row is None:
            return False
        with self.db.session() as session:
            stored = session.get(Connection, row.id)
            if stored is not None:
                session.delete(stored)
                session.commit()
        log.info("connection removed: %s", site_id)
        self.apply()
        return True

    def record_test(self, user_id: str, site_id: str, ok: bool) -> None:
        row = self._row(user_id, site_id)
        if row is None:
            return
        with self.db.session() as session:
            stored = session.get(Connection, row.id)
            if stored is not None:
                stored.last_test_at = _now()
                stored.last_test_ok = ok
                session.add(stored)
                session.commit()

    # ----- using ---------------------------------------------------------------

    def apply(self, user_id: str = OWNER_ID) -> None:
        """Key connections fill Settings; without one, the environment's value is back."""
        for name in KEY_SETTINGS:
            setattr(self.settings, name, self._env.get(name, ""))
        for site in SITES:
            if site.kind != "key":
                continue
            fields = self.payload(user_id, site.id).get("fields") or {}
            for field_name, setting in zip(site.fields, site.settings, strict=True):
                if fields.get(field_name):
                    setattr(self.settings, setting, fields[field_name])

    def cookies_for(self, url_host: str, user_id: str = OWNER_ID) -> tuple[str, str | None]:
        """(cookies.txt text, proxy) for the site of this host; ("", None) if none."""
        site = next(
            (s for s in COOKIE_SITES if any(host_matches(url_host, d) for d in s.domains)), None
        )
        if site is None:
            return "", None
        payload = self.payload(user_id, site.id)
        return str(payload.get("cookies") or ""), payload.get("proxy") or None

    def write_cookie_file(self, url_host: str, target: Path, user_id: str = OWNER_ID) -> bool:
        """Write this site's cookies to a 0600 file for one job; False if there are none."""
        text, _ = self.cookies_for(url_host, user_id)
        if not text:
            return False
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        return True

    def proxy_for(self, url_host: str, user_id: str = OWNER_ID) -> str | None:
        site = next(
            (s for s in COOKIE_SITES if any(host_matches(url_host, d) for d in s.domains)), None
        )
        return (self.payload(user_id, site.id).get("proxy") or None) if site else None

    # ----- views ---------------------------------------------------------------

    def view(self, user_id: str = OWNER_ID) -> ConnectionsView:
        with self.db.session() as session:
            rows = {
                r.site: r
                for r in session.exec(select(Connection).where(Connection.user_id == user_id))
            }
        now = _now()
        sites = []
        for site in SITES:
            row = rows.get(site.id)
            status: Status = "not_connected"
            if row is not None:
                expires = row.expires_at.replace(tzinfo=UTC) if row.expires_at else None
                status = "expired" if expires and expires < now else "connected"
            elif site.kind == "key" and any(self._env.get(n) for n in site.settings):
                status = "server"  # set in the server's environment
            proxy = bool(row and self._open(row).get("proxy"))
            sites.append(
                ConnectionView(
                    id=site.id,
                    label=site.label,
                    kind=site.kind,
                    fields=list(site.fields) if site.kind == "key" else [],
                    status=status,
                    connected_on=_utc(row.updated_at) if row else None,
                    expires_on=_utc(row.expires_at) if row else None,
                    cookie_count=row.cookie_count if row and site.kind == "cookies" else None,
                    proxy=proxy,
                    last_test_ok=row.last_test_ok if row else None,
                    last_test_at=_utc(row.last_test_at) if row else None,
                    help_url=site.help_url,
                )
            )
        return ConnectionsView(key_source=self.key_source, sites=sites)


def _utc(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def site_or_none(site_id: str) -> Site | None:
    return BY_ID.get(site_id)
