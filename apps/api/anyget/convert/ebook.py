"""EPUB → PDF with Calibre's ebook-convert, when Calibre is installed."""

from pathlib import Path

from anyget.convert.tools import run, which


def available() -> bool:
    return which("ebook-convert") is not None


async def epub_to_pdf(source: Path, target: Path) -> Path:
    partial = target.with_name(f"{target.stem}.part.pdf")
    await run(["ebook-convert", str(source), str(partial)], what="Calibre")
    partial.replace(target)
    return target
