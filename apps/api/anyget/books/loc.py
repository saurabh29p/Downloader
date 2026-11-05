"""Library of Congress (loc.gov JSON API). Page images come from its IIIF manifests."""

import re
from urllib.parse import quote

from anyget.books.base import Access, Adapter, BookFormat, BookHit, SearchContext, as_list, first
from anyget.books.http import get_json

_ITEM = re.compile(r"loc\.gov/item/([^/?#]+)")


async def search(ctx: SearchContext, query: str, limit: int) -> list[BookHit]:
    url = f"https://www.loc.gov/books/?q={quote(query)}&fo=json&c={limit}&fa=online-format:image"
    data = await get_json(ctx, url)
    hits = []
    for result in data.get("results") or []:
        link = str(result.get("id") or result.get("url") or "")
        match = _ITEM.search(link)
        if not match:
            continue
        item_id = match.group(1)
        restricted = bool(result.get("access_restricted"))
        hits.append(
            BookHit(
                source="loc",
                id=item_id,
                title=first(result.get("title")) or item_id,
                authors=as_list(result.get("contributor"))[:3],
                year=first(result.get("date")),
                language=first(result.get("language")),
                access=Access.view_online if restricted else Access.full_view,
                formats=[]
                if restricted
                else [
                    BookFormat(
                        kind="images",
                        url=f"https://www.loc.gov/item/{item_id}/",
                        label="Page images",
                    )
                ],
                details_url=f"https://www.loc.gov/item/{item_id}/",
                thumbnail=first(result.get("image_url")),
            )
        )
    return hits


ADAPTER = Adapter(
    "loc", "Library of Congress", "americas", search, kinds=("books", "libraries"), trust=3
)
