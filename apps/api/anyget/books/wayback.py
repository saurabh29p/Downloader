"""Wayback Machine for dead ebook links: give it the old URL of a PDF or EPUB."""

from urllib.parse import urlsplit

from anyget.books.base import Access, Adapter, BookFormat, BookHit, FormatKind, SearchContext
from anyget.handlers.wayback import list_snapshots, raw_url

KINDS: dict[str, FormatKind] = {"epub": "epub", "pdf": "pdf_scan", "txt": "txt", "djvu": "pdf_scan"}


async def search(ctx: SearchContext, query: str, limit: int) -> list[BookHit]:
    text = query.strip()
    parts = urlsplit(text if "://" in text else f"http://{text}")
    ext = parts.path.rsplit(".", 1)[-1].lower() if "." in parts.path else ""
    if " " in text or not parts.hostname or "." not in parts.hostname or ext not in KINDS:
        return []
    page = await list_snapshots(ctx.net, text, limit=limit)
    good = [s for s in page.snapshots if (s.status or "200").startswith("2")]
    if not good:
        return []
    latest = good[-1]
    name = parts.path.rsplit("/", 1)[-1]
    return [
        BookHit(
            source="wayback",
            id=f"{latest.timestamp}/{latest.original}",
            title=name,
            year=latest.timestamp[:4],
            access=Access.full_view,
            formats=[
                BookFormat(
                    kind=KINDS[ext],
                    url=raw_url(latest.timestamp, latest.original),
                    size=latest.length,
                    label=ext.upper(),
                )
            ],
            details_url=f"https://web.archive.org/web/{latest.timestamp}/{latest.original}",
        )
    ]


ADAPTER = Adapter("wayback", "Wayback Machine", "global", search, trust=7)
