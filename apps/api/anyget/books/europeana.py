"""Europeana (free key): openly licensed texts; page images through its IIIF API."""

from urllib.parse import quote

from anyget.books.base import Access, Adapter, BookFormat, BookHit, SearchContext, as_list, first
from anyget.books.http import get_json


async def search(ctx: SearchContext, query: str, limit: int) -> list[BookHit]:
    key = ctx.settings.europeana_key
    lang = f"&qf=LANGUAGE:{quote(ctx.lang)}" if ctx.lang else ""
    url = (
        f"https://api.europeana.eu/record/v2/search.json?wskey={quote(key)}&query={quote(query)}"
        f"&qf=TYPE:TEXT&reusability=open&rows={limit}{lang}"
    )
    data = await get_json(ctx, url)
    hits = []
    for item in data.get("items") or []:
        record = str(item.get("id") or "")  # "/9200365/BibliographicResource_…"
        if not record:
            continue
        hits.append(
            BookHit(
                source="europeana",
                id=record,
                title=first(item.get("title")) or record,
                authors=as_list(item.get("dcCreator"))[:3],
                year=first(item.get("year")),
                language=first(item.get("language")),
                access=Access.full_view,
                formats=[
                    BookFormat(
                        kind="images",
                        url=f"https://iiif.europeana.eu/presentation{record}/manifest",
                        label="Page images",
                    )
                ],
                details_url=first(item.get("guid")) or f"https://www.europeana.eu/item{record}",
                thumbnail=first(item.get("edmPreview")),
            )
        )
    return hits


ADAPTER = Adapter(
    "europeana",
    "Europeana",
    "europe",
    search,
    key_setting="europeana_key",
    kinds=("books", "libraries"),
    trust=4,
)
