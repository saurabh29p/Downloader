"""Wikisource (any language): transcribed texts, exported as EPUB by ws-export."""

from urllib.parse import quote

from anyget.books.base import Access, Adapter, BookFormat, BookHit, SearchContext
from anyget.books.http import get_json


async def search(ctx: SearchContext, query: str, limit: int) -> list[BookHit]:
    lang = (ctx.lang or "en").split("-")[0]
    api = (
        f"https://{lang}.wikisource.org/w/api.php?action=query&list=search&format=json"
        f"&srnamespace=0&srlimit={limit}&srsearch={quote(query)}"
    )
    data = await get_json(ctx, api)
    hits = []
    for item in (data.get("query") or {}).get("search") or []:
        title = str(item.get("title") or "")
        if not title:
            continue
        page = quote(title.replace(" ", "_"))
        hits.append(
            BookHit(
                source="wikisource",
                id=f"{lang}:{title}",
                title=title,
                language=lang,
                access=Access.full_view,
                formats=[
                    BookFormat(
                        kind="epub",
                        url=f"https://ws-export.wmcloud.org/?format=epub&lang={lang}&page={page}",
                        label="EPUB",
                    )
                ],
                details_url=f"https://{lang}.wikisource.org/wiki/{page}",
                partial="/" in title,  # sub-pages are chapters
            )
        )
    return hits


ADAPTER = Adapter("wikisource", "Wikisource", "global", search, trust=4)
