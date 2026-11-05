"""Order book hits so the best legal copy comes first.

1. Downloadable full-view copies first, then free-to-read online, then borrow-only,
   then not legally downloadable.
2. Among those, the closest match to what was asked for.
3. The best format: EPUB, text PDF, scanned PDF, page images, plain text, HTML.
4. Whole works before chapters or single volumes; then the more trusted source.
"""

import re
import unicodedata

from anyget.books.base import Access, BookHit

FORMAT_RANK = {"epub": 0, "pdf_text": 1, "pdf_scan": 2, "images": 3, "txt": 4, "html": 5}
ACCESS_RANK = {
    Access.full_view: 0,
    Access.view_online: 1,
    Access.borrow_only: 2,
    Access.in_copyright: 3,
}


def _words(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(c for c in folded if not unicodedata.combining(c))
    return {w for w in re.split(r"\W+", plain) if len(w) > 1 or not w.isascii()}


def relevance(hit: BookHit, query: str) -> float:
    """Share of the query's words found in the title and authors (0 to 1)."""
    asked = _words(query)
    if not asked:
        return 1.0
    have = _words(" ".join([hit.title, *hit.authors]))
    return len(asked & have) / len(asked)


def best_format_rank(hit: BookHit) -> int:
    return min((FORMAT_RANK[f.kind] for f in hit.formats), default=len(FORMAT_RANK))


def rank(hits: list[BookHit], query: str, trust: dict[str, int] | None = None) -> list[BookHit]:
    trust = trust or {}

    def key(item: tuple[int, BookHit]) -> tuple[int, int, int, int, int, int]:
        order, hit = item
        access = (
            0 if hit.downloadable else ACCESS_RANK[hit.access] + (hit.access == Access.full_view)
        )
        return (
            access,
            -round(relevance(hit, query) * 4),  # coarse buckets so format can still win
            best_format_rank(hit),
            int(hit.partial),
            trust.get(hit.source, 5),
            order,
        )

    return [hit for _, hit in sorted(enumerate(hits), key=key)]


def sort_formats(hit: BookHit) -> BookHit:
    formats = sorted(hit.formats, key=lambda f: FORMAT_RANK[f.kind])
    return hit.model_copy(update={"formats": formats})
