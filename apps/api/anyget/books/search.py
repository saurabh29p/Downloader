"""Ask many sources at once, with a time limit each, and rank what comes back."""

import asyncio
import logging
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from anyget.books.base import Adapter, BookHit, SearchContext, find_links
from anyget.books.ranker import rank, sort_formats
from anyget.books.sources import ADAPTERS
from anyget.core.net import BlockedURLError, Net
from anyget.core.settings import Settings
from anyget.handlers.base import HandlerError

log = logging.getLogger("anyget.books")

SourceState = Literal["ok", "needs_key", "timeout", "error", "link_only", "skipped"]


class SourceStatus(BaseModel):
    name: str
    label: str
    region: str
    status: SourceState
    count: int = 0
    message: str | None = None
    search_url: str | None = None


class BookSearch(BaseModel):
    query: str
    best: BookHit | None = None
    results: list[BookHit] = Field(default_factory=list)
    sources: list[SourceStatus] = Field(default_factory=list)


def pick_adapters(
    settings: Settings, kind: Literal["books", "libraries"], names: list[str] | None = None
) -> list[Adapter]:
    allowed = set(names or settings.book_sources or [])
    return [a for a in ADAPTERS if kind in a.kinds and (not allowed or a.name in allowed)]


async def _run(
    adapter: Adapter, ctx: SearchContext, query: str, limit: int, time_limit: float
) -> tuple[SourceStatus, list[BookHit]]:
    def status(state: SourceState, count: int = 0, message: str | None = None) -> SourceStatus:
        return SourceStatus(
            name=adapter.name,
            label=adapter.label,
            region=adapter.region,
            status=state,
            count=count,
            message=message,
            search_url=adapter.manual_url(query),
        )

    if adapter.search is None:
        return status("link_only"), []
    if adapter.key_setting and not adapter.key(ctx.settings):
        return status("needs_key", message=f"set ANYGET_{adapter.key_setting.upper()}"), []
    try:
        hits = await asyncio.wait_for(adapter.search(ctx, query, limit), time_limit)
    except TimeoutError:
        return status("timeout"), []
    except HandlerError as exc:
        return status("needs_key" if exc.code == "needs_key" else "error", message=exc.message), []
    except (httpx.HTTPError, BlockedURLError, ValueError, KeyError, TypeError) as exc:
        log.info("book source %s failed: %s", adapter.name, exc)
        return status("error", message=type(exc).__name__), []
    return status("ok", len(hits)), hits


async def search_books(
    net: Net,
    settings: Settings,
    query: str,
    *,
    kind: Literal["books", "libraries"] = "books",
    lang: str | None = None,
    limit: int = 10,
    sources: list[str] | None = None,
    time_limit: float = 8.0,
) -> BookSearch:
    query = query.strip()
    if not query:
        return BookSearch(query=query)
    ctx = SearchContext(net=net, settings=settings, lang=lang or None)
    adapters = pick_adapters(settings, kind, sources)
    outcomes = await asyncio.gather(*(_run(a, ctx, query, limit, time_limit) for a in adapters))
    labels = {a.name: a.label for a in adapters}
    hits = [
        sort_formats(find_links(hit)).model_copy(update={"source_label": labels.get(hit.source)})
        for _, found in outcomes
        for hit in found
    ]
    ranked = rank(hits, query, {a.name: a.trust for a in adapters})
    best = ranked[0] if ranked and ranked[0].downloadable else None
    return BookSearch(
        query=query, best=best, results=ranked, sources=[status for status, _ in outcomes]
    )
