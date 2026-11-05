"""Internet Archive texts (advancedsearch). Lending-library items are borrow-only."""

from urllib.parse import quote

from anyget.books.base import Access, Adapter, BookFormat, BookHit, SearchContext, as_list, first
from anyget.books.http import get_json
from anyget.handlers.archive_org import build_query

LENDING = {"inlibrary", "printdisabled", "lendinglibrary"}
FIELDS = ("identifier", "title", "creator", "year", "language", "format", "collection")


async def search(ctx: SearchContext, query: str, limit: int) -> list[BookHit]:
    q = build_query(query, mediatype="texts", language=None)
    fields = "&".join(f"fl[]={f}" for f in FIELDS)
    url = (
        "https://archive.org/advancedsearch.php?"
        f"q={quote(q)}&{fields}&rows={limit}&page=1&output=json&sort[]=downloads+desc"
    )
    data = await get_json(ctx, url)
    hits = []
    for doc in (data.get("response") or {}).get("docs") or []:
        identifier = str(doc.get("identifier") or "")
        if not identifier:
            continue
        details = f"https://archive.org/details/{identifier}"
        formats = {f.lower() for f in as_list(doc.get("format"))}
        lending = bool(LENDING & {c.lower() for c in as_list(doc.get("collection"))})
        kinds: list[BookFormat] = []
        if not lending:
            if "epub" in formats:
                kinds.append(BookFormat(kind="epub", url=details, label="EPUB"))
            if "text pdf" in formats:
                kinds.append(BookFormat(kind="pdf_text", url=details, label="Text PDF"))
            elif "pdf" in formats or "image container pdf" in formats:
                kinds.append(BookFormat(kind="pdf_scan", url=details, label="PDF"))
            if "djvutxt" in formats or "djvu txt" in formats:
                kinds.append(BookFormat(kind="txt", url=details, label="Text"))
        hits.append(
            BookHit(
                source="internet_archive",
                id=identifier,
                title=first(doc.get("title")) or identifier,
                authors=as_list(doc.get("creator"))[:3],
                year=first(doc.get("year")),
                language=first(doc.get("language")),
                access=Access.borrow_only if lending else Access.full_view,
                formats=kinds,
                details_url=details,
                thumbnail=f"https://archive.org/services/img/{identifier}",
            )
        )
    return hits


ADAPTER = Adapter(
    "internet_archive", "Internet Archive", "global", search, kinds=("books", "libraries"), trust=3
)
