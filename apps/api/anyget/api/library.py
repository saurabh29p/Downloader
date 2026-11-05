"""Offline library: list, search, tag, preview and remove downloaded files."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from anyget.api.deps import ERROR_RESPONSES, ServicesDep, UserDep
from anyget.core.filenames import UnsafePathError
from anyget.core.jobs import JobOut
from anyget.core.users import OWNER_ID
from anyget.library.epub import EpubPreview, epub_preview
from anyget.library.models import Kind, LibraryItem, LibraryItemOut, LibraryPage

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
) -> LibraryPage:
    return services.library.search(q, kind, tag, duplicates, offset, limit, user_id=user)


@router.post("/library/scan", operation_id="scanLibrary")
async def scan_library(services: ServicesDep) -> ScanResult:
    return ScanResult(**await services.library.scan())


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
    return FileResponse(
        path,
        filename=path.name,
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
    "/library/{item_id}/preview", operation_id="previewLibraryItem", responses=ERROR_RESPONSES
)
async def preview_item(item_id: str, services: ServicesDep, user: UserDep) -> EpubPreview:
    """Text preview for EPUB files (other kinds preview the file itself)."""
    item = _item(services, item_id, user)
    if item.kind != "epub":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"code": "unsupported", "message": "text previews are for EPUB files"},
        )
    try:
        return epub_preview(services.library.path_of(item))
    except (OSError, ValueError, KeyError, UnsafePathError) as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"code": "unsupported", "message": f"this EPUB cannot be previewed: {exc}"},
        ) from exc


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
