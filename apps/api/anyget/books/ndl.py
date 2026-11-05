"""National Diet Library, Japan: NDL Search (OpenSearch), IIIF from NDL Digital Collections.

The search asks only for Digital Collections items published on the internet
(data provider `ndl-dl-online`), the ones with open IIIF manifests.
"""

import re
from urllib.parse import quote

from anyget.books.base import Access, Adapter, BookFormat, BookHit, SearchContext
from anyget.books.http import children, get_xml, text_of, texts_of

# Digital Collections ids appear as https://dl.ndl.go.jp/pid/N, …/info:ndljp/pid/N or
# a bare info:ndljp/pid/N identifier.
_PID = re.compile(r"(?:dl\.ndl\.go\.jp/(?:info:ndljp/)?|info:ndljp/)pid/(\d+)")


async def search(ctx: SearchContext, query: str, limit: int) -> list[BookHit]:
    # dpid=ndl-dl-online: Digital Collections items published on the internet (open).
    url = (
        "https://ndlsearch.ndl.go.jp/api/opensearch"
        f"?any={quote(query)}&cnt={limit}&dpid=ndl-dl-online"
    )
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
