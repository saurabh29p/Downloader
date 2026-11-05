"""HathiTrust: looked up by ISBN/OCLC/LCCN. Full-view volumes are read on the site.

HathiTrust has no open full-text search API, and whole-book PDFs need a member
login, so full-view items are offered as "read online" links only.
"""

import re

from anyget.books.base import Access, Adapter, BookHit, SearchContext, as_list
from anyget.books.http import get_json

_ISBN = re.compile(r"^(?:isbn:?\s*)?([0-9][0-9\- ]{8,16}[0-9Xx])$", re.I)
_OCLC = re.compile(r"^oclc:?\s*(\d+)$", re.I)


def identifier(query: str) -> tuple[str, str] | None:
    text = query.strip()
    if match := _OCLC.match(text):
        return "oclc", match.group(1)
    if match := _ISBN.match(text):
        digits = re.sub(r"[\- ]", "", match.group(1))
        if len(digits) in (10, 13):
            return "isbn", digits
    return None


async def search(ctx: SearchContext, query: str, limit: int) -> list[BookHit]:
    found = identifier(query)
    if found is None:
        return []
    kind, value = found
    data = await get_json(
        ctx, f"https://catalog.hathitrust.org/api/volumes/brief/{kind}/{value}.json"
    )
    records = data.get("records") or {}
    title = next((as_list(r.get("titles"))[0] for r in records.values() if r.get("titles")), value)
    hits = []
    for item in (data.get("items") or [])[:limit]:
        full = str(item.get("usRightsString") or "").lower().startswith("full view")
        hits.append(
            BookHit(
                source="hathitrust",
                id=str(item.get("htid")),
                title=title,
                year=str(item.get("enumcron") or "") or None,
                access=Access.view_online if full else Access.in_copyright,
                details_url=str(item.get("itemURL") or "https://www.hathitrust.org/"),
                isbn=[value] if kind == "isbn" else [],
                partial=bool(item.get("enumcron")),
            )
        )
    return hits


ADAPTER = Adapter("hathitrust", "HathiTrust", "americas", search, trust=6)
