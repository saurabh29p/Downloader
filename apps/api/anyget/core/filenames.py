"""Safe, Unicode-friendly filenames and paths that can never leave the downloads root."""

import re
import unicodedata
from pathlib import Path, PurePosixPath

MAX_FILENAME_BYTES = 180

# Characters illegal on Windows (the strictest OS) plus path separators.
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_MAX_EXT_CHARS = 16


class UnsafePathError(ValueError):
    """A path would end up outside the downloads root."""


def _truncate_utf8(text: str, max_bytes: int) -> str:
    """Cut text to at most max_bytes of UTF-8 without splitting a character."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def _split_ext(name: str) -> tuple[str, str]:
    stem, dot, ext = name.rpartition(".")
    if dot and stem and 0 < len(ext) <= _MAX_EXT_CHARS and " " not in ext:
        return stem, "." + ext
    return name, ""


def sanitize_filename(name: str, fallback: str = "download") -> str:
    """Make one path component safe on Windows, macOS and Linux.

    Keeps the original script (Japanese, Arabic, Devanagari…), NFC-normalizes,
    removes only illegal characters, avoids reserved names and limits the result
    to 180 bytes while keeping the extension.
    """
    cleaned = unicodedata.normalize("NFC", name)
    cleaned = _ILLEGAL.sub("_", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".").rstrip()
    if not cleaned or set(cleaned) <= {"_", " ", "."}:
        cleaned = (
            _ILLEGAL.sub("_", unicodedata.normalize("NFC", fallback)).strip(" .") or "download"
        )

    stem, ext = _split_ext(cleaned)
    if stem.split(".")[0].upper() in _WINDOWS_RESERVED:
        stem = "_" + stem

    ext_bytes = len(ext.encode("utf-8"))
    stem = _truncate_utf8(stem, MAX_FILENAME_BYTES - ext_bytes).rstrip(" .")
    if not stem:
        stem = _truncate_utf8(fallback, MAX_FILENAME_BYTES - ext_bytes) or "download"
    return stem + ext


def safe_join(root: Path, *parts: str) -> Path:
    """Join parts under root and refuse anything that escapes it.

    Each part may contain '/' for sub-folders; every component is sanitized and
    the resolved result must stay inside the resolved root.
    """
    root_resolved = root.resolve()
    target = root_resolved
    for part in parts:
        if part.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", part):
            raise UnsafePathError(f"absolute path not allowed: {part!r}")
        for component in PurePosixPath(part.replace("\\", "/")).parts:
            if component in ("..", "."):
                raise UnsafePathError(f"path traversal not allowed: {part!r}")
            target = target / sanitize_filename(component)
    resolved = target.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise UnsafePathError(f"path escapes the downloads folder: {part!r}")
    return resolved


def ensure_inside(root: Path, path: Path) -> Path:
    """Return the resolved path if it is inside root, else raise UnsafePathError."""
    root_resolved = root.resolve()
    resolved = path.resolve()
    if resolved == root_resolved or root_resolved not in resolved.parents:
        raise UnsafePathError("path is outside the downloads folder")
    return resolved


def unique_path(path: Path) -> Path:
    """Return path, or 'name (1).ext', 'name (2).ext'… if it already exists."""
    if not path.exists():
        return path
    stem, ext = _split_ext(path.name)
    for i in range(1, 10_000):
        candidate = path.with_name(f"{stem} ({i}){ext}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(path)
