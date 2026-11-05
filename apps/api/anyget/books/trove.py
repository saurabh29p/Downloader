"""Trove, National Library of Australia (free key, API v3)."""

from urllib.parse import quote

from anyget.books.base import Access, Adapter, BookHit, SearchContext, as_list, first
from anyget.books.http import get_json


async def search(ctx: SearchContext, query: str, limit: int) -> list[BookHit]:
    url = (
        "https://api.trove.nla.gov.au/v3/result?category=book&encoding=json&reclevel=brief"
        f"&n={limit}&q={quote(query)}"
    )
    data = await get_json(ctx, url, headers={"X-API-KEY": ctx.settings.trove_key})
    hits = []
    for category in data.get("category") or []:
        for work in (category.get("records") or {}).get("work") or []:
            hits.append(
                BookHit(
                    source="trove",
                    id=str(work.get("id")),
                    title=str(work.get("title") or work.get("id")),
                    authors=as_list(work.get("contributor"))[:3],
                    year=first(work.get("issued")),
                    access=Access.view_online,
                    details_url=str(work.get("troveUrl") or "https://trove.nla.gov.au/"),
                )
            )
    return hits[:limit]


ADAPTER = Adapter(
    "trove", "Trove", "oceania", search, key_setting="trove_key", kinds=("libraries",)
)
