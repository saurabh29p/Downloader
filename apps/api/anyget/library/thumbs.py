"""Library thumbnails: 320 px WebP images, made the first time the Library asks.

- video: a representative frame (ffmpeg's `thumbnail` filter, a few seconds in)
- audio: the embedded cover art (ffmpeg)
- PDF: the first page (poppler's pdftoppm)
- image: the picture, resized (Pillow)

Thumbnails live in data/thumbs/<item id>.webp. A file that can't be pictured gets a
`.none` marker so it isn't tried again. ffmpeg and pdftoppm only read the local file
(it is inside the downloads folder); they never fetch anything.
"""

import asyncio
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, UnidentifiedImageError

log = logging.getLogger("anyget.thumbs")

SIZE = 320
TIMEOUT = 30.0
KINDS = frozenset({"video", "audio", "pdf", "image"})
# Raster formats Pillow reads; SVG is shown by the browser itself.
PILLOW_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".avif")

_limit = asyncio.Semaphore(2)  # thumbnails are made two at a time


def _save(image: Image.Image, out: Path) -> None:
    image.thumbnail((SIZE, SIZE))
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    image.save(tmp, "WEBP", quality=80)
    tmp.replace(out)


def _from_image_file(source: Path, out: Path) -> bool:
    try:
        with Image.open(source) as image:
            image.seek(0)
            _save(image.copy(), out)
        return True
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return False


def _run(args: list[str]) -> bool:
    try:
        done = subprocess.run(  # noqa: S603 - fixed tool, local paths only
            args, capture_output=True, timeout=TIMEOUT, check=False, stdin=subprocess.DEVNULL
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


def _ffmpeg_frame(source: Path, out: Path, *, audio: bool) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return False
    with tempfile.TemporaryDirectory() as tmp:
        frame = Path(tmp) / "frame.png"
        base = [ffmpeg, "-nostdin", "-v", "error", "-protocol_whitelist", "file", "-y"]
        if audio:  # the cover art is the file's attached picture stream
            attempts = [[*base, "-i", str(source), "-map", "0:v:0", "-frames:v", "1", str(frame)]]
        else:
            pick = ["-vf", "thumbnail=60", "-frames:v", "1", str(frame)]
            attempts = [
                [*base, "-ss", "3", "-i", str(source), *pick],
                [*base, "-i", str(source), *pick],  # shorter than 3 seconds
            ]
        for args in attempts:
            if _run(args) and frame.is_file() and frame.stat().st_size:
                return _from_image_file(frame, out)
    return False


def _pdf_page(source: Path, out: Path) -> bool:
    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm is None:
        return False
    with tempfile.TemporaryDirectory() as tmp:
        prefix = Path(tmp) / "page"
        args = [pdftoppm, "-f", "1", "-l", "1", "-singlefile", "-scale-to", str(SIZE * 2)]
        if not _run([*args, "-png", str(source), str(prefix)]):
            return False
        page = prefix.with_suffix(".png")
        return page.is_file() and _from_image_file(page, out)


def make_thumbnail(source: Path, kind: str, out: Path) -> bool:
    if kind == "image":
        return source.suffix.lower() in PILLOW_SUFFIXES and _from_image_file(source, out)
    if kind == "video":
        return _ffmpeg_frame(source, out, audio=False)
    if kind == "audio":
        return _ffmpeg_frame(source, out, audio=True)
    if kind == "pdf":
        return _pdf_page(source, out)
    return False


def thumb_path(data_dir: Path, item_id: str) -> Path:
    return data_dir / "thumbs" / f"{item_id}.webp"


def _status(out: Path, source: Path, kind: str) -> str:
    if out.is_file():
        return "ready"
    if kind not in KINDS or out.with_suffix(".none").exists() or not source.is_file():
        return "none"
    return "make"


def _make_once(source: Path, kind: str, out: Path) -> bool:
    if out.is_file():  # made while this request waited its turn
        return True
    if make_thumbnail(source, kind, out):
        return True
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".none").touch()
    log.info("no thumbnail for %s (%s)", out.stem, kind)
    return False


async def thumbnail_for(data_dir: Path, item_id: str, source: Path, kind: str) -> Path | None:
    """The cached thumbnail, made now if needed; None when this file has no picture."""
    out = thumb_path(data_dir, item_id)
    status = await asyncio.to_thread(_status, out, source, kind)
    if status != "make":
        return out if status == "ready" else None
    async with _limit:
        made = await asyncio.to_thread(_make_once, source, kind, out)
    return out if made else None


def forget(data_dir: Path, item_id: str) -> None:
    out = thumb_path(data_dir, item_id)
    out.unlink(missing_ok=True)
    out.with_suffix(".none").unlink(missing_ok=True)
