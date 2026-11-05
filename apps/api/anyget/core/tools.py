"""Versions of the external tools AnyGet depends on (shown by /api/health)."""

import importlib.metadata
import re
import shutil
import subprocess
from functools import lru_cache

from pydantic import BaseModel

from anyget.convert.ocr import languages as ocr_languages


class ToolVersions(BaseModel):
    yt_dlp: str | None
    yt_dlp_ejs: str | None
    deno: str | None
    ffmpeg: str | None
    ocrmypdf: str | None = None
    tesseract: str | None = None
    tesseract_langs: list[str] = []
    calibre: str | None = None
    img2pdf: str | None = None


def _package(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _binary(name: str, args: list[str], pattern: str) -> str | None:
    path = shutil.which(name)
    if path is None:
        return None
    try:
        out = subprocess.run(  # noqa: S603 (fixed binary, fixed args)
            [path, *args], capture_output=True, text=True, timeout=5, check=False
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(pattern, out)
    return match.group(1) if match else None


@lru_cache(maxsize=1)
def tool_versions() -> ToolVersions:
    """Computed once per process; tools do not change while it runs."""
    return ToolVersions(
        yt_dlp=_package("yt-dlp"),
        yt_dlp_ejs=_package("yt-dlp-ejs"),
        deno=_binary("deno", ["--version"], r"deno (\S+)"),
        ffmpeg=_binary("ffmpeg", ["-version"], r"ffmpeg version (\S+)"),
        ocrmypdf=_binary("ocrmypdf", ["--version"], r"(\d+\.\d+[\w.]*)"),
        tesseract=_binary("tesseract", ["--version"], r"tesseract v?(\S+)"),
        tesseract_langs=list(ocr_languages()),
        calibre=_binary("ebook-convert", ["--version"], r"calibre (\S+?)\)?$"),
        img2pdf=_package("img2pdf"),
    )


def deno_path() -> str | None:
    return shutil.which("deno")
