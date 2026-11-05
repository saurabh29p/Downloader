"""OCR with OCRmyPDF (Tesseract): adds a searchable text layer to a PDF."""

import re
import subprocess
from functools import lru_cache
from pathlib import Path

from anyget.convert.tools import run, which

_LANG = re.compile(r"^[a-z]{3}(?:_[a-z]+)?$", re.I)


def available() -> bool:
    return which("ocrmypdf") is not None and which("tesseract") is not None


@lru_cache(maxsize=1)
def languages() -> tuple[str, ...]:
    exe = which("tesseract")
    if exe is None:
        return ()
    try:
        out = subprocess.run(  # noqa: S603 (fixed binary, fixed args)
            [exe, "--list-langs"], capture_output=True, text=True, timeout=10, check=False
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ()
    return tuple(sorted(line.strip() for line in out.splitlines()[1:] if _LANG.match(line.strip())))


def pick_languages(wanted: str | None) -> str:
    """'eng+hin' style list limited to installed languages (default: English)."""
    installed = set(languages())
    asked = [lang for lang in (wanted or "eng").replace(",", "+").split("+") if _LANG.match(lang)]
    chosen = [lang for lang in asked if not installed or lang in installed]
    return "+".join(chosen or ["eng"])


async def ocr_pdf(source: Path, target: Path, langs: str | None = None) -> Path:
    partial = target.with_name(target.name + ".part.pdf")
    await run(
        [
            "ocrmypdf",
            "--skip-text",  # pages that already have text are kept as they are
            "--output-type",
            "pdf",
            "--sidecar",
            str(target.with_suffix(".txt")),
            "-l",
            pick_languages(langs),
            str(source),
            str(partial),
        ],
        what="OCR",
    )
    partial.replace(target)
    return target
