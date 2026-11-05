"""Backups of AnyGet's data folder: database (jobs, library, watches, saved settings),
cookies.txt and download archives. Downloaded files themselves are not included.

The database is copied with SQLite's online backup, so a backup taken while AnyGet runs
is consistent. Restoring replaces the data folder's files; stop AnyGet first.
Backups can contain cookies and API keys saved in Settings: they are written 0600.
"""

import io
import json
import os
import sqlite3
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from anyget import __version__

DB_NAME = "anyget.db"
EXTRA = ("cookies.txt", "archives")
MANIFEST = "anyget-backup.json"


class BackupError(Exception):
    pass


def _sqlite_copy(source: Path, target: Path) -> None:
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src, sqlite3.connect(target) as dst:
        src.backup(dst)


def create(data_dir: Path, out_dir: Path, *, include_env: Path | None = None) -> Path:
    data_dir, out_dir = data_dir.resolve(), out_dir.resolve()
    db = data_dir / DB_NAME
    if not db.is_file():
        raise BackupError(f"no database at {db}")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    target = out_dir / f"anyget-{stamp}.tar.gz"
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / DB_NAME
        _sqlite_copy(db, copy)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as raw, tarfile.open(fileobj=raw, mode="w:gz") as tar:
            files = [DB_NAME]
            tar.add(copy, arcname=DB_NAME)
            for name in EXTRA:
                path = data_dir / name
                if path.exists():
                    tar.add(path, arcname=name)
                    files.append(name)
            if include_env is not None and include_env.is_file():
                tar.add(include_env, arcname=".env")
                files.append(".env")
            manifest = {
                "version": __version__,
                "created": datetime.now(UTC).isoformat(),
                "files": files,
            }
            blob = json.dumps(manifest, indent=2).encode()
            info = tarfile.TarInfo(MANIFEST)
            info.size = len(blob)
            info.mode = 0o600
            tar.addfile(info, io.BytesIO(blob))
    return target


def _safe_members(tar: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = []
    for member in tar.getmembers():
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise BackupError(f"unsafe path in backup: {member.name}")
        if not (member.isfile() or member.isdir()):
            raise BackupError(f"links and devices are not allowed in a backup: {member.name}")
        members.append(member)
    return members


def restore(archive: Path, data_dir: Path, *, env_target: Path | None = None) -> list[str]:
    """Replace the data folder's database, cookies and archives with the backup's."""
    data_dir = data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        members = _safe_members(tar)
        names = {m.name.split("/", 1)[0] for m in members}
        if DB_NAME not in names or MANIFEST not in names:
            raise BackupError("this is not an AnyGet backup")
        with tempfile.TemporaryDirectory(dir=data_dir) as tmp:
            tar.extractall(tmp, members=members, filter="data")
            restored = []
            for name in (DB_NAME, *EXTRA):
                source = Path(tmp) / name
                if not source.exists():
                    continue
                target = data_dir / name
                if target.is_dir() and source.is_dir():
                    for old in sorted(target.rglob("*"), reverse=True):
                        old.rmdir() if old.is_dir() else old.unlink()
                    target.rmdir()
                for suffix in ("-wal", "-shm"):  # stale SQLite side files
                    Path(f"{target}{suffix}").unlink(missing_ok=True)
                source.replace(target)
                restored.append(name)
            env = Path(tmp) / ".env"
            if env_target is not None and env.is_file():
                env.replace(env_target)
                restored.append(".env")
    cookies = data_dir / "cookies.txt"
    if cookies.exists():
        cookies.chmod(0o600)
    return restored
