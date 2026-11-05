"""Run a plan: every source at once, each with a time limit, as result cards.

`stream` yields each source's cards as soon as that source answers, so the page fills
in while slow sources (national libraries, YouTube search) are still working.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any, Literal

from anyget.books.base import Access, BookHit
from anyget.books.ranker import relevance as book_relevance
from anyget.books.search import search_books
from anyget.core.net import Net
from anyget.core.settings import Settings
from anyget.core.text import words
from anyget.handlers.archive_org import SearchHit, build_query
from anyget.handlers.archive_org import search as archive_search
from anyget.universal.models import (
    Licence,
    Media,
    QuerySpec,
    ResultCard,
    RouterPlan,
    SourceDone,
    UniversalDone,
)
from anyget.universal.relevance import score as archive_score

log = logging.getLogger("anyget.universal")

TIME_LIMIT = {"archive": 10.0, "books": 10.0, "videos": 20.0, "libraries": 20.0}
PER_SOURCE = 12

ARCHIVE_MEDIA: dict[str, Media] = {
    "movies": "movie",
    "audio": "music",
    "etree": "music",
    "texts": "book",
    "image": "photo",
}


def archive_licence(hit: SearchHit) -> Licence:
    url = (hit.licenseurl or "").lower()
    if "publicdomain" in url:
        return "public_domain"
    if "creativecommons.org" in url:
        return "cc"
    return "unknown"


def book_licence(hit: BookHit) -> Licence:
    if hit.access == Access.full_view:
        return "public_domain"  # free full view: public domain or openly licensed
    if hit.access == Access.view_online:
        return "streaming_only"
    return "rights_reserved"


def archive_card(hit: SearchHit, query: str) -> ResultCard:
    media = ARCHIVE_MEDIA.get(hit.mediatype or "", "other")
    if media == "book" and set(hit.collection or []) & {"cia-readingroom", "fbi-vault"}:
        media = "declassified"
    page = f"https://archive.org/details/{hit.identifier}"
    return ResultCard(
        id=f"archive:{hit.identifier}",
        source="archive",
        source_label="Internet Archive",
        title=hit.title,
        url=page,
        download=page if hit.mediatype != "collection" else None,
        media=media,
        licence=archive_licence(hit),
        year=hit.year,
        creator=hit.creator,
        thumbnail=hit.thumbnail,
        score=archive_score(hit, query),
    )


def book_card(hit: BookHit, query: str, source: str) -> ResultCard:
    best = hit.formats[0] if hit.formats else None
    score = 2.0 * book_relevance(hit, query) + (0.5 if hit.downloadable else 0.0)
    return ResultCard(
        id=f"{source}:{hit.source}:{hit.id}",
        source="libraries" if source == "libraries" else "books",
        source_label=hit.source_label or hit.source,
        title=hit.title,
        url=hit.details_url,
        download=best.url if best and hit.downloadable else None,
        media="book",
        licence=book_licence(hit),
        year=hit.year,
        creator=", ".join(hit.authors[:2]) or None,
        formats=[f.kind for f in hit.formats],
        thumbnail=hit.thumbnail,
        score=score,
    )


def video_card(entry: dict[str, Any], query: str) -> ResultCard:
    asked = words(query)
    share = len(asked & words(str(entry.get("title", "")))) / len(asked) if asked else 0.0
    return ResultCard(
        id=f"videos:{entry['id']}",
        source="videos",
        source_label="YouTube",
        title=str(entry.get("title") or entry["id"]),
        url=str(entry["url"]),
        download=str(entry["url"]),
        media="video",
        licence="unknown",
        creator=entry.get("channel"),
        thumbnail=entry.get("thumbnail"),
        score=2.0 * share,
    )


class Engine:
    def __init__(self, net: Net, settings: Settings, video_search: Any = None) -> None:
        self.net = net
        self.settings = settings
        # `async (query, limit) -> list[dict]`: YouTube search through yt-dlp.
        self.video_search = video_search

    async def _run(self, spec: QuerySpec) -> list[ResultCard]:
        if spec.source == "archive":
            query = build_query(spec.q, mediatype=spec.filters.get("mediatype"))
            page = await archive_search(self.net, query, rows=50)
            return [archive_card(hit, spec.q) for hit in page.items]
        if spec.source in ("books", "libraries"):
            kind: Literal["books", "libraries"] = (
                "libraries" if spec.source == "libraries" else "books"
            )
            found = await search_books(self.net, self.settings, spec.q, kind=kind, limit=PER_SOURCE)
            return [book_card(hit, spec.q, spec.source) for hit in found.results]
        if spec.source == "videos" and self.video_search is not None:
            entries = await self.video_search(spec.q, PER_SOURCE)
            return [video_card(entry, spec.q) for entry in entries]
        return []

    async def _one(self, spec: QuerySpec) -> SourceDone:
        try:
            cards = await asyncio.wait_for(self._run(spec), TIME_LIMIT[spec.source])
        except TimeoutError:
            return SourceDone(source=spec.source, status="timeout")
        except Exception as exc:  # one source failing never stops the others
            log.info("universal source %s failed: %s", spec.source, type(exc).__name__)
            return SourceDone(source=spec.source, status="error", message=type(exc).__name__)
        cards.sort(key=lambda c: -c.score)
        return SourceDone(source=spec.source, status="ok", results=cards[:PER_SOURCE])

    async def stream(self, plan: RouterPlan) -> AsyncIterator[SourceDone | UniversalDone]:
        tasks = [asyncio.ensure_future(self._one(spec)) for spec in plan.queries]
        counts: dict[str, int] = {}
        total = 0
        try:
            for next_done in asyncio.as_completed(tasks):
                done = await next_done
                for card in done.results:
                    counts[card.media] = counts.get(card.media, 0) + 1
                total += len(done.results)
                yield done
        finally:
            for task in tasks:
                task.cancel()
        yield UniversalDone(total=total, counts=counts)
