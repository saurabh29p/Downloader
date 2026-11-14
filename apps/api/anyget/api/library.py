"""Offline library: list, search, tag, preview and remove downloaded files."""

import asyncio
import zipfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from anyget.api.deps import ERROR_RESPONSES, ServicesDep, UserDep
from anyget.core.filenames import UnsafePathError
from anyget.core.jobs import JobOut
from anyget.core.users import OWNER_ID
from anyget.library.epub import (
    EpubBook,
    EpubChapter,
    EpubPreview,
    EpubProtected,
    epub_book,
    epub_chapter,
    epub_preview,
)
from anyget.library.fulltext import text_of
from anyget.library.inspect import FileInfo, inspect, read_text, srt_to_vtt, subtitles_for
from anyget.library.models import Kind, LibraryItem, LibraryItemOut, LibraryPage, Licence
from anyget.library.thumbs import forget, thumbnail_for

router = APIRouter(tags=["library"])


class LibraryPatch(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    tags: list[str] | None = Field(default=None, max_length=30)


class ScanResult(BaseModel):
    added: int
    removed: int
    total: int


def _missing() -> HTTPException:
    return HTTPException(
        status.HTTP_404_NOT_FOUND, {"code": "not_found", "message": "no such library item"}
    )


def _item(services: ServicesDep, item_id: str, user: str) -> LibraryItem:
    item = services.library.get(item_id)
    if item is None or (item.user_id or OWNER_ID) != user:
        raise _missing()
    return item


@router.get("/library", operation_id="listLibrary")
async def list_library(
    services: ServicesDep,
    user: UserDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
    kind: Kind | None = None,
    tag: Annotated[str | None, Query(max_length=40)] = None,
    duplicates: bool | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 60,
    section: Annotated[str | None, Query(max_length=40)] = None,
    source: Annotated[str | None, Query(max_length=253)] = None,
    licence: Licence | None = None,
) -> LibraryPage:
    """Search titles and file text (OCR, PDF, EPUB, text files); filter by kind,
    collection (tag), section, source site and licence."""
    return services.library.search(
        q,
        kind,
        tag,
        duplicates,
        offset,
        limit,
        user_id=user,
        section=section,
        source=source,
        licence=licence,
    )


@router.post("/library/scan", operation_id="scanLibrary")
async def scan_library(services: ServicesDep) -> ScanResult:
    return ScanResult(**await services.library.scan())


@router.get("/library/by-job/{job_id}", operation_id="libraryItemForJob", responses=ERROR_RESPONSES)
async def item_for_job(job_id: str, services: ServicesDep, user: UserDep) -> LibraryItemOut:
    """The library item for a finished download's main file (Downloads → Preview)."""
    job = services.store.get(job_id)
    if job is None or (job.user_id or OWNER_ID) != user or not job.rel_path:
        raise _missing()
    item = services.library.find(job.rel_path)
    if item is None or (item.user_id or OWNER_ID) != user:
        raise _missing()
    return services.library.out(item)


@router.get("/library/{item_id}", operation_id="getLibraryItem", responses=ERROR_RESPONSES)
async def get_item(item_id: str, services: ServicesDep, user: UserDep) -> LibraryItemOut:
    return services.library.out(_item(services, item_id, user))


@router.patch("/library/{item_id}", operation_id="updateLibraryItem", responses=ERROR_RESPONSES)
async def update_item(
    item_id: str, body: LibraryPatch, services: ServicesDep, user: UserDep
) -> LibraryItemOut:
    _item(services, item_id, user)
    item = services.library.update(item_id, **body.model_dump(exclude_unset=True))
    if item is None:
        raise _missing()
    return services.library.out(item)


@router.delete(
    "/library/{item_id}",
    operation_id="deleteLibraryItem",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERROR_RESPONSES,
)
async def delete_item(
    item_id: str, services: ServicesDep, user: UserDep, delete_file: bool = False
) -> Response:
    _item(services, item_id, user)
    forget(services.settings.data_dir, item_id)
    if not services.library.delete(item_id, delete_file=delete_file):
        raise _missing()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/library/{item_id}/file",
    operation_id="getLibraryFile",
    response_class=FileResponse,
    responses=ERROR_RESPONSES,
)
async def get_file(
    item_id: str, services: ServicesDep, user: UserDep, download: bool = False
) -> FileResponse:
    """The file itself; Range requests work, so video and audio can seek."""
    item = _item(services, item_id, user)
    try:
        path = services.library.path_of(item)
    except UnsafePathError as exc:
        raise _missing() from exc
    if not path.is_file():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, {"code": "not_found", "message": "the file was removed"}
        )
    info = inspect(path)
    # The sniffed type, so a file without (or with a wrong) extension still plays;
    # HTML and SVG keep their usual type but run sandboxed (CSP below).
    media_type = info.mime if info.preview not in ("none", "text") else None
    return FileResponse(
        path,
        filename=path.name,
        media_type=media_type,
        content_disposition_type="attachment" if download else "inline",
        # Untrusted files (HTML, SVG) must not run scripts on AnyGet's origin.
        headers={
            "Content-Security-Policy": "sandbox",
            "X-Content-Type-Options": "nosniff",
            # The Library page shows PDFs in an iframe on the same site.
            "X-Frame-Options": "SAMEORIGIN",
        },
    )


