"""Standard Ebooks: carefully produced public-domain EPUBs.

Their OPDS/Atom catalog feeds need a Patrons Circle login, so this adapter reads
the public search page and builds each book's documented download link.
"""

import re
from html import unescape
from urllib.parse import quote

from anyget.books.base import Access, Adapter, BookFormat, BookHit, SearchContext
from anyget.books.http import get_text

BASE = "https://standardebooks.org"
_ITEM = re.compile(r'<li[^>]*about="(/ebooks/[^"]+)"[^>]*>(.*?)</li>', re.S)
_NAME = re.compile(r'property="schema:name"[^>]*>(.*?)<', re.S)
_AUTHOR = re.compile(r'typeof="schema:Person"[^>]*>.*?property="schema:name"[^>]*>(.*?)<', re.S)
_IMG = re.compile(r'<img[^>]+src="([^"]+)"')


def epub_url(path: str) -> str:
    """/ebooks/jane-austen/pride-and-prejudice → …/downloads/jane-austen_pride-and-prejudice.epub"""
    parts = path.strip("/").split("/")[1:]
    return f"{BASE}{path.rstrip('/')}/downloads/{'_'.join(parts)}.epub"


def parse_search(html: str, limit: int) -> list[BookHit]:
    hits = []
    for path, body in _ITEM.findall(html)[:limit]:
        names = [unescape(n).strip() for n in _NAME.findall(body)]
        author = _AUTHOR.search(body)
        image = _IMG.search(body)
        hits.append(
            BookHit(
                source="standard_ebooks",
                id=path,
                title=names[0] if names else path.rsplit("/", 1)[-1],
                authors=[unescape(author.group(1)).strip()] if author else [],
                language="en",
                access=Access.full_view,
                formats=[BookFormat(kind="epub", url=epub_url(path), label="EPUB")],
                details_url=BASE + path,
                thumbnail=BASE + image.group(1)
                if image and image.group(1).startswith("/")
                else None,
            )
        )
    return hits


async def search(ctx: SearchContext, query: str, limit: int) -> list[BookHit]:
    if ctx.lang and ctx.lang != "en":
        return []
    return parse_search(await get_text(ctx, f"{BASE}/ebooks?query={quote(query)}"), limit)


ADAPTER = Adapter("standard_ebooks", "Standard Ebooks", "global", search, trust=0)
