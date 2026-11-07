"""What a saved file really is, and how (or whether) AnyGet can show it.

The answer comes from the file's first bytes (magic numbers) as well as its name, so a
video saved without an extension, or a PDF named `.bin`, still opens in the right
viewer. Nothing is decoded or converted here: browsers play what they can, and
everything else gets a clear reason plus Download / Open.
"""

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from anyget.library.kinds import kind_of

Preview = Literal["video", "audio", "image", "pdf", "epub", "text", "none"]
# Why there is no preview (the web translates these codes).
Reason = Literal["unsupported_format", "office", "archive", "too_large", "empty", "missing"]

HEAD_BYTES = 4096
MAX_IMAGE = 60 * 1024 * 1024  # bigger pictures: Download / Open instead
TEXT_SUFFIXES = {".txt", ".md", ".srt", ".vtt", ".csv", ".json", ".xml", ".log", ".html", ".htm"}
# Browsers can't show these pictures; Convert (img2pdf) or Download instead.
UNSHOWABLE_IMAGES = {"image/tiff", "image/heic", "image/x-ms-bmp-unknown"}


class Subtitle(BaseModel):
    index: int
    label: str
    lang: str | None


class FileInfo(BaseModel):
    preview: Preview
    mime: str
    size: int
    reason: Reason | None = None
    # Browsers differ (MKV, MOV, FLAC…): the player tests canPlayType() and explains.
    may_not_play: bool = False
    subtitles: list[Subtitle] = []


def _ftyp(head: bytes) -> str | None:
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return head[8:12].decode("latin-1")
    return None


def sniff(head: bytes, name: str) -> tuple[Preview, str]:
    """(preview kind, MIME type) from the first bytes, falling back to the name."""
    suffix = Path(name).suffix.lower()
    if head.startswith(b"%PDF-"):
        return "pdf", "application/pdf"
    if head.startswith(b"PK\x03\x04"):
        if b"mimetypeapplication/epub+zip" in head[:100]:
            return "epub", "application/epub+zip"
        if b"[Content_Types].xml" in head or suffix in {".docx", ".xlsx", ".pptx", ".odt"}:
            return "none", "application/vnd.openxmlformats-officedocument"
        return "none", "application/zip"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image", "image/jpeg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image", "image/gif"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image", "image/webp"
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return "audio", "audio/wav"
    if head.startswith(b"RIFF") and head[8:12] == b"AVI ":
        return "none", "video/x-msvideo"
    if head.startswith(b"BM") and suffix == ".bmp":
        return "image", "image/bmp"
    if head.startswith((b"II*\x00", b"MM\x00*")):
        return "none", "image/tiff"
    brand = _ftyp(head)
    if brand is not None:
        if brand in ("avif", "avis"):
            return "image", "image/avif"
        if brand in ("heic", "heix", "mif1", "msf1"):
            return "none", "image/heic"
        if brand.startswith("M4A") or brand.startswith("M4B") or suffix in {".m4a", ".m4b"}:
            return "audio", "audio/mp4"
        if brand == "qt  ":
            return "video", "video/quicktime"
        return "video", "video/mp4"
    if head.startswith(b"\x1aE\xdf\xa3"):
        return ("video", "video/webm") if b"webm" in head[:64] else ("video", "video/x-matroska")
    if head.startswith(b"OggS"):
        if b"theora" in head[:128]:
            return "video", "video/ogg"
        return "audio", "audio/ogg"
    if head.startswith(b"fLaC"):
        return "audio", "audio/flac"
    if head.startswith(b"ID3") or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0):
        if suffix in {".aac"}:
            return "audio", "audio/aac"
        return "audio", "audio/mpeg"
    text = _as_text(head)
    if text is not None:
        lowered = text.lstrip()[:300].lower()
        if "<svg" in lowered and (lowered.startswith("<svg") or lowered.startswith("<?xml")):
            return "image", "image/svg+xml"
        if lowered.startswith(("<!doctype html", "<html")) or suffix in {".html", ".htm"}:
            return "text", "text/html"
        if suffix == ".vtt" or text.startswith("WEBVTT"):
            return "text", "text/vtt"
        if suffix == ".json":
            return "text", "application/json"
        if suffix == ".csv":
            return "text", "text/csv"
        if suffix in TEXT_SUFFIXES or not suffix:
            return "text", "text/plain"
        return "text", "text/plain"
    return "none", "application/octet-stream"


