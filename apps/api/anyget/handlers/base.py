"""The contract every download handler implements.

Adding a new site means adding one file in this package with a class that
satisfies `Handler`, then registering it in `registry.py`.
"""

import shutil
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
    # A short status code the UI translates, e.g. "merging" or "extracting_audio".
    message: str | None = None


class DownloadResult(BaseModel):
    """paths[0] is the main file; more paths are extras (subtitles, info.json).

    An empty list means nothing new was saved; `note` says why (e.g. "already_downloaded").
    """

    paths: list[Path]
    checksum_ok: bool | None = None
    note: str | None = None


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

    Codes: unsupported, upstream, not_found, incomplete, checksum, unsafe_path, and for
    media: drm, members_only, paid, private, age_restricted, login_required, bot_check,
    geo_blocked, live_not_finished, unavailable.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def part_path(output_dir: Path, job_id: str) -> Path:
    """Where a job's partial download lives (stable across restarts, so it can resume)."""
    return output_dir / f".anyget-{job_id}.part"


def work_dir(output_dir: Path, job_id: str) -> Path:
    """A job's private temp folder (yt-dlp fragments and partial files)."""
    return output_dir / f".anyget-{job_id}"


def remove_partials(output_dir: Path, job_id: str) -> None:
    """Delete everything a job left half-done (file or folder)."""
    part_path(output_dir, job_id).unlink(missing_ok=True)
    shutil.rmtree(work_dir(output_dir, job_id), ignore_errors=True)
    # Multi-file jobs (archive.org items) keep their partials inside their own folder.
    for stray in output_dir.glob(f"*/.anyget-{job_id}*"):
        if stray.is_dir():
            shutil.rmtree(stray, ignore_errors=True)
        else:
            stray.unlink(missing_ok=True)


def partial_size(output_dir: Path, job_id: str) -> int | None:
    """Bytes downloaded so far by a paused job, if anything is on disk."""
    part = part_path(output_dir, job_id)
    if part.exists():
        return part.stat().st_size
    folder = work_dir(output_dir, job_id)
    if folder.is_dir():
        return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
    return None


ProgressCallback = Callable[[Progress], None]


@runtime_checkable
class Handler(Protocol):
    name: str

    def can_handle(self, url: str) -> bool:
        """Cheap check; avoid network calls unless unavoidable."""
        ...

    async def probe(self, url: str, options: dict[str, Any] | None = None) -> Probe:
        """Return title, size and choices for the URL (options: e.g. a channel tab)."""
        ...

    async def download(
        self, job: JobRef, options: dict[str, Any], progress_cb: ProgressCallback
    ) -> DownloadResult:
        """Download into job.output_dir, reporting progress through progress_cb."""
        ...
