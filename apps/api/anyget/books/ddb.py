"""Deutsche Digitale Bibliothek (free key)."""

from urllib.parse import quote

from anyget.books.base import Access, Adapter, BookHit, SearchContext, first
from anyget.books.http import get_json


async def search(ctx: SearchContext, query: str, limit: int) -> list[BookHit]:
    url = (
        "https://api.deutsche-digitale-bibliothek.de/2/search/index/search/select"
        f"?q={quote(query)}&rows={limit}&oauth_consumer_key={quote(ctx.settings.ddb_key)}"
    )
    data = await get_json(ctx, url)
    hits = []
    for doc in (data.get("response") or {}).get("docs") or []:
        item_id = str(doc.get("id") or "")
        if not item_id:
            continue
        hits.append(
            BookHit(
                source="ddb",
                id=item_id,
                title=first(doc.get("label")) or first(doc.get("title")) or item_id,
                year=first(doc.get("begin_time")) or first(doc.get("time")),
                access=Access.view_online,
                details_url=f"https://www.deutsche-digitale-bibliothek.de/item/{item_id}",
                thumbnail=first(doc.get("thumbnail")),
            )
        )
    return hits


ADAPTER = Adapter(
    "ddb",
    "Deutsche Digitale Bibliothek",
    "europe",
    search,
    key_setting="ddb_key",
    kinds=("libraries",),
)
