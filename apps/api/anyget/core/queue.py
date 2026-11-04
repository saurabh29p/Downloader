"""The download queue: runs jobs with a global and a per-host concurrency limit."""

import asyncio
import contextlib
import logging
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

import httpx

from anyget.core.events import EventBus
from anyget.core.filenames import UnsafePathError, ensure_inside
from anyget.core.jobs import ACTIVE_STATES, Job, JobOut, JobState, JobStore
from anyget.core.net import BlockedURLError, HostLimiter
from anyget.core.router import Router
from anyget.core.settings import Settings
from anyget.handlers.base import (
    HandlerError,
    JobContext,
    Progress,
    partial_size,
    remove_partials,
)

log = logging.getLogger(__name__)

PUBLISH_INTERVAL = 0.25
DB_INTERVAL = 1.0


class JobNotFoundError(KeyError):
    """No job with this id."""


class InvalidStateError(Exception):
    """The action does not fit the job's current state (e.g. pausing a finished job)."""


class DownloadQueue:
    def __init__(self, settings: Settings, store: JobStore, bus: EventBus, router: Router) -> None:
        self.settings = settings
        self.store = store
        self.bus = bus
        self.router = router
        self.output_dir = settings.downloads_dir
        self._global = asyncio.Semaphore(settings.max_concurrent_downloads)
        self._hosts = HostLimiter(settings.max_per_host, settings.host_limits)
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._stop_as: dict[str, JobState] = {}

    # ----- lifecycle -------------------------------------------------------

    async def start(self, recover: bool = True) -> None:
        """Recover jobs interrupted by a restart and schedule everything queued."""
        if not recover:
            return
        self.store.reset_interrupted()
        for job in reversed(self.store.list_jobs({JobState.queued}, limit=10_000)):
            self.schedule(job.id)

    async def stop(self) -> None:
        """Stop running tasks; their jobs are resumed on the next start."""
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def wait_idle(self) -> None:
        while self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)

    # ----- actions ---------------------------------------------------------

    def submit(self, url: str, options: dict[str, Any] | None = None) -> Job:
        job = self.store.create(url, options)
        self._publish("job.created", job)
        self.schedule(job.id)
        return job

    async def pause(self, job_id: str) -> Job:
        job = self._require(job_id)
        if job.state not in ACTIVE_STATES:
            raise InvalidStateError(f"cannot pause a {job.state} job")
        return await self._halt(job_id, JobState.paused)

    async def cancel(self, job_id: str) -> Job:
        job = self._require(job_id)
        if job.state not in (*ACTIVE_STATES, JobState.paused, JobState.failed):
            raise InvalidStateError(f"cannot cancel a {job.state} job")
        job = await self._halt(job_id, JobState.canceled)
        remove_partials(self.output_dir, job_id)
        return job

    def resume(self, job_id: str) -> Job:
        job = self._require(job_id)
        if job.state not in (JobState.paused, JobState.failed, JobState.canceled):
            raise InvalidStateError(f"cannot resume a {job.state} job")
        updated = self.store.update(
            job_id, state=JobState.queued, error=None, error_code=None, speed=None
        )
        if updated is None:
            raise JobNotFoundError(job_id)
        self._publish("job.updated", updated)
        self.schedule(job_id)
        return updated

    retry = resume

    async def delete(self, job_id: str, delete_file: bool = False) -> None:
        job = self._require(job_id)
        if job_id in self._tasks:
            await self._halt(job_id, JobState.canceled)
        remove_partials(self.output_dir, job_id)
        if delete_file:
            for rel in [job.rel_path, *(job.files or [])]:
                if rel:
                    with contextlib.suppress(UnsafePathError, FileNotFoundError):
                        ensure_inside(self.output_dir, self.output_dir / rel).unlink()
        self.store.delete(job_id)
        self.bus.publish({"type": "job.deleted", "job": {"id": job_id}})

    # ----- internals -------------------------------------------------------

    def _require(self, job_id: str) -> Job:
        job = self.store.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    def _publish(self, event_type: str, job: Job) -> None:
        self.bus.publish(
            {"type": event_type, "job": JobOut.model_validate(job).model_dump(mode="json")}
        )

    def _update(self, job_id: str, **changes: Any) -> Job:
        job = self.store.update(job_id, **changes)
        if job is None:
            raise JobNotFoundError(job_id)
        self._publish("job.updated", job)
        return job

    def schedule(self, job_id: str) -> None:
        if job_id in self._tasks:
            return
        task = asyncio.create_task(self._run(job_id), name=f"job-{job_id}")
        self._tasks[job_id] = task
        task.add_done_callback(lambda _t: self._tasks.pop(job_id, None))

    async def _halt(self, job_id: str, state: JobState) -> Job:
        task = self._tasks.get(job_id)
        if task is not None:
            self._stop_as[job_id] = state
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._stop_as.pop(job_id, None)
        changes: dict[str, Any] = {"state": state, "speed": None}
        size = partial_size(self.output_dir, job_id)
        if size is not None:
            changes["downloaded"] = size
        return self._update(job_id, **changes)

    async def _run(self, job_id: str) -> None:
        job = self.store.get(job_id)
        if job is None:
            return
        host = urlsplit(job.url).hostname or ""
        try:
            async with self._hosts.semaphore(host), self._global:
                await self._download(job)
        except asyncio.CancelledError:
            if job_id not in self._stop_as:  # shutdown: leave it to be resumed
                with contextlib.suppress(Exception):
                    self.store.update(job_id, state=JobState.queued, speed=None)
            raise
        except BlockedURLError as exc:
            self._update(job_id, state=JobState.failed, error=str(exc), error_code="blocked_url")
        except HandlerError as exc:
            self._update(job_id, state=JobState.failed, error=exc.message, error_code=exc.code)
        except UnsafePathError as exc:
            self._update(job_id, state=JobState.failed, error=str(exc), error_code="unsafe_path")
        except httpx.HTTPError as exc:
            message = f"network error: {exc}" if str(exc) else "network error"
            self._update(job_id, state=JobState.failed, error=message, error_code="network")
        except Exception as exc:  # never let one job crash the queue
            log.exception("job %s crashed", job_id)
            self._update(job_id, state=JobState.failed, error=str(exc), error_code="internal")

    async def _download(self, job: Job) -> None:
        self._update(job.id, state=JobState.probing, error=None, error_code=None, note=None)
        url, handler = await self.router.resolve(job.url)
        probe = await handler.probe(url)
        job = self._update(
            job.id,
            state=JobState.downloading,
            handler=handler.name,
            title=job.title or probe.title,
            filename=probe.extra.get("filename") or job.filename,
            total=probe.size,
        )

        tracker = _ProgressTracker(self, job)
        context = JobContext(id=job.id, url=url, output_dir=self.output_dir)
        options = {**job.options, "probe": probe.model_dump(mode="json")}
        result = await handler.download(context, options, tracker)

        if not result.paths:  # nothing new saved, e.g. already in the download archive
            self._update(job.id, state=JobState.done, speed=None, note=result.note)
            return
        root = self.output_dir.resolve()
        final = result.paths[0]
        size = final.stat().st_size
        self._update(
            job.id,
            state=JobState.done,
            rel_path=final.relative_to(root).as_posix(),
            files=[p.relative_to(root).as_posix() for p in result.paths[1:]] or None,
            filename=final.name,
            downloaded=size,
            total=size,
            speed=None,
            checksum_ok=result.checksum_ok,
            note=result.note,
        )


