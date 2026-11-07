"""Retention: remove downloaded files older than N days (default 7; 0 = off).

Safety rules (each has a test):
- Only files AnyGet indexed in its library are considered (managed storage). Files
  copied in by hand count only after a library scan indexed them.
- Age is when AnyGet saved the file (`added_at`), not the file's own date: yt-dlp
  sets a video's file date to its upload date.
- Never: files of active jobs (queued, probing, downloading, paused), items tagged
  "keep", symlinks or paths through a symlinked folder, anything outside the
  downloads folder. If the downloads and data folders overlap, nothing runs.
- Grace period: the first removals happen N days after retention was switched on,
  so turning it on (or upgrading) never deletes existing files at once.
- The library entry stays ("removed", with Download again); the download row gets
  the note "expired".
"""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel
from sqlmodel import col, select

from anyget.core.db import Database
from anyget.core.filenames import UnsafePathError, ensure_inside
from anyget.core.jobs import Job, JobState
from anyget.core.settings import Settings
from anyget.core.settings_store import SettingsStore
from anyget.library.index import LibraryIndex
from anyget.library.models import LibraryItem
from anyget.library.thumbs import forget

log = logging.getLogger("anyget.retention")

KEEP_TAG = "keep"
ACTIVE = (JobState.queued, JobState.probing, JobState.downloading, JobState.paused)
SINCE = "retention_since"
LAST = "retention_last_run"


class RetentionStatus(BaseModel):
    days: int
    enabled: bool
    # When removals can start (end of the grace period), if retention is on.
    starts_at: datetime | None
    last_run: datetime | None
    # Why cleanup can't run at all (e.g. the folders overlap), if so.
    blocked: str | None = None


class CleanupResult(BaseModel):
    dry_run: bool
    enabled: bool
    days: int
    cutoff: datetime | None
    starts_at: datetime | None
    removed: list[str]
    freed_bytes: int
    skipped_active: int
    skipped_kept: int
    skipped_unsafe: int
    blocked: str | None = None


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _overlap(a: Path, b: Path) -> bool:
    a, b = a.resolve(), b.resolve()
    return a == b or a in b.parents or b in a.parents


def _through_symlink(root: Path, path: Path) -> bool:
    """True if the path, or any folder between the downloads root and it, is a symlink."""
    current = path
    while current != root and root in current.parents:
        if current.is_symlink():
            return True
        current = current.parent
    return False


class Retention:
    def __init__(
        self,
        db: Database,
        settings: Settings,
        store: SettingsStore,
        library: LibraryIndex,
    ) -> None:
        self.db = db
        self.settings = settings
        self.store = store
        self.library = library

    def _blocked(self) -> str | None:
        if _overlap(self.settings.downloads_dir, self.settings.data_dir):
            return "folders_overlap"
        return None

    def _since(self, now: datetime, write: bool) -> datetime:
        raw = self.store.get_state(SINCE)
        if raw:
            with contextlib.suppress(ValueError):
                return _utc(datetime.fromisoformat(raw))
        if write:
            self.store.set_state(SINCE, now.isoformat())
        return now

    def status(self, now: datetime | None = None) -> RetentionStatus:
        now = now or datetime.now(UTC)
        days = self.settings.retention_days
        last = self.store.get_state(LAST)
        return RetentionStatus(
            days=days,
            enabled=days > 0,
            starts_at=self._since(now, write=False) + timedelta(days=days) if days > 0 else None,
            last_run=_utc(datetime.fromisoformat(last)) if last else None,
            blocked=self._blocked(),
        )

    def run(self, now: datetime | None = None, dry_run: bool = False) -> CleanupResult:
        now = now or datetime.now(UTC)
        days = self.settings.retention_days
        result = CleanupResult(
            dry_run=dry_run,
            enabled=days > 0,
            days=days,
            cutoff=None,
            starts_at=None,
            removed=[],
            freed_bytes=0,
            skipped_active=0,
            skipped_kept=0,
            skipped_unsafe=0,
            blocked=self._blocked(),
        )
        if days <= 0:
            if not dry_run:
                self.store.set_state(SINCE, None)  # switching it on later restarts the grace
            return result
        if result.blocked:
            log.warning("retention cleanup skipped: downloads and data folders overlap")
            return result
        since = self._since(now, write=not dry_run)
        result.starts_at = since + timedelta(days=days)
        result.cutoff = now - timedelta(days=days)
        if now < result.starts_at:
            return result  # grace period
        root = self.settings.downloads_dir.resolve()
        with self.db.session() as session:
            active_jobs = list(session.exec(select(Job).where(col(Job.state).in_(ACTIVE))).all())
            candidates = list(
                session.exec(select(LibraryItem).where(col(LibraryItem.expired_at).is_(None))).all()
            )
        active_ids = {job.id for job in active_jobs}
        # Folders that active jobs write into (folder templates, multi-file items).
        active_dirs = {
            str((job.options or {}).get("_folder") or "").strip("/")
            for job in active_jobs
            if (job.options or {}).get("_folder")
        }
        for item in candidates:
            if _utc(item.added_at) >= result.cutoff:
                continue
            if KEEP_TAG in (item.tags or []):
                result.skipped_kept += 1
                continue
            if item.job_id in active_ids or any(
                item.rel_path == d or item.rel_path.startswith(f"{d}/") for d in active_dirs
            ):
                result.skipped_active += 1
                continue
            path = root / item.rel_path
            try:
                if _through_symlink(root, path):
                    raise UnsafePathError("symlink")
                ensure_inside(root, path)
            except UnsafePathError:
                result.skipped_unsafe += 1
                continue
            if not path.is_file():
                if not dry_run:
                    self._mark(item, now)  # already gone: mark it like a removal
                continue
            size = path.stat().st_size
            if not dry_run:
                try:
                    path.unlink()
                except OSError as exc:
                    log.info("could not remove %s: %s", item.rel_path, type(exc).__name__)
                    continue
                forget(self.settings.data_dir, item.id)
                self.library.text.drop(item.id)
                self._mark(item, now)
            result.removed.append(item.rel_path)
            result.freed_bytes += size
        if not dry_run:
            self.store.set_state(LAST, now.isoformat())
            if result.removed:
                log.info(
                    "retention removed %d files (%d bytes) older than %d days",
                    len(result.removed),
                    result.freed_bytes,
                    days,
                )
        return result

    def _mark(self, item: LibraryItem, now: datetime) -> None:
        with self.db.session() as session:
            row = session.get(LibraryItem, item.id)
            if row is not None:
                row.expired_at = now
                session.add(row)
            if item.job_id:
                job = session.get(Job, item.job_id)
                if job is not None and job.rel_path == item.rel_path:
                    job.note = "expired"
                    session.add(job)
            session.commit()


class RetentionScheduler:
    """Runs cleanup once a day in the API server (first run 10 minutes after start)."""

    def __init__(
        self, retention: Retention, first_delay: float = 600.0, every: float = 86_400.0
    ) -> None:
        self.retention = retention
        self.first_delay = first_delay
        self.every = every
        self._task: asyncio.Task[None] | None = None

    async def _loop(self) -> None:
        await asyncio.sleep(self.first_delay)
        while True:
            try:
                await asyncio.to_thread(self.retention.run)
            except Exception as exc:
                log.warning("retention cleanup failed: %s", type(exc).__name__)
            await asyncio.sleep(self.every)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="anyget-retention")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
