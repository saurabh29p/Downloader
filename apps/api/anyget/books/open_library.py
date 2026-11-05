"""Open Library: editions and ISBNs; open scans live on archive.org."""

from urllib.parse import quote

from anyget.books.base import Access, Adapter, BookFormat, BookHit, SearchContext, as_list
from anyget.books.http import get_json

FIELDS = "key,title,author_name,first_publish_year,language,ia,ebook_access,isbn,cover_i"
ACCESS = {
    "public": Access.full_view,
    "borrowable": Access.borrow_only,
    "printdisabled": Access.borrow_only,
}


async def search(ctx: SearchContext, query: str, limit: int) -> list[BookHit]:
    url = f"https://openlibrary.org/search.json?q={quote(query)}&fields={FIELDS}&limit={limit}"
    data = await get_json(ctx, url)
    hits = []
    for doc in data.get("docs") or []:
        key = str(doc.get("key") or "")
        access = ACCESS.get(str(doc.get("ebook_access") or ""), Access.in_copyright)
        ia = as_list(doc.get("ia"))
        formats = (
            [BookFormat(kind="pdf_scan", url=f"https://archive.org/details/{ia[0]}", label="PDF")]
            if access == Access.full_view and ia
            else []
        )
        cover = doc.get("cover_i")
        hits.append(
            BookHit(
                source="open_library",
                id=key,
                title=str(doc.get("title") or key),
                authors=as_list(doc.get("author_name"))[:3],
                year=str(doc["first_publish_year"]) if doc.get("first_publish_year") else None,
                language=next(iter(as_list(doc.get("language"))), None),
                access=access,
                formats=formats,
                details_url=f"https://openlibrary.org{key}",
                thumbnail=f"https://covers.openlibrary.org/b/id/{cover}-M.jpg" if cover else None,
                isbn=as_list(doc.get("isbn"))[:3],
            )
        )
    return hits


ADAPTER = Adapter("open_library", "Open Library", "global", search, trust=4)
