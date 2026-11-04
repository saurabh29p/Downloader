"""The contract every download handler implements.

Adding a new site means adding one file in this package with a class that
satisfies `Handler`, then registering it in `registry.py`.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class Choice(BaseModel):
    """One thing the user can pick after a probe: a format, a file or a playlist item."""

    id: str
    label: str
    kind: str = Field(description="e.g. video, audio, subtitle, file, item")
    size: int | None = None
    ext: str | None = None
    default: bool = False


class Probe(BaseModel):
    """What a handler learns about a URL before downloading."""

    url: str
    handler: str
    title: str
    size: int | None = None
    thumbnail: str | None = None
    choices: list[Choice] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class Progress(BaseModel):
    downloaded: int = 0
    total: int | None = None
    speed: float | None = None
    message: str | None = None


class DownloadResult(BaseModel):
    paths: list[Path]
    checksum_ok: bool | None = None


class JobRef(Protocol):
    """The minimal view of a job a handler needs."""

    @property
    def id(self) -> str: ...

    @property
    def url(self) -> str: ...

    @property
    def output_dir(self) -> Path: ...


@dataclass(frozen=True)
class JobContext:
    """Concrete JobRef the queue hands to handlers."""

    id: str
    url: str
    output_dir: Path


class HandlerError(Exception):
    """A problem the user should see, with a stable code for the UI.

    Codes: unsupported, upstream, not_found, incomplete, checksum, unsafe_path.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def part_path(output_dir: Path, job_id: str) -> Path:
    """Where a job's partial download lives (stable across restarts, so it can resume)."""
    return output_dir / f".anyget-{job_id}.part"


ProgressCallback = Callable[[Progress], None]


@runtime_checkable
class Handler(Protocol):
    name: str

    def can_handle(self, url: str) -> bool:
        """Cheap check; avoid network calls unless unavoidable."""
        ...

    async def probe(self, url: str) -> Probe:
        """Return title, size and choices for the URL."""
        ...

    async def download(
        self, job: JobRef, options: dict[str, Any], progress_cb: ProgressCallback
    ) -> DownloadResult:
        """Download into job.output_dir, reporting progress through progress_cb."""
        ...