@router.get(
    "/library/{item_id}/thumb",
    operation_id="getLibraryThumb",
    response_class=FileResponse,
    responses={**ERROR_RESPONSES, 204: {"description": "This file has no picture"}},
)
async def get_thumb(item_id: str, services: ServicesDep, user: UserDep) -> Response:
    """A 320 px WebP picture of the file (video frame, PDF page, cover art, image)."""
    item = _item(services, item_id, user)
    try:
        source = services.library.path_of(item)
    except UnsafePathError as exc:
        raise _missing() from exc
    thumb = await thumbnail_for(services.settings.data_dir, item.id, source, item.kind)
    if thumb is None:
        # "No picture" is an answer, not an error: an empty 204 (cached) instead of a 404
        # that browsers log as a failed request. Unknown items still answer 404.
        return Response(status_code=204, headers={"Cache-Control": "private, max-age=86400"})
    return FileResponse(
        thumb, media_type="image/webp", headers={"Cache-Control": "private, max-age=86400"}
    )


def _path(services: ServicesDep, item: LibraryItem) -> Path:
    try:
        path = services.library.path_of(item)
    except UnsafePathError as exc:
        raise _missing() from exc
    if not path.is_file():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, {"code": "not_found", "message": "the file was removed"}
        )
    return path


def _unsupported(message: str) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT, {"code": "unsupported", "message": message}
    )


def _protected() -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        {"code": "protected", "message": "this file is DRM-protected and can't be opened"},
    )


@router.get("/library/{item_id}/info", operation_id="libraryFileInfo", responses=ERROR_RESPONSES)
async def file_info(item_id: str, services: ServicesDep, user: UserDep) -> FileInfo:
    """What the file really is (from its first bytes) and how AnyGet can show it."""
    item = _item(services, item_id, user)
    try:
        path = services.library.path_of(item)
    except UnsafePathError:
        return inspect(Path("/nonexistent"))
    return inspect(path)


class TextPage(BaseModel):
    text: str
    offset: int
    next_offset: int | None
    size: int


TEXT_PAGE = 256 * 1024


