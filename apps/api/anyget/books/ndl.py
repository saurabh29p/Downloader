"""National Diet Library, Japan: NDL Search (OpenSearch), IIIF from NDL Digital Collections.

Only items published on the internet have open manifests; others are read on site.
"""

import re
from urllib.parse import quote

from anyget.books.base import Access, Adapter, BookFormat, BookHit, SearchContext
from anyget.books.http import children, get_xml, text_of, texts_of

_PID = re.compile(r"dl\.ndl\.go\.jp/(?:info:ndljp/)?pid/(\d+)")


async def search(ctx: SearchContext, query: str, limit: int) -> list[BookHit]:
    url = f"https://ndlsearch.ndl.go.jp/api/opensearch?any={quote(query)}&cnt={limit}&mediatype=digitized"
    root = await get_xml(ctx, url)
    hits = []
    for item in children(root, "item"):
        blob = " ".join(
            [
                *(c.text or "" for c in item.iter()),
                *(v for c in item.iter() for v in c.attrib.values()),
            ]
        )
        pid = next(iter(_PID.findall(blob)), None)
        link = text_of(item, "link") or ""
        hits.append(
            BookHit(
                source="ndl",
                id=pid or link,
                title=text_of(item, "title") or (pid or link),
                authors=[a for a in texts_of(item, "creator") if a][:3]
                or texts_of(item, "author")[:3],
                year=text_of(item, "date") or text_of(item, "issued"),
                language="ja",
                access=Access.full_view if pid else Access.view_online,
                formats=[
                    BookFormat(
                        kind="images", url=f"https://dl.ndl.go.jp/pid/{pid}", label="Page images"
                    )
                ]
                if pid
                else [],
                details_url=f"https://dl.ndl.go.jp/pid/{pid}" if pid else link,
            )
        )
    return hits


ADAPTER = Adapter(
    "ndl", "National Diet Library", "asia", search, kinds=("books", "libraries"), trust=4
)
