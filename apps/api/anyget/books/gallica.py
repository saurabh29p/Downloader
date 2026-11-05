"""Gallica (Bibliothèque nationale de France): SRU search, IIIF page images."""

import re
from urllib.parse import quote

from anyget.books.base import Access, Adapter, BookFormat, BookHit, SearchContext
from anyget.books.http import children, get_xml, text_of, texts_of

_ARK = re.compile(r"ark:/12148/([a-z0-9]+)", re.I)


async def search(ctx: SearchContext, query: str, limit: int) -> list[BookHit]:
    cql = f'gallica all "{query.replace(chr(34), " ")}" and dc.type all "monographie"'
    url = (
        "https://gallica.bnf.fr/SRU?operation=searchRetrieve&version=1.2"
        f"&maximumRecords={limit}&query={quote(cql)}"
    )
    root = await get_xml(ctx, url)
    hits = []
    for record in children(root, "recordData"):
        ark = next(
            (m.group(1) for i in texts_of(record, "identifier") if (m := _ARK.search(i))), None
        )
        if not ark:
            continue
        rights = " ".join(texts_of(record, "rights")).lower()
        public = "domaine public" in rights or "public domain" in rights or not rights
        hits.append(
            BookHit(
                source="gallica",
                id=ark,
                title=text_of(record, "title") or ark,
                authors=texts_of(record, "creator")[:3],
                year=text_of(record, "date"),
                language=text_of(record, "language"),
                access=Access.full_view if public else Access.view_online,
                formats=[
                    BookFormat(
                        kind="images",
                        url=f"https://gallica.bnf.fr/ark:/12148/{ark}",
                        label="Page images",
                    )
                ]
                if public
                else [],
                details_url=f"https://gallica.bnf.fr/ark:/12148/{ark}",
                thumbnail=f"https://gallica.bnf.fr/ark:/12148/{ark}/f1.thumbnail",
            )
        )
    return hits


ADAPTER = Adapter(
    "gallica", "Gallica (BnF)", "europe", search, kinds=("books", "libraries"), trust=3
)
