"""Biodiversity Heritage Library (free key): old science and natural history, as PDF."""

from urllib.parse import quote

from anyget.books.base import Access, Adapter, BookFormat, BookHit, SearchContext
from anyget.books.http import get_json


async def search(ctx: SearchContext, query: str, limit: int) -> list[BookHit]:
    url = (
        "https://www.biodiversitylibrary.org/api3?op=PublicationSearch&searchtype=F&format=json"
        f"&searchterm={quote(query)}&apikey={quote(ctx.settings.bhl_key)}"
    )
    data = await get_json(ctx, url)
    hits = []
    for item in (data.get("Result") or [])[:limit]:
        item_id = item.get("ItemID")
        title_id = item.get("TitleID")
        formats = (
            [
                BookFormat(
                    kind="pdf_scan",
                    url=f"https://www.biodiversitylibrary.org/itempdf/{item_id}",
                    label="PDF",
                )
            ]
            if item_id
            else []
        )
        hits.append(
            BookHit(
                source="bhl",
                id=str(item_id or title_id),
                title=str(item.get("Title") or item_id),
                authors=[str(a.get("Name")) for a in item.get("Authors") or [] if a.get("Name")][
                    :3
                ],
                year=str(item.get("PublicationDate") or "") or None,
                language=item.get("Language"),
                access=Access.full_view if formats else Access.view_online,
                formats=formats,
                details_url=str(
                    item.get("ItemUrl")
                    or item.get("TitleUrl")
                    or f"https://www.biodiversitylibrary.org/bibliography/{title_id}"
                ),
                partial=bool(item.get("Volume")),
            )
        )
    return hits


ADAPTER = Adapter(
    "bhl",
    "Biodiversity Heritage Library",
    "global",
    search,
    key_setting="bhl_key",
    kinds=("books", "libraries"),
    trust=4,
)
