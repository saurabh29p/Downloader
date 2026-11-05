"""Owner sign-in: argon2 password check and the signed session cookie.

The cookie holds `{"uid", "iat"}` signed with HMAC-SHA256. The signing key mixes the
session secret with the password hash, so changing the password signs everyone out.
AnyGet has one user today (the owner, id "owner"); `user_id` columns are ready for more.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from pathlib import Path
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from anyget.core.settings import Settings
from anyget.core.users import OWNER_ID

log = logging.getLogger("anyget.session")

COOKIE = "anyget_session"
# Web writes send this header; browsers can't add it to cross-site requests (CSRF).
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "anyget"

_hasher = PasswordHasher()
# Checked when the email is wrong, so a wrong email takes as long as a wrong password.
_DUMMY = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _secret_file(settings: Settings) -> Path:
    return settings.data_dir / "session.key"


def session_secret(settings: Settings) -> bytes:
    """ANYGET_SESSION_SECRET, or a random key kept in data/session.key (0600)."""
    if settings.session_secret:
        return settings.session_secret.encode()
    path = _secret_file(settings)
    if path.is_file():
        return path.read_bytes().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(48).encode()
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:  # another worker made it first
        return path.read_bytes().strip()
    with os.fdopen(fd, "wb") as handle:
        handle.write(key)
    return key


class Sessions:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._key: bytes | None = None

    def _signing_key(self) -> bytes:
        if self._key is None:
            self._key = session_secret(self.settings)
        mix = self._key + b"\0" + self.settings.owner_password_hash.encode()
        return hashlib.sha256(mix).digest()

    @property
    def max_age(self) -> int:
        return self.settings.session_days * 86400

    def check_password(self, email: str, password: str) -> str | None:
        """The user id when the email and password match the owner, else None."""
        s = self.settings
        if not s.owner_configured:
            return None
        email_ok = hmac.compare_digest(
            email.strip().lower().encode(), s.owner_email.strip().lower().encode()
        )
        stored = s.owner_password_hash.strip() if email_ok else _DUMMY
        try:
            _hasher.verify(stored, password)
        except (VerifyMismatchError, VerificationError):
            return None
        except InvalidHashError:
            log.error("ANYGET_OWNER_PASSWORD_HASH is not an argon2 hash")
            return None
        return OWNER_ID if email_ok else None

    def issue(self, user_id: str, now: float | None = None) -> str:
        payload = _b64(json.dumps({"uid": user_id, "iat": int(now or time.time())}).encode())
        mac = hmac.new(self._signing_key(), payload.encode(), hashlib.sha256).digest()
        return f"{payload}.{_b64(mac)}"

    def verify(self, token: str, now: float | None = None) -> str | None:
        """The user id in a valid, unexpired cookie, else None."""
        if not self.settings.owner_configured:
            return None
        payload, _, mac = token.partition(".")
        if not payload or not mac:
            return None
        expected = hmac.new(self._signing_key(), payload.encode(), hashlib.sha256).digest()
        try:
            if not hmac.compare_digest(expected, _unb64(mac)):
                return None
            data: Any = json.loads(_unb64(payload))
        except (ValueError, TypeError):
            return None
        if not isinstance(data, dict):
            return None
        iat, uid = data.get("iat"), data.get("uid")
        if not isinstance(iat, int) or not isinstance(uid, str):
            return None
        age = (now or time.time()) - iat
        if age < -60 or age > self.max_age:
            return None
        return uid
