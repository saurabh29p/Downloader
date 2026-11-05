"""Conversions as jobs: `anyget:convert?job=<id>&to=<target>[&lang=eng+hin]`.

The source is a finished job's files, which are always inside the downloads
folder (checked again here). Targets:
- pdf: page images → one PDF (img2pdf), or EPUB → PDF (Calibre, if installed)
- ocr: a PDF (or page images) → searchable PDF (OCRmyPDF/Tesseract, if installed)
- mp3, m4a, opus, flac, wav, mp4, mkv, webm: audio/video with ffmpeg
"""

from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode

from anyget.convert import ebook, media, ocr
from anyget.convert.pdf import images_to_pdf, is_image
from anyget.core.filenames import UnsafePathError, ensure_inside, unique_path
from anyget.core.jobs import JobState, JobStore
from anyget.core.settings import Settings
from anyget.handlers.base import (
    DownloadResult,
    HandlerError,
    JobRef,
    Probe,
    Progress,
    ProgressCallback,
)

SCHEME = "anyget:convert?"
TARGETS = ("pdf", "ocr", *media.PRESETS)


def convert_url(job_id: str, to: str, lang: str | None = None) -> str:
    query = {"job": job_id, "to": to, **({"lang": lang} if lang else {})}
    return SCHEME + urlencode(query)


def parse(url: str) -> tuple[str, str, str | None]:
    if not url.startswith(SCHEME):
        raise HandlerError("unsupported", "not a conversion link")
    query = parse_qs(url[len(SCHEME) :])
    job_id = (query.get("job") or [""])[0]
    to = (query.get("to") or [""])[0]
    lang = next(iter(query.get("lang") or []), None)
    if not job_id or to not in TARGETS:
        raise HandlerError("unsupported", f"convert to one of: {', '.join(TARGETS)}")
    return job_id, to, lang


class ConvertHandler:
    name = "convert"

    def __init__(self, settings: Settings, store: JobStore) -> None:
        self.settings = settings
        self.store = store

    def can_handle(self, url: str) -> bool:
        return url.startswith(SCHEME)

    def _sources(self, job_id: str) -> list[Path]:
        job = self.store.get(job_id)
        if job is None or job.state != JobState.done or not job.rel_path:
            raise HandlerError("not_found", "convert needs a finished download")
        root = self.settings.downloads_dir.resolve()
        paths = []
        for rel in [job.rel_path, *(job.files or [])]:
            try:
                path = ensure_inside(root, root / rel)
            except UnsafePathError as exc:
                raise HandlerError(
                    "unsafe_path", "that file is outside the downloads folder"
                ) from exc
            if path.is_file():
                paths.append(path)
        if not paths:
            raise HandlerError("not_found", "the downloaded files are gone")
        return paths

    def _plan(self, sources: list[Path], to: str) -> tuple[str, list[Path]]:
        """What will be done and with which inputs; raises if not possible here."""
        images = [p for p in sources if is_image(p)]
        pdfs = [p for p in sources if p.suffix.lower() == ".pdf"]
        epubs = [p for p in sources if p.suffix.lower() == ".epub"]
        if to == "pdf":
            if len(images) >= 1:
                return "images", sorted(images)
            if epubs:
                if not ebook.available():
                    raise HandlerError("tool_missing", "EPUB to PDF needs Calibre (ebook-convert)")
                return "epub", epubs[:1]
            raise HandlerError("unsupported", "only page images or an EPUB can become a PDF")
        if to == "ocr":
            if not ocr.available():
                raise HandlerError("tool_missing", "OCR needs OCRmyPDF and Tesseract")
            if pdfs:
                return "pdf", pdfs[:1]
            if images:
                return "images", sorted(images)
            raise HandlerError("unsupported", "OCR works on a PDF or page images")
        found = [p for p in sources if media.is_media(p)]
        if not found:
            raise HandlerError("unsupported", "that download has no audio or video file")
        return "media", found[:1]

    async def probe(self, url: str, options: dict[str, Any] | None = None) -> Probe:
        job_id, to, _ = parse(url)
        sources = self._sources(job_id)
        kind, inputs = self._plan(sources, to)
        return Probe(
            url=url,
            handler=self.name,
            title=f"{inputs[0].stem} → {to.upper()}",
            extra={"kind": "convert", "to": to, "source": kind, "inputs": len(inputs)},
        )

    async def download(
        self, job: JobRef, options: dict[str, Any], progress_cb: ProgressCallback
    ) -> DownloadResult:
        job_id, to, lang = parse(job.url)
        kind, inputs = self._plan(self._sources(job_id), to)
        first = inputs[0]
        root = self.settings.downloads_dir.resolve()
        # Many page images in their own folder → "<folder>.pdf" next to that folder.
        grouped = kind == "images" and len(inputs) > 1 and first.parent != root
        folder = first.parent.parent if grouped else first.parent
        name = first.parent.name if grouped else first.stem
        progress_cb(Progress(downloaded=0, total=None))
        if to == "pdf":
            target = unique_path(folder / f"{name}.pdf")
            if kind == "images":
                images_to_pdf(inputs, target)
            else:
                await ebook.epub_to_pdf(first, target)
        elif to == "ocr":
            target = unique_path(folder / f"{name} (OCR).pdf")
            source = first
            if kind == "images":
                source = images_to_pdf(inputs, unique_path(folder / f"{name}.pdf"))
            await ocr.ocr_pdf(source, target, lang)
        else:
            target = unique_path(folder / f"{first.stem}.{to}")
            await media.convert(first, target, to)
        size = target.stat().st_size
        progress_cb(Progress(downloaded=size, total=size))
        sidecar = target.with_suffix(".txt")
        return DownloadResult(paths=[target, *([sidecar] if sidecar.exists() else [])])
