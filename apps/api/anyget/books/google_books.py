"""Google Books, free ebooks only (public-domain scans Google lets you download)."""

from urllib.parse import quote

from anyget.books.base import Access, Adapter, BookFormat, BookHit, SearchContext, as_list
from anyget.books.http import get_json


async def search(ctx: SearchContext, query: str, limit: int) -> list[BookHit]:
    lang = f"&langRestrict={quote(ctx.lang)}" if ctx.lang else ""
    url = (
        "https://www.googleapis.com/books/v1/volumes?filter=free-ebooks&printType=books"
        f"&maxResults={min(limit, 40)}&q={quote(query)}{lang}"
    )
    data = await get_json(ctx, url)
    hits = []
    for item in data.get("items") or []:
        info = item.get("volumeInfo") or {}
        access = item.get("accessInfo") or {}
        formats = []
        for key, kind, label in (("epub", "epub", "EPUB"), ("pdf", "pdf_scan", "PDF")):
            entry = access.get(key) or {}
            if entry.get("isAvailable") and entry.get("downloadLink"):
                formats.append(BookFormat(kind=kind, url=str(entry["downloadLink"]), label=label))
        isbn = [
            str(i.get("identifier"))
            for i in info.get("industryIdentifiers") or []
            if str(i.get("type", "")).startswith("ISBN")
        ]
        hits.append(
            BookHit(
                source="google_books",
                id=str(item.get("id")),
                title=str(info.get("title") or item.get("id")),
                authors=as_list(info.get("authors"))[:3],
                year=str(info.get("publishedDate") or "")[:4] or None,
                language=info.get("language"),
                access=Access.full_view if formats else Access.view_online,
                formats=formats,
                details_url=str(
                    info.get("infoLink") or f"https://books.google.com/books?id={item.get('id')}"
                ),
                thumbnail=(info.get("imageLinks") or {}).get("thumbnail"),
                isbn=isbn,
            )
        )
    return hits


ADAPTER = Adapter("google_books", "Google Books", "global", search, trust=6)
