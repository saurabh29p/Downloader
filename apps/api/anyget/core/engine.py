"""Updating yt-dlp without a new AnyGet image ("Update yt-dlp" in Settings → Advanced and
`anyget update-engine`). Sites change every week and yt-dlp follows them.

An update downloads the yt-dlp wheel and its matching yt-dlp-ejs wheel from PyPI through
`Net` (the SSRF guard), checks each file against the SHA-256 that PyPI publishes, and
unpacks both into `data/engine/<version>/`. Both are pure-Python wheels, so a wheel is
only a zip: nothing is written to the image or the virtual environment, and no pip runs.

The next start puts that folder first on `sys.path` (`activate`), but only when its
version is newer than the bundled one, so a newer AnyGet image still wins. Before an
update is accepted, a fresh Python process must import the new yt-dlp and install the
network guard (`net_guard`) on it. If that fails, the update is refused: yt-dlp's sockets
must never run unguarded.
"""

import asyncio
import contextlib
import hashlib
import importlib
import importlib.metadata
import logging
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from anyget.core.net import Net
from anyget.handlers.base import HandlerError

log = logging.getLogger(__name__)

PYPI = "https://pypi.org/pypi"
MAX_WHEEL = 50 * 1024 * 1024
CHECK_TIMEOUT = 120
_EJS = re.compile(r"^yt-dlp-ejs\s*==\s*([0-9][0-9A-Za-z.+-]*)")
_VERSION = re.compile(r"^[0-9]+(\.[0-9]+)*$")
_lock = asyncio.Lock()

# Run in a fresh process: import the new yt-dlp first on sys.path, install the guard on it
# (net_guard refuses when it hooks nothing) and report the version that was imported.
_SELF_CHECK = """
import sys
sys.path.insert(0, sys.argv[1])
from anyget.core import net_guard
net_guard.install()
import yt_dlp.version, yt_dlp_ejs
print(yt_dlp.version.__version__)
"""


def engine_root(data_dir: Path) -> Path:
    return data_dir / "engine"


def version_key(version: str) -> tuple[int, ...]:
    """yt-dlp versions are dates with optional parts (2026.10.26, 2026.11.03.1)."""
    return tuple(int(part) for part in version.split(".") if part.isdigit())


def _bundled() -> str | None:
    """The yt-dlp in the image or venv (not one this module put on sys.path)."""
    with contextlib.suppress(importlib.metadata.PackageNotFoundError):
        return importlib.metadata.version("yt-dlp")
    return None


def installed_update(data_dir: Path) -> str | None:
    """The version of the updated yt-dlp in the data folder, if one is installed."""
    root = engine_root(data_dir)
    try:
        name = (root / "current").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not _VERSION.match(name) or not (root / name / "yt_dlp").is_dir():
        return None
    return name


_active: str | None = None
_bundled_version: str | None = None  # remembered before an update goes on sys.path


def bundled_version() -> str | None:
    return _bundled_version if _active else _bundled()


def activate(data_dir: Path) -> str | None:
    """Put an updated yt-dlp first on sys.path when it is newer than the bundled one.

    Call before yt_dlp is imported (Services.build does). Returns the version now in use
    from the data folder, or None for the bundled yt-dlp.
    """
    global _active, _bundled_version
    if _active is not None:
        return _active
    update = installed_update(data_dir)
    if update is None or "yt_dlp" in sys.modules:
        return None
    bundled = _bundled()
    if bundled and version_key(update) <= version_key(bundled):
        return None
    sys.path.insert(0, str(engine_root(data_dir) / update))
    importlib.invalidate_caches()
    _active, _bundled_version = update, bundled
    log.info("using the updated yt-dlp %s from the data folder", update)
    return update


@dataclass
class EngineStatus:
    running: str | None  # the yt-dlp this process uses
    bundled: str | None
    updated: str | None  # installed in the data folder (used after a restart if newer)
    latest: str | None  # on PyPI, None when it couldn't be checked

    @property
    def restart_needed(self) -> bool:
        return bool(
            self.updated
            and self.updated != self.running
            and (not self.bundled or version_key(self.updated) > version_key(self.bundled))
        )

    @property
    def update_available(self) -> bool:
        newest = max((v for v in (self.running, self.updated) if v), key=version_key, default=None)
        return bool(
            self.latest and (newest is None or version_key(self.latest) > version_key(newest))
        )


def running_version() -> str | None:
    if _active:
        return _active
    return _bundled()


async def latest_version(net: Net) -> str | None:
    try:
        response = await net.request("GET", f"{PYPI}/yt-dlp/json")
        if response.status_code != 200:
            return None
        version = str(response.json().get("info", {}).get("version") or "")
    except Exception:  # unreachable, blocked or odd JSON: "couldn't check"
        log.info("could not check the latest yt-dlp", exc_info=True)
        return None
    return version if _VERSION.match(version) else None


