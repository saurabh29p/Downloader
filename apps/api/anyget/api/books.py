"""Books, worldwide libraries, universal search and conversions."""

import asyncio
from collections.abc import Awaitable
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from anyget.api.deps import ERROR_RESPONSES, ServicesDep
from anyget.books.search import BookSearch, search_books
from anyget.books.sources import BY_NAME
from anyget.core.jobs import JobOut
from anyget.handlers.archive_org import SearchHit, build_query
from anyget.handlers.archive_org import search as archive_search
from anyget.handlers.base import HandlerError
from anyget.handlers.convert import TARGETS, convert_url
from anyget.handlers.ytdlp import YtDlpHandler
from anyget.libraries.registry import LIBRARIES, REGIONS, Library

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
) -> BookSearch:
    return await search_books(services.net, services.settings, q, lang=lang, limit=limit)


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
            archive_search(services.net, build_query(q), rows=limit), TIME_LIMIT
        )
    except TimeoutError:
        return ArchiveGroup(status="timeout")
    except Exception as exc:  # network and upstream errors become a group status
        return ArchiveGroup(status="error", message=type(exc).__name__)
    return ArchiveGroup(items=page.items)


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
async def convert(body: ConvertRequest, services: ServicesDep) -> JobOut:
    if body.to not in TARGETS:  # pragma: no cover - Literal already checks
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown target")
    source = services.store.get(body.job_id)
    if source is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, {"code": "not_found", "message": "no such job"}
        )
    job = services.queue.submit(convert_url(body.job_id, body.to, body.lang), {})
    return JobOut.model_validate(job)