def _as_text(head: bytes) -> str | None:
    if not head or b"\x00" in head:
        return None
    # A cut multi-byte character at the end is fine.
    for cut in range(4):
        try:
            return head[: len(head) - cut].decode("utf-8")
        except UnicodeDecodeError:
            continue
    return None


SUBTITLE = re.compile(r"\.(srt|vtt)$", re.IGNORECASE)


def subtitles_for(path: Path) -> list[Path]:
    """Subtitle files saved next to a video: `<stem>.vtt`, `<stem>.en.srt`…"""
    stem = path.stem
    try:
        siblings = sorted(path.parent.iterdir())
    except OSError:
        return []
    return [
        p
        for p in siblings
        if p.is_file()
        and not p.is_symlink()
        and SUBTITLE.search(p.name)
        and (p.stem == stem or p.name.startswith(f"{stem}."))
    ]


def subtitle_lang(path: Path, stem: str) -> str | None:
    middle = path.name[len(stem) :].strip(".").rsplit(".", 1)[0]
    return middle or None


def inspect(path: Path) -> FileInfo:
    if not path.is_file():
        return FileInfo(preview="none", mime="application/octet-stream", size=0, reason="missing")
    size = path.stat().st_size
    if size == 0:
        return FileInfo(preview="none", mime="application/octet-stream", size=0, reason="empty")
    with path.open("rb") as fh:
        head = fh.read(HEAD_BYTES)
    preview, mime = sniff(head, path.name)
    reason: Reason | None = None
    if preview == "none":
        if mime == "application/zip" or kind_of(path) == "archive":
            reason = "archive"
        elif mime.startswith("application/vnd.openxml"):
            reason = "office"
        else:
            reason = "unsupported_format"
    elif preview == "image" and size > MAX_IMAGE:
        preview, reason = "none", "too_large"
    subs: list[Subtitle] = []
    if preview == "video":
        for index, sub in enumerate(subtitles_for(path)):
            lang = subtitle_lang(sub, path.stem)
            subs.append(Subtitle(index=index, label=lang or sub.suffix[1:].upper(), lang=lang))
    return FileInfo(
        preview=preview,
        mime=mime,
        size=size,
        reason=reason,
        may_not_play=mime
        in {"video/x-matroska", "video/quicktime", "audio/flac", "audio/ogg", "video/ogg"},
        subtitles=subs,
    )


def srt_to_vtt(text: str) -> str:
    """SubRip → WebVTT: a header and '.' instead of ',' in the timings."""
    if text.lstrip("﻿").startswith("WEBVTT"):
        return text.lstrip("﻿")
    body = re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", text.lstrip("﻿"))
    return "WEBVTT\n\n" + body.replace("\r\n", "\n")


def read_text(path: Path, offset: int, limit: int) -> tuple[str, int | None]:
    """A UTF-8 slice of a text file starting at a byte offset, never splitting a
    character; returns (text, next offset or None at the end)."""
    size = path.stat().st_size
    with path.open("rb") as fh:
        fh.seek(offset)
        chunk = fh.read(limit)
    end = offset + len(chunk)
    if end < size:
        cut = _incomplete_tail(chunk)
        chunk = chunk[: len(chunk) - cut]
        end -= cut
    return chunk.decode("utf-8", errors="replace"), (end if end < size else None)


def _incomplete_tail(chunk: bytes) -> int:
    """How many bytes at the end belong to a UTF-8 character that was cut off."""
    for back in range(1, min(4, len(chunk)) + 1):
        byte = chunk[-back]
        if byte & 0xC0 == 0x80:
            continue  # a continuation byte: keep looking for the lead byte
        need = 1 if byte < 0x80 else 2 if byte >= 0xC0 and byte < 0xE0 else 3 if byte < 0xF0 else 4
        return back if need > back else 0
    return 0