class _ProgressTracker:
    """Progress callback: computes speed, throttles events and database writes."""

    def __init__(self, queue: DownloadQueue, job: Job) -> None:
        self.queue = queue
        self.job = job
        self._last_publish = 0.0
        self._last_db = 0.0
        self._window: list[tuple[float, int]] = []

    def __call__(self, progress: Progress) -> None:
        now = time.monotonic()
        self._window.append((now, progress.downloaded))
        self._window = [(t, b) for t, b in self._window if now - t <= 3.0]
        first_t, first_b = self._window[0]
        speed = (progress.downloaded - first_b) / (now - first_t) if now > first_t else None

        self.job.downloaded = progress.downloaded
        if progress.message is not None:
            self.job.note = progress.message
        self.job.total = progress.total if progress.total is not None else self.job.total
        self.job.speed = speed
        # Fresh timestamp so clients never mistake live progress for a stale copy.
        self.job.updated_at = datetime.now(UTC)
        if now - self._last_publish >= PUBLISH_INTERVAL:
            self._last_publish = now
            self.queue._publish("job.updated", self.job)
        if now - self._last_db >= DB_INTERVAL:
            self._last_db = now
            self.queue.store.update(
                self.job.id,
                downloaded=self.job.downloaded,
                total=self.job.total,
                speed=speed,
                note=self.job.note,
            )
