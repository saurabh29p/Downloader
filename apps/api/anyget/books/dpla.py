"""Digital Public Library of America (free key). Items are read at the partner library."""

from urllib.parse import quote

from anyget.books.base import Access, Adapter, BookHit, SearchContext, as_list, first
from anyget.books.http import get_json


async def search(ctx: SearchContext, query: str, limit: int) -> list[BookHit]:
    key = ctx.settings.dpla_key
    url = (
        f"https://api.dp.la/v2/items?q={quote(query)}&sourceResource.type=text"
        f"&page_size={limit}&api_key={quote(key)}"
    )
    data = await get_json(ctx, url)
    hits = []
    for doc in data.get("docs") or []:
        res = doc.get("sourceResource") or {}
        date = res.get("date")
        hits.append(
            BookHit(
                source="dpla",
                id=str(doc.get("id")),
                title=first(res.get("title")) or str(doc.get("id")),
                authors=as_list(res.get("creator"))[:3],
                year=first(date.get("displayDate") if isinstance(date, dict) else first(date)),
                language=first(
                    [
                        lang.get("name")
                        for lang in res.get("language") or []
                        if isinstance(lang, dict)
                    ]
                ),
                access=Access.view_online,
                details_url=str(doc.get("isShownAt") or "https://dp.la/"),
                thumbnail=first(doc.get("object")),
            )
        )
    return hits


ADAPTER = Adapter(
    "dpla", "DPLA", "americas", search, key_setting="dpla_key", kinds=("books", "libraries")
)
