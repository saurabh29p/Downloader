"""What kind of file is this (for filters and previews)."""

from pathlib import PurePath

from anyget.library.models import Kind

EXTENSIONS: dict[Kind, set[str]] = {
    "video": {"mp4", "mkv", "webm", "mov", "m4v", "avi", "ogv"},
    "audio": {"mp3", "m4a", "opus", "ogg", "oga", "flac", "wav", "aac"},
    "image": {"jpg", "jpeg", "png", "gif", "webp", "avif", "svg", "bmp", "tif", "tiff", "jp2"},
    "pdf": {"pdf"},
    "epub": {"epub"},
    "text": {"txt", "md", "html", "htm", "json", "csv", "srt", "vtt", "xml"},
    "archive": {"zip", "7z", "rar", "tar", "gz", "tgz", "bz2", "xz", "iso"},
}
_BY_EXT = {ext: kind for kind, exts in EXTENSIONS.items() for ext in exts}


def kind_of(path: str | PurePath) -> Kind:
    suffix = PurePath(path).suffix.lower().lstrip(".")
    return _BY_EXT.get(suffix, "other")
