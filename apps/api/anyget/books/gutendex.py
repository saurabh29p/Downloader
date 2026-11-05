"""Project Gutenberg through Gutendex (public-domain EPUB and text)."""

from typing import Any
from urllib.parse import quote

from anyget.books.base import Access, Adapter, BookFormat, BookHit, FormatKind, SearchContext
from anyget.books.http import get_json

MIME: list[tuple[str, FormatKind, str]] = [
    ("application/epub+zip", "epub", "EPUB"),
    ("text/plain; charset=utf-8", "txt", "Plain text"),
    ("text/plain; charset=us-ascii", "txt", "Plain text"),
    ("text/plain", "txt", "Plain text"),
    ("text/html", "html", "HTML"),
]


def to_hit(book: dict[str, Any]) -> BookHit:
    formats = book.get("formats") or {}
    found: list[BookFormat] = []
    seen: set[str] = set()
    for mime, kind, label in MIME:
        url = formats.get(mime)
        if url and kind not in seen:
            seen.add(kind)
            found.append(BookFormat(kind=kind, url=str(url), label=label))
    in_copyright = bool(book.get("copyright"))
    gid = str(book.get("id"))
    return BookHit(
        source="gutendex",
        id=gid,
        title=str(book.get("title") or gid),
        authors=[str(a.get("name")) for a in book.get("authors") or [] if a.get("name")][:3],
        language=(book.get("languages") or [None])[0],
        access=Access.in_copyright if in_copyright else Access.full_view,
        formats=[] if in_copyright else found,
        details_url=f"https://www.gutenberg.org/ebooks/{gid}",
        thumbnail=formats.get("image/jpeg"),
    )


async def search(ctx: SearchContext, query: str, limit: int) -> list[BookHit]:
    base = ctx.settings.gutendex_url.rstrip("/")
    lang = f"&languages={quote(ctx.lang)}" if ctx.lang else ""
    data = await get_json(ctx, f"{base}/books?search={quote(query)}{lang}")
    return [to_hit(b) for b in (data.get("results") or [])[:limit]]


ADAPTER = Adapter("gutendex", "Project Gutenberg", "global", search, trust=1)