@router.get("/library/{item_id}/text", operation_id="libraryText", responses=ERROR_RESPONSES)
async def file_text(
    item_id: str,
    services: ServicesDep,
    user: UserDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1024, le=1024 * 1024)] = TEXT_PAGE,
) -> TextPage:
    """A page of a text file (UTF-8), so big logs and books load piece by piece.
    HTML comes back as its visible text: tags and scripts never run."""
    path = _path(services, _item(services, item_id, user))
    info = inspect(path)
    if info.preview != "text":
        raise _unsupported("this file is not text")
    size = info.size
    if offset >= size:
        return TextPage(text="", offset=offset, next_offset=None, size=size)
    if info.mime == "text/html":
        if offset > 0:
            return TextPage(text="", offset=offset, next_offset=None, size=size)
        return TextPage(text=text_of(path)[: limit * 2], offset=0, next_offset=None, size=size)
    text, next_offset = await asyncio.to_thread(read_text, path, offset, limit)
    return TextPage(text=text, offset=offset, next_offset=next_offset, size=size)


@router.get("/library/{item_id}/epub", operation_id="libraryEpub", responses=ERROR_RESPONSES)
async def epub_contents(item_id: str, services: ServicesDep, user: UserDep) -> EpubBook:
    """An EPUB's title and chapters (from its table of contents when it has one)."""
    path = _path(services, _item(services, item_id, user))
    try:
        return await asyncio.to_thread(epub_book, path)
    except EpubProtected as exc:
        raise _protected() from exc
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise _unsupported(f"this EPUB can't be read: {type(exc).__name__}") from exc


@router.get(
    "/library/{item_id}/epub/{index}",
    operation_id="libraryEpubChapter",
    responses=ERROR_RESPONSES,
)
async def epub_contents_chapter(
    item_id: str, index: int, services: ServicesDep, user: UserDep
) -> EpubChapter:
    """One chapter as plain text blocks (headings, paragraphs, lists): no HTML."""
    path = _path(services, _item(services, item_id, user))
    try:
        return await asyncio.to_thread(epub_chapter, path, index)
    except EpubProtected as exc:
        raise _protected() from exc
    except KeyError as exc:
        raise _missing() from exc
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise _unsupported(f"this chapter can't be read: {type(exc).__name__}") from exc


@router.get(
    "/library/{item_id}/subtitles/{index}",
    operation_id="librarySubtitles",
    response_class=PlainTextResponse,
    responses=ERROR_RESPONSES,
)
async def subtitles(
    item_id: str, index: int, services: ServicesDep, user: UserDep
) -> PlainTextResponse:
    """A subtitle file saved next to the video, as WebVTT (SRT is converted)."""
    path = _path(services, _item(services, item_id, user))
    found = subtitles_for(path)
    if not 0 <= index < len(found) or found[index].stat().st_size > 5 * 1024 * 1024:
        raise _missing()
    text = found[index].read_text(encoding="utf-8", errors="replace")
    return PlainTextResponse(
        srt_to_vtt(text),
        media_type="text/vtt",
        headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )


@router.get(
    "/library/{item_id}/preview", operation_id="previewLibraryItem", responses=ERROR_RESPONSES
)
async def preview_item(item_id: str, services: ServicesDep, user: UserDep) -> EpubPreview:
    """Short text preview: the first chapters of an EPUB, or the start of a text file."""
    item = _item(services, item_id, user)
    path = _path(services, item)
    info = inspect(path)
    if info.preview == "text":
        text, more = await asyncio.to_thread(read_text, path, 0, 20_000)
        if info.mime == "text/html":
            text, more = text_of(path)[:20_000], None
        return EpubPreview(title=item.title, text=text, truncated=more is not None)
    if info.preview != "epub":
        raise _unsupported("text previews are for EPUB and text files")
    try:
        return epub_preview(path)
    except EpubProtected as exc:
        raise _protected() from exc
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, UnsafePathError) as exc:
        raise _unsupported(f"this EPUB cannot be previewed: {exc}") from exc


@router.post(
    "/library/{item_id}/redownload",
    operation_id="redownloadLibraryItem",
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def redownload(item_id: str, services: ServicesDep, user: UserDep) -> JobOut:
    item = _item(services, item_id, user)
    if not item.source_url:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"code": "unsupported", "message": "this file has no source link"},
        )
    await services.net.check(item.source_url)
    return JobOut.model_validate(services.queue.submit(item.source_url, {}, user))
