"""Books, worldwide libraries, universal search and conversions."""

import asyncio
from collections.abc import AsyncIterator, Awaitable
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from anyget.api.deps import ERROR_RESPONSES, ServicesDep, UserDep
from anyget.books.search import BookSearch, search_books, stream_books
from anyget.books.sources import BY_NAME
from anyget.core.events import SSE_HEADERS, format_sse
from anyget.core.jobs import JobOut
from anyget.core.users import OWNER_ID
from anyget.handlers.archive_org import SearchHit, build_query
from anyget.handlers.archive_org import search as archive_search
from anyget.handlers.base import HandlerError
from anyget.handlers.convert import TARGETS, convert_url
from anyget.handlers.ytdlp import YtDlpHandler
from anyget.libraries.registry import LIBRARIES, REGIONS, Library
from anyget.universal.relevance import rank_hits

router = APIRouter(tags=["books"])

SearchType = Literal["archive", "books", "videos", "libraries"]
GroupStatus = Literal["ok", "error", "timeout"]
TIME_LIMIT = 10.0


class LibraryOut(Library):
    searchable: bool
    key_configured: bool | None = None


class LibraryList(BaseModel):
    regions: list[str]
    libraries: list[LibraryOut]


class VideoHit(BaseModel):
    id: str
    title: str
    url: str
    duration: float | None = None
    channel: str | None = None
    thumbnail: str | None = None


class ArchiveGroup(BaseModel):
    status: GroupStatus = "ok"
    message: str | None = None
    items: list[SearchHit] = Field(default_factory=list)


class VideoGroup(BaseModel):
    status: GroupStatus = "ok"
    message: str | None = None
    items: list[VideoHit] = Field(default_factory=list)


class UniversalSearch(BaseModel):
    query: str
    archive: ArchiveGroup | None = None
    books: BookSearch | None = None
    videos: VideoGroup | None = None
    libraries: BookSearch | None = None


class ConvertRequest(BaseModel):
    job_id: str
    to: Literal["pdf", "ocr", "mp3", "m4a", "opus", "flac", "wav", "mp4", "mkv", "webm"]
    lang: str | None = Field(default=None, pattern=r"^[A-Za-z_+]{1,64}$")


@router.get("/books/search", operation_id="searchBooks", responses=ERROR_RESPONSES)
async def books_search(
    services: ServicesDep,
    q: Annotated[str, Query(min_length=1, max_length=300)],
    lang: Annotated[str | None, Query(pattern=r"^[a-z]{2,3}$")] = None,
    limit: Annotated[int, Query(ge=1, le=40)] = 10,
    sources: Annotated[list[str] | None, Query(max_length=40)] = None,
) -> BookSearch:
    return await search_books(
        services.net, services.settings, q, lang=lang, limit=limit, sources=sources
    )


@router.get(
    "/books/search/stream",
    operation_id="streamBookSearch",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def books_search_stream(
    services: ServicesDep,
    q: Annotated[str, Query(min_length=1, max_length=300)],
    lang: Annotated[str | None, Query(pattern=r"^[a-z]{2,3}$")] = None,
    limit: Annotated[int, Query(ge=1, le=40)] = 10,
    sources: Annotated[list[str] | None, Query(max_length=40)] = None,
) -> StreamingResponse:
    """Server-Sent Events: a `source` event per source as it answers, then `done`.

    `source` carries {source: SourceStatus, results: [BookHit]}; `done` the ranked
    BookSearch. Pass `sources=` to ask only some sources again (retry).
    """

    async def events() -> AsyncIterator[str]:
        async for part in stream_books(
            services.net, services.settings, q, lang=lang, limit=limit, sources=sources
        ):
            name = "done" if isinstance(part, BookSearch) else "source"
            yield format_sse(name, part.model_dump(mode="json"))

    return StreamingResponse(events(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.get("/libraries", operation_id="listLibraries")
async def libraries(services: ServicesDep) -> LibraryList:
    settings = services.settings
    out = []
    for library in LIBRARIES:
        adapter = BY_NAME.get(library.adapter or "")
        out.append(
            LibraryOut(
                **library.model_dump(),
                searchable=bool(adapter and adapter.search),
                key_configured=bool(getattr(settings, library.key_setting, ""))
                if library.key_setting
                else None,
            )
        )
    return LibraryList(regions=list(REGIONS), libraries=out)


async def _archive(services: ServicesDep, q: str, limit: int) -> ArchiveGroup:
    try:
        page = await asyncio.wait_for(
            archive_search(services.net, build_query(q), rows=min(limit * 4, 50)), TIME_LIMIT
        )
    except TimeoutError:
        return ArchiveGroup(status="timeout")
    except Exception as exc:  # network and upstream errors become a group status
        return ArchiveGroup(status="error", message=type(exc).__name__)
    # archive.org sorts by downloads: rank by relevance, then keep the best few.
    return ArchiveGroup(items=rank_hits(page.items, q)[:limit])


async def _videos(services: ServicesDep, q: str, limit: int) -> VideoGroup:
    handler = services.registry.get("ytdlp")
    if not isinstance(handler, YtDlpHandler):
        return VideoGroup(status="error", message="video search is not available")
    try:
        found = await asyncio.wait_for(handler.search_videos(q, limit), TIME_LIMIT * 2)
    except TimeoutError:
        return VideoGroup(status="timeout")
    except HandlerError as exc:
        return VideoGroup(status="error", message=exc.code)
    except Exception as exc:  # yt-dlp and network errors
        return VideoGroup(status="error", message=type(exc).__name__)
    return VideoGroup(items=[VideoHit.model_validate(v) for v in found])


@router.get("/search", operation_id="universalSearch", responses=ERROR_RESPONSES)
async def universal_search(
    services: ServicesDep,
    q: Annotated[str, Query(min_length=1, max_length=300)],
    types: Annotated[list[SearchType] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=40)] = 10,
) -> UniversalSearch:
    wanted = set(types or ["archive", "books", "videos", "libraries"])
    net, settings = services.net, services.settings
    pending: dict[str, Awaitable[BaseModel]] = {}
    if "archive" in wanted:
        pending["archive"] = _archive(services, q, limit)
    if "books" in wanted:
        pending["books"] = search_books(net, settings, q, limit=limit)
    if "videos" in wanted:
        pending["videos"] = _videos(services, q, limit)
    if "libraries" in wanted:
        pending["libraries"] = search_books(net, settings, q, kind="libraries", limit=limit)
    names = list(pending)
    results = await asyncio.gather(*pending.values())
    return UniversalSearch(query=q, **dict(zip(names, results, strict=True)))


@router.post(
    "/convert",
    operation_id="convertJob",
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def convert(body: ConvertRequest, services: ServicesDep, user: UserDep) -> JobOut:
    if body.to not in TARGETS:  # pragma: no cover - Literal already checks
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown target")
    source = services.store.get(body.job_id)
    if source is None or (source.user_id or OWNER_ID) != user:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, {"code": "not_found", "message": "no such job"}
        )
    job = services.queue.submit(convert_url(body.job_id, body.to, body.lang), {}, user)
    return JobOut.model_validate(job)
