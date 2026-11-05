"""Run watches: list a source's items, queue the ones not seen before.

- media (yt-dlp channels and playlists): the probe lists entries newest first; items
  already in the per-source download archive count as seen.
- archive_collection: archive.org's scrape API sorted by publish date (newest first).

The first run queues the `initial` newest items and marks the rest as seen, so
watching a big channel does not download its whole history.
"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import col, select

from anyget.core.db import Database
from anyget.core.net import Net
from anyget.core.queue import DownloadQueue
from anyget.core.router import Router
from anyget.handlers.archive_org import ArchiveOrgHandler, parse_item_url, scrape
from anyget.handlers.base import HandlerError
from anyget.watch.models import Watch, WatchIn, WatchOut, WatchRunResult

log = logging.getLogger("anyget.watch")

MAX_LIST = 200  # items looked at per run
MAX_QUEUE = 50  # items queued per run; the rest wait for the next run
SEEN_KEEP = 5000


@dataclass(frozen=True)
class Entry:
    id: str
    url: str
    options: dict[str, Any]
    saved: bool = False


def _aware(when: datetime | None) -> datetime | None:
    return when.replace(tzinfo=UTC) if when is not None and when.tzinfo is None else when


def out(watch: Watch) -> WatchOut:
    last = _aware(watch.last_run)
    return WatchOut(
        id=watch.id,
        url=watch.url,
        kind=watch.kind if watch.kind == "media" else "archive_collection",
        title=watch.title,
        interval_minutes=watch.interval_minutes,
        enabled=watch.enabled,
        initial=watch.initial,
        seen=len(watch.seen_ids or []),
        last_run=last,
        last_new=watch.last_new,
        last_error=watch.last_error,
        next_run=(last + timedelta(minutes=watch.interval_minutes)) if last else None,
        created_at=_aware(watch.created_at) or watch.created_at,
    )


class WatchService:
    def __init__(self, db: Database, net: Net, router: Router, queue: DownloadQueue) -> None:
        self.db = db
        self.net = net
        self.router = router
        self.queue = queue
        self._lock = asyncio.Lock()

    # ----- storage ---------------------------------------------------------

    def all(self) -> list[Watch]:
        with self.db.session() as session:
            return list(session.exec(select(Watch).order_by(col(Watch.created_at))).all())

    def get(self, watch_id: str) -> Watch | None:
        with self.db.session() as session:
            return session.get(Watch, watch_id)

    def _save(self, watch: Watch) -> Watch:
        with self.db.session() as session:
            session.add(watch)
            session.commit()
            session.refresh(watch)
            return watch

    def delete(self, watch_id: str) -> bool:
        with self.db.session() as session:
            watch = session.get(Watch, watch_id)
            if watch is None:
                return False
            session.delete(watch)
            session.commit()
            return True

    def update(self, watch_id: str, **changes: Any) -> Watch | None:
        watch = self.get(watch_id)
        if watch is None:
            return None
        for key, value in changes.items():
            if value is not None:
                setattr(watch, key, value)
        return self._save(watch)

    # ----- sources ---------------------------------------------------------

    async def create(self, body: WatchIn) -> Watch:
        url, handler = await self.router.resolve(body.url)
        if handler.name == "archive_org" and isinstance(handler, ArchiveOrgHandler):
            identifier, _ = parse_item_url(url)
            item = await handler.item(identifier)
            if item.mediatype != "collection":
                raise HandlerError("unsupported", "watch an archive.org collection, not one item")
            kind, title = "archive_collection", item.title
        else:
            # Media handlers (yt-dlp) describe channels and playlists with entries.
            probe = await handler.probe(url, {"max_entries": 5})
            if probe.extra.get("kind") not in ("playlist", "channel"):
                raise HandlerError(
                    "unsupported",
                    "watches work with channels, playlists and archive.org collections",
                )
            kind, title = "media", probe.title
        watch = Watch(
            url=url,
            kind=kind,
            title=title,
            interval_minutes=body.interval_minutes,
            initial=body.initial,
            options={k: v for k, v in body.options.items() if not str(k).startswith("_")},
        )
        return self._save(watch)

    async def _entries(self, watch: Watch) -> list[Entry]:
        if watch.kind == "archive_collection":
            identifier, _ = parse_item_url(watch.url)
            page = await scrape(
                self.net,
                f'collection:"{identifier}"',
                count=MAX_LIST,
                sorts="publicdate desc",
            )
            return [
                Entry(
                    id=hit.identifier,
                    url=f"https://archive.org/details/{hit.identifier}",
                    options={},
                )
                for hit in page.items[:MAX_LIST]
            ]
        _, handler = await self.router.resolve(watch.url)
        probe = await handler.probe(watch.url, {"max_entries": MAX_LIST})
        extra = probe.extra
        folder = probe.title
        entries = []
        for entry in extra.get("entries") or []:
            if entry.get("live"):
                continue  # unfinished streams: try again on a later run
            entries.append(
                Entry(
                    id=str(entry["archive_id"]),
                    url=str(entry["url"]),
                    options={
                        "folder": folder,
                        "index": entry["index"],
                        "archive": extra.get("archive"),
                        "archive_id": entry["archive_id"],
                    },
                    saved=bool(entry.get("saved")),
                )
            )
        return entries

    # ----- running ---------------------------------------------------------

    async def run(self, watch_id: str) -> WatchRunResult:
        async with self._lock:  # one run at a time keeps "seen" consistent
            watch = self.get(watch_id)
            if watch is None:
                raise HandlerError("not_found", "no such watch")
            first_run = watch.last_run is None
            seen = set(watch.seen_ids or [])
            job_ids: list[str] = []
            try:
                entries = await self._entries(watch)
            except Exception as exc:  # stored on the watch for the UI, then re-raised
                watch.last_run = datetime.now(UTC)
                watch.last_new = 0
                watch.last_error = str(exc)[:300] or type(exc).__name__
                self._save(watch)
                raise
            new = [e for e in entries if e.id not in seen and not e.saved]
            seen.update(e.id for e in entries if e.saved)
            to_queue = new[: watch.initial] if first_run else new[:MAX_QUEUE]
            for entry in to_queue:
                job = self.queue.submit(entry.url, {**watch.options, **entry.options})
                job_ids.append(job.id)
                seen.add(entry.id)
            if first_run:
                seen.update(e.id for e in new)  # older items are history, not news
            watch.seen_ids = list(seen)[-SEEN_KEEP:]
            watch.last_run = datetime.now(UTC)
            watch.last_new = len(job_ids)
            watch.last_error = None
            watch = self._save(watch)
            log.info("watch %s queued %d new item(s)", watch.id, len(job_ids))
            return WatchRunResult(watch=out(watch), queued=len(job_ids), job_ids=job_ids)

    def due(self, now: datetime | None = None) -> list[Watch]:
        now = now or datetime.now(UTC)
        due = []
        for watch in self.all():
            last = _aware(watch.last_run)
            if watch.enabled and (
                last is None or last + timedelta(minutes=watch.interval_minutes) <= now
            ):
                due.append(watch)
        return due


class WatchScheduler:
    """Checks every minute for watches that are due and runs them one by one."""

    def __init__(self, service: WatchService, tick_seconds: float = 60.0) -> None:
        self.service = service
        self.tick_seconds = tick_seconds
        self._task: asyncio.Task[None] | None = None

    async def tick(self, now: datetime | None = None) -> int:
        ran = 0
        for watch in self.service.due(now):
            try:
                await self.service.run(watch.id)
            except Exception as exc:  # saved on the watch; keep going with the others
                log.info("watch %s failed: %s", watch.id, exc)
            ran += 1
        return ran

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self.tick_seconds)
            await self.tick()

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="anyget-watch")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
