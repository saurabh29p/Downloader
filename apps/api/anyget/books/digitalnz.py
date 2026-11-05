"""DigitalNZ (free key): New Zealand collections, including Papers Past."""

from urllib.parse import quote

from anyget.books.base import Access, Adapter, BookHit, SearchContext, as_list, first
from anyget.books.http import get_json


async def search(ctx: SearchContext, query: str, limit: int) -> list[BookHit]:
    url = (
        f"https://api.digitalnz.org/v3/records.json?text={quote(query)}&per_page={limit}"
        f"&and[category][]=Books&api_key={quote(ctx.settings.digitalnz_key)}"
    )
    data = await get_json(ctx, url)
    hits = []
    for record in (data.get("search") or {}).get("results") or []:
        hits.append(
            BookHit(
                source="digitalnz",
                id=str(record.get("id")),
                title=str(record.get("title") or record.get("id")),
                authors=as_list(record.get("creator"))[:3],
                year=first(record.get("date")),
                access=Access.view_online,
                details_url=str(record.get("landing_url") or "https://digitalnz.org/"),
                thumbnail=record.get("thumbnail_url"),
            )
        )
    return hits


ADAPTER = Adapter(
    "digitalnz", "DigitalNZ", "oceania", search, key_setting="digitalnz_key", kinds=("libraries",)
)
