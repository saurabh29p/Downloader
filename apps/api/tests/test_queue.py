import asyncio
import errno
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from anyget.core.jobs import JobState
from anyget.core.queue import InvalidStateError
from anyget.core.services import Services
from anyget.core.settings import Settings
from anyget.handlers.base import (
    DownloadResult,
    HandlerError,
    JobRef,
    Probe,
    Progress,
    ProgressCallback,
    part_path,
)


class GateHandler:
    """Fake handler: each download waits for the gate, so tests control timing."""

    name = "gate"

    def __init__(self) -> None:
        self.gate = asyncio.Event()
        self.running = 0
        self.max_running = 0
        self.fail_with: Exception | None = None

    def can_handle(self, url: str) -> bool:
        return "gate.test" in url

    async def probe(self, url: str, options: dict[str, Any] | None = None) -> Probe:
        return Probe(url=url, handler=self.name, title=f"title of {url}", size=3)

    async def download(
        self, job: JobRef, options: dict[str, Any], progress_cb: ProgressCallback
    ) -> DownloadResult:
        self.running += 1
        self.max_running = max(self.max_running, self.running)
        try:
            await self.gate.wait()
            if self.fail_with:
                raise self.fail_with
            job.output_dir.mkdir(parents=True, exist_ok=True)
            path = job.output_dir / f"{job.id}.txt"
            path.write_text("abc")
            progress_cb(Progress(downloaded=3, total=3))
            return DownloadResult(paths=[path], checksum_ok=None)
        finally:
            self.running -= 1


@pytest.fixture
def gate() -> GateHandler:
    return GateHandler()


async def build(settings: Settings, gate: GateHandler) -> Services:
    services = Services.build(settings)
    services.registry.register(gate, 10)
    await services.start()
    return services


async def wait_for(condition: Any, timeout: float = 2.0) -> None:
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(0.01)


@pytest.fixture
async def svc(settings: Settings, gate: GateHandler) -> AsyncIterator[Services]:
    services = await build(settings, gate)
    yield services
    gate.gate.set()
    await services.stop()


async def test_global_limit(settings: Settings, gate: GateHandler) -> None:
    settings.max_concurrent_downloads = 2
    services = await build(settings, gate)
    jobs = [services.queue.submit(f"https://h{i}.gate.test/f") for i in range(5)]
    await wait_for(lambda: gate.running == 2)
    await asyncio.sleep(0.05)
    assert gate.max_running == 2
    gate.gate.set()
    await services.queue.wait_idle()
    assert all(services.store.get(j.id).state == JobState.done for j in jobs)  # type: ignore[union-attr]
    await services.stop()


async def test_per_host_limit(settings: Settings, gate: GateHandler) -> None:
    settings.host_limits = {"gate.test": 1}
    services = await build(settings, gate)
    for i in range(3):
        services.queue.submit(f"https://cdn{i}.gate.test/f")
    await wait_for(lambda: gate.running == 1)
    await asyncio.sleep(0.05)
    assert gate.max_running == 1
    gate.gate.set()
    await services.queue.wait_idle()
    await services.stop()


async def test_done_job_has_file_and_title(svc: Services, gate: GateHandler) -> None:
    gate.gate.set()
    job = svc.queue.submit("https://a.gate.test/f")
    await svc.queue.wait_idle()
    done = svc.store.get(job.id)
    assert done is not None
    assert done.state == JobState.done
    assert done.title == "title of https://a.gate.test/f"
    assert done.handler == "gate"
    assert done.rel_path == f"{job.id}.txt"
    assert done.finished_at is not None


async def test_pause_and_resume(svc: Services, gate: GateHandler) -> None:
    job = svc.queue.submit("https://a.gate.test/f")
    await wait_for(lambda: gate.running == 1)
    paused = await svc.queue.pause(job.id)
    assert paused.state == JobState.paused
    assert gate.running == 0
    with pytest.raises(InvalidStateError):
        await svc.queue.pause(job.id)
    svc.queue.resume(job.id)
    gate.gate.set()
    await svc.queue.wait_idle()
    assert svc.store.get(job.id).state == JobState.done  # type: ignore[union-attr]


async def test_cancel_removes_partial_file(svc: Services, settings: Settings) -> None:
    job = svc.queue.submit("https://a.gate.test/f")
    part = part_path(settings.downloads_dir, job.id)
    part.write_bytes(b"partial")
    canceled = await svc.queue.cancel(job.id)
    assert canceled.state == JobState.canceled
    assert not part.exists()


async def test_handler_error_marks_failed(svc: Services, gate: GateHandler) -> None:
    gate.fail_with = HandlerError("upstream", "the server answered 500")
    gate.gate.set()
    job = svc.queue.submit("https://a.gate.test/f")
    await svc.queue.wait_idle()
    failed = svc.store.get(job.id)
    assert failed is not None
    assert failed.state == JobState.failed
    assert failed.error_code == "upstream"
    gate.fail_with = None
    svc.queue.retry(job.id)
    await svc.queue.wait_idle()
    assert svc.store.get(job.id).state == JobState.done  # type: ignore[union-attr]


async def test_full_disk_has_its_own_error(svc: Services, gate: GateHandler) -> None:
    # Not "something went wrong": say the disk is full, so the user can free space and retry.
    gate.fail_with = OSError(errno.ENOSPC, "No space left on device")
    gate.gate.set()
    job = svc.queue.submit("https://a.gate.test/big")
    await svc.queue.wait_idle()
    failed = svc.store.get(job.id)
    assert failed is not None and failed.error_code == "disk_full"


async def test_blocked_url_fails_cleanly(svc: Services) -> None:
    job = svc.queue.submit("http://127.0.0.1/secret")
    await svc.queue.wait_idle()
    failed = svc.store.get(job.id)
    assert failed is not None
    assert failed.error_code == "blocked_url"


async def test_interrupted_jobs_resume_on_start(settings: Settings, gate: GateHandler) -> None:
    first = Services.build(settings)
    job = first.store.create("https://a.gate.test/f")
    first.store.update(job.id, state=JobState.downloading)
    first.db.dispose()

    gate.gate.set()
    services = await build(settings, gate)
    await services.queue.wait_idle()
    assert services.store.get(job.id).state == JobState.done  # type: ignore[union-attr]
    await services.stop()


async def test_events_are_published(svc: Services, gate: GateHandler) -> None:
    events = svc.bus.subscribe()
    seen: list[str] = []

    async def collect() -> None:
        async for event in events:
            seen.append(f"{event['type']}:{event['job'].get('state')}")
            if event["job"].get("state") == "done":
                return

    collector = asyncio.create_task(collect())
    await asyncio.sleep(0)
    gate.gate.set()
    svc.queue.submit("https://a.gate.test/f")
    await asyncio.wait_for(collector, 2)
    assert seen[0] == "job.created:queued"
    assert "job.updated:probing" in seen
    assert "job.updated:downloading" in seen
    assert seen[-1] == "job.updated:done"


async def test_delete_with_file(svc: Services, gate: GateHandler, settings: Settings) -> None:
    gate.gate.set()
    job = svc.queue.submit("https://a.gate.test/f")
    await svc.queue.wait_idle()
    path: Path = settings.downloads_dir / f"{job.id}.txt"
    assert path.exists()
    await svc.queue.delete(job.id, delete_file=True)
    assert not path.exists()
    assert svc.store.get(job.id) is None
