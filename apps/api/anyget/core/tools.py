"""Versions of the external tools AnyGet depends on (shown by /api/health)."""

import importlib.metadata
import re
import shutil
import subprocess
from functools import lru_cache

from pydantic import BaseModel


class ToolVersions(BaseModel):
    yt_dlp: str | None
    yt_dlp_ejs: str | None
    deno: str | None
    ffmpeg: str | None


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
    )


def deno_path() -> str | None:
    return shutil.which("deno")
