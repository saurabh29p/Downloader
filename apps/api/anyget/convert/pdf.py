"""Page images → one PDF (img2pdf: lossless, keeps each image's resolution)."""

from pathlib import Path

import img2pdf  # type: ignore[import-untyped]
from PIL import Image

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".jp2", ".webp", ".gif", ".bmp"}


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


def _pdf_ready(path: Path, scratch: Path) -> Path:
    """img2pdf takes JPEG/PNG/TIFF/JP2 without alpha; convert the rest to JPEG/PNG."""
    with Image.open(path) as image:
        if path.suffix.lower() in {".jpg", ".jpeg", ".jp2"} or (
            image.format in {"PNG", "TIFF"} and image.mode not in {"RGBA", "LA", "P"}
        ):
            return path
        target = scratch / f"{path.stem}.png"
        image.convert("RGB").save(target, "PNG")
        return target


def images_to_pdf(images: list[Path], target: Path) -> Path:
    if not images:
        raise ValueError("no images to merge")
    scratch = target.parent / f".{target.stem}.tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    try:
        ready = [str(_pdf_ready(p, scratch)) for p in images]
        partial = target.with_name(target.name + ".part")
        partial.write_bytes(img2pdf.convert(ready, rotation=img2pdf.Rotation.ifvalid))
        partial.replace(target)
    finally:
        for leftover in scratch.glob("*"):
            leftover.unlink()
        scratch.rmdir()
    return target
