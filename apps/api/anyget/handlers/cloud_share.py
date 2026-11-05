"""Public cloud-share links: Google Drive/Docs, Dropbox, OneDrive, MEGA.

Share pages are rewritten to their direct-download form and fetched with the
normal HTTP path (resume, SSRF guard). Private files, Drive folders and quota
pages give a clear reason. MEGA files are end-to-end encrypted, so they need
the `megadl` tool (megatools) when it is installed; otherwise we say so.
"""

import asyncio
import base64
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from anyget.core.filenames import ensure_inside, safe_join
from anyget.core.net import Net
from anyget.handlers.base import (
    DownloadResult,
    HandlerError,
    JobContext,
    JobRef,
    Probe,
    ProgressCallback,
    work_dir,
)
from anyget.handlers.http_generic import HttpGenericHandler

_DRIVE_ID = re.compile(
    r"/(?:file/d|document/d|spreadsheets/d|presentation/d|drawings/d)/([\w-]{10,})"
)
DOC_EXPORTS = {
    "document": "pdf",
    "spreadsheets": "xlsx",
    "presentation": "pdf",
    "drawings": "pdf",
}


def provider(url: str) -> str | None:
    host = (urlsplit(url).hostname or "").lower()
    if host in ("drive.google.com", "docs.google.com", "drive.usercontent.google.com"):
        return "gdrive"
    if host in ("www.dropbox.com", "dropbox.com", "dl.dropboxusercontent.com"):
        return "dropbox"
    if host in ("onedrive.live.com", "1drv.ms", "api.onedrive.com") or host.endswith(
        ".sharepoint.com"
    ):
        return "onedrive"
    if host in ("mega.nz", "mega.io", "mega.co.nz"):
        return "mega"
    return None


def drive_direct(url: str) -> str:
    """Drive file or Docs link → a direct download URL (Docs are exported)."""
    parts = urlsplit(url)
    if "/drive/folders/" in parts.path or "/folderview" in parts.path:
        raise HandlerError(
            "unsupported", "Google Drive folders need the Drive API; share single files instead"
        )
    host = (parts.hostname or "").lower()
    match = _DRIVE_ID.search(parts.path)
    if host == "docs.google.com" and match:
        kind = parts.path.split("/")[1]
        fmt = DOC_EXPORTS.get(kind, "pdf")
        return f"https://docs.google.com/{kind}/d/{match.group(1)}/export?format={fmt}"
    file_id = match.group(1) if match else (parse_qs(parts.query).get("id") or [""])[0]
    if not re.fullmatch(r"[\w-]{10,}", file_id):
        raise HandlerError("unsupported", "could not find the file id in this Drive link")
    # confirm=t skips the "can't scan for viruses" page for large files.
    return "https://drive.usercontent.google.com/download?" + urlencode(
        {"id": file_id, "export": "download", "confirm": "t"}
    )


def dropbox_direct(url: str) -> str:
    parts = urlsplit(url)
    query = {k: v for k, v in parse_qs(parts.query).items() if k != "dl"}
    query["dl"] = ["1"]
    return urlunsplit(("https", "www.dropbox.com", parts.path, urlencode(query, doseq=True), ""))


def onedrive_direct(url: str) -> str:
    """Any public OneDrive/SharePoint share link → the shares API content URL."""
    token = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
    return f"https://api.onedrive.com/v1.0/shares/u!{token}/root/content"


def direct_url(url: str) -> str:
    kind = provider(url)
    if kind == "gdrive":
        return drive_direct(url)
    if kind == "dropbox":
        return dropbox_direct(url)
    if kind == "onedrive":
        return onedrive_direct(url)
    raise HandlerError("unsupported", "not a supported cloud-share link")


class CloudShareHandler:
    name = "cloud_share"

    def __init__(self, net: Net) -> None:
        self.http = HttpGenericHandler(net)

    def can_handle(self, url: str) -> bool:
        return provider(url) is not None

    async def probe(self, url: str, options: dict[str, Any] | None = None) -> Probe:
        if provider(url) == "mega":
            if not shutil.which("megadl"):
                raise HandlerError(
                    "unsupported", "MEGA links need megatools (megadl), which is not installed"
                )
            return Probe(url=url, handler=self.name, title="MEGA file", extra={"kind": "mega"})
        direct = direct_url(url)
        try:
            probe = await self.http.probe(direct)
        except HandlerError as exc:
            if exc.code == "unsupported":  # got an HTML page instead of the file
                raise HandlerError(
                    "login_required",
                    "the share link opened a sign-in or quota page; check that it is public",
                ) from exc
            raise
        return Probe(
            url=url,
            handler=self.name,
            title=probe.title,
            size=probe.size,
            choices=probe.choices,
            extra={
                **probe.extra,
                "kind": "cloud_file",
                "provider": provider(url),
                "direct": direct,
            },
        )

    async def download(
        self, job: JobRef, options: dict[str, Any], progress_cb: ProgressCallback
    ) -> DownloadResult:
        if provider(job.url) == "mega":
            return await self._mega(job)
        direct = direct_url(job.url)
        probe = options.get("probe") or {}
        inner = JobContext(id=job.id, url=direct, output_dir=job.output_dir)
        inner_options: dict[str, Any] = {}
        if probe.get("extra", {}).get("direct") == direct:
            inner_options["probe"] = {**probe, "url": direct}
        return await self.http.download(inner, inner_options, progress_cb)

    async def _mega(self, job: JobRef) -> DownloadResult:
        exe = shutil.which("megadl")
        if exe is None:
            raise HandlerError("unsupported", "MEGA links need megatools (megadl)")
        temp = work_dir(job.output_dir, job.id)
        temp.mkdir(parents=True, exist_ok=True)
        process = await asyncio.create_subprocess_exec(
            exe,
            "--no-progress",
            "--path",
            str(temp),
            job.url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise HandlerError(
                "upstream", stderr.decode(errors="replace").strip()[:300] or "megadl failed"
            )
        paths: list[Path] = []
        for item in sorted(temp.iterdir()):
            final = safe_join(job.output_dir, item.name)
            item.rename(final)
            paths.append(ensure_inside(job.output_dir, final))
        shutil.rmtree(temp, ignore_errors=True)
        if not paths:
            raise HandlerError("upstream", "megadl saved no files")
        return DownloadResult(paths=paths)