async def status(net: Net, data_dir: Path, check_latest: bool = True) -> EngineStatus:
    return EngineStatus(
        running=running_version(),
        bundled=bundled_version(),
        updated=installed_update(data_dir),
        latest=await latest_version(net) if check_latest else None,
    )


async def _release(net: Net, package: str, version: str) -> dict[str, Any]:
    response = await net.request("GET", f"{PYPI}/{package}/{version}/json")
    if response.status_code != 200:
        raise HandlerError("upstream", f"PyPI answered {response.status_code} for {package}")
    data: dict[str, Any] = response.json()
    return data


def _wheel(release: dict[str, Any], package: str) -> dict[str, Any]:
    for file in release.get("urls", []):
        name = str(file.get("filename", ""))
        if file.get("packagetype") == "bdist_wheel" and name.endswith("-py3-none-any.whl"):
            return dict(file)
    raise HandlerError("upstream", f"PyPI has no pure-Python wheel for {package}")


async def _download(net: Net, file: dict[str, Any], target: Path) -> None:
    expected = str(file.get("digests", {}).get("sha256", "")).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise HandlerError("checksum", "PyPI gave no SHA-256 for the file")
    digest = hashlib.sha256()
    size = 0
    async with net.stream("GET", str(file["url"])) as response:
        if response.status_code != 200:
            raise HandlerError("upstream", f"the download answered {response.status_code}")
        with target.open("wb") as fh:
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > MAX_WHEEL:
                    raise HandlerError("upstream", "the yt-dlp download is unexpectedly large")
                digest.update(chunk)
                fh.write(chunk)
    if digest.hexdigest() != expected:
        raise HandlerError("checksum", f"{file.get('filename')} does not match PyPI's SHA-256")


def unpack_wheel(wheel: Path, target: Path) -> None:
    """Unzip a pure-Python wheel; refuse absolute paths, `..` and links."""
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            name = PurePosixPath(info.filename)
            if name.is_absolute() or ".." in name.parts or "\\" in info.filename:
                raise HandlerError("unsafe_path", f"unsafe path in the wheel: {info.filename}")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:  # a symlink entry
                raise HandlerError("unsafe_path", f"link in the wheel: {info.filename}")
        archive.extractall(target)


def self_check(folder: Path) -> str:
    """Import the new yt-dlp with the guard in a fresh process; returns its version."""
    try:
        result = subprocess.run(  # noqa: S603 - fixed arguments, no shell
            [sys.executable, "-c", _SELF_CHECK, str(folder)],
            capture_output=True,
            text=True,
            timeout=CHECK_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HandlerError("engine_check_failed", "the new yt-dlp took too long to load") from exc
    if result.returncode != 0:
        detail = (result.stderr.strip().splitlines() or ["no output"])[-1][:300]
        raise HandlerError("engine_check_failed", f"the new yt-dlp failed its check: {detail}")
    return result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""


async def update(net: Net, data_dir: Path) -> EngineStatus:
    """Install the latest yt-dlp (and its yt-dlp-ejs) into the data folder."""
    async with _lock:
        latest = await latest_version(net)
        if latest is None:
            raise HandlerError("network", "could not reach PyPI to find the latest yt-dlp")
        current = await status(net, data_dir, check_latest=False)
        current.latest = latest
        if not current.update_available:
            return current
        release = await _release(net, "yt-dlp", latest)
        requires = release.get("info", {}).get("requires_dist") or []
        ejs = next((m.group(1) for r in requires if (m := _EJS.match(str(r)))), None)
        root = engine_root(data_dir)
        staging = root / f".staging-{latest}"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        try:
            packages = [("yt-dlp", latest, release)]
            if ejs:
                packages.append(("yt-dlp-ejs", ejs, await _release(net, "yt-dlp-ejs", ejs)))
            for package, _version, data in packages:
                file = _wheel(data, package)
                wheel = staging.parent / f".{file['filename']}"
                try:
                    await _download(net, file, wheel)
                    unpack_wheel(wheel, staging)
                finally:
                    wheel.unlink(missing_ok=True)
            checked = await asyncio.to_thread(self_check, staging)
            if checked != latest:
                raise HandlerError(
                    "engine_check_failed", f"expected yt-dlp {latest}, the check loaded {checked}"
                )
            final = root / latest
            shutil.rmtree(final, ignore_errors=True)
            staging.rename(final)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        marker = root / "current.tmp"
        marker.write_text(latest, encoding="utf-8")
        marker.replace(root / "current")
        for old in root.iterdir():  # keep only the new version (and what is running)
            if (
                old.is_dir()
                and old.name not in (latest, _active or "")
                and _VERSION.match(old.name)
            ):
                shutil.rmtree(old, ignore_errors=True)
        log.info("installed yt-dlp %s into the data folder", latest)
        done = await status(net, data_dir, check_latest=False)
        done.latest = latest
        return done
