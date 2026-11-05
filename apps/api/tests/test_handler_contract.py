from pathlib import Path
from typing import Any

from anyget.handlers.base import DownloadResult, Handler, JobRef, Probe, ProgressCallback


class DummyHandler:
    name = "dummy"

    def can_handle(self, url: str) -> bool:
        return url.startswith("dummy:")

    async def probe(self, url: str, options: dict[str, Any] | None = None) -> Probe:
        return Probe(url=url, handler=self.name, title="Dummy")

    async def download(
        self, job: JobRef, options: dict[str, Any], progress_cb: ProgressCallback
    ) -> DownloadResult:
        return DownloadResult(paths=[Path(job.output_dir) / "dummy.bin"])


def test_dummy_satisfies_protocol() -> None:
    handler = DummyHandler()
    assert isinstance(handler, Handler)
    assert handler.can_handle("dummy:x")


async def test_probe_model() -> None:
    probe = await DummyHandler().probe("dummy:x")
    assert probe.title == "Dummy"
    assert probe.choices == []
