"""Folder templates: where new downloads go, e.g. "{type}/{source}".

Placeholders: {type} (videos, audio, images, books, code, files…), {source}
(the site, e.g. youtube.com), {year}, {month}, {title}. Each part is sanitized and
the result always stays inside the downloads folder. Empty template = no folder.
"""

import re
from datetime import UTC, datetime
from urllib.parse import urlsplit

from anyget.core.filenames import sanitize_filename

PLACEHOLDERS = ("type", "source", "year", "month", "title")
_FIELD = re.compile(r"\{(\w+)\}")
MAX_DEPTH = 4

TYPE_BY_HANDLER = {
    "ytdlp": "videos",
    "gallery": "images",
    "iiif_library": "books",
    "books": "books",
    "archive_org": "archive",
    "wayback": "web",
    "git_code": "code",
    "ai_resources": "ai",
    "cloud_share": "files",
    "http": "files",
}


class TemplateError(ValueError):
    pass


def validate(template: str) -> str:
    template = template.strip().strip("/")
    unknown = [name for name in _FIELD.findall(template) if name not in PLACEHOLDERS]
    if unknown:
        raise TemplateError(f"unknown placeholder {{{unknown[0]}}}; use {', '.join(PLACEHOLDERS)}")
    if len([p for p in template.split("/") if p]) > MAX_DEPTH:
        raise TemplateError(f"at most {MAX_DEPTH} folder levels")
    return template


def kind_for(handler: str, options: dict[str, object] | None = None) -> str:
    if handler == "ytdlp" and (options or {}).get("preset") == "audio":
        return "audio"
    return TYPE_BY_HANDLER.get(handler, "files")


def source_for(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.").removeprefix("m.") or "local"


def render(
    template: str, *, kind: str, url: str, title: str, when: datetime | None = None
) -> list[str]:
    """Folder parts for one download ([] when the template is empty)."""
    template = validate(template)
    if not template:
        return []
    when = when or datetime.now(UTC)
    values = {
        "type": kind,
        "source": source_for(url),
        "year": f"{when.year:04d}",
        "month": f"{when.month:02d}",
        "title": title,
    }
    parts = []
    for raw in template.split("/"):
        text = _FIELD.sub(lambda m: values[m.group(1)], raw).strip()
        if not text or text in (".", ".."):
            continue
        parts.append(sanitize_filename(text, fallback="files"))
    return parts
