"""Download several files of one job into a folder, with summed progress.

Used by handlers whose links stand for many files (archive.org items, release
assets, gists, model repos, galleries, links found on a web page). Each file goes
through HttpGenericHandler, so Range resume, checksums and the SSRF guard apply.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from anyget.handlers.base import DownloadResult, JobContext, JobRef, Progress, ProgressCallback
from anyget.handlers.http_generic import HttpGenericHandler


@dataclass(frozen=True)
class RemoteFile:
    url: str
    name: str  # may contain "/" for sub-folders; each part is sanitized
    size: int | None = None
    md5: str | None = None
    sha1: str | None = None
    sha256: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    # Other URLs for the same bytes (e.g. archive.org's second storage server),
    # tried in order when a server can't be reached. The .part file carries over.
    mirrors: tuple[str, ...] = ()


async def download_many(
    http: HttpGenericHandler,
    job: JobRef,
    files: Sequence[RemoteFile],
    folder: Path,
    progress_cb: ProgressCallback,
) -> DownloadResult:
    from anyget.core.filenames import safe_join

    total = sum(f.size or 0 for f in files) or None
    done = 0
    paths: list[Path] = []
    verified = True
    for index, remote in enumerate(files):
        base = done

        def report(progress: Progress, base: int = base) -> None:
            progress_cb(Progress(downloaded=base + progress.downloaded, total=total))

        parts = remote.name.replace("\\", "/").split("/")
        target_dir = safe_join(folder, *parts[:-1]) if len(parts) > 1 else folder
        target_dir.mkdir(parents=True, exist_ok=True)
        options: dict[str, object] = {"filename": parts[-1]}
        for algo in ("md5", "sha1", "sha256"):
            if getattr(remote, algo):
                options[algo] = getattr(remote, algo)
        if remote.headers:
            options["_headers"] = remote.headers
        urls = [remote.url, *remote.mirrors]
        for attempt, url in enumerate(urls):
            sub = JobContext(id=f"{job.id}-{index}", url=url, output_dir=target_dir)
            try:
                result = await http.download(sub, options, report)
                break
            except (httpx.ConnectError, httpx.ConnectTimeout):
                if attempt == len(urls) - 1:
                    raise
        paths.extend(result.paths)
        has_checksum = bool(remote.md5 or remote.sha1 or remote.sha256)
        verified = verified and (not has_checksum or bool(result.checksum_ok))
        done = base + (remote.size or (result.paths[0].stat().st_size if result.paths else 0))
    return DownloadResult(paths=paths, checksum_ok=verified if paths else None)
