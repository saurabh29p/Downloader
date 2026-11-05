"""archive.org search and items, and Wayback Machine snapshot lists."""

from typing import Annotated

from fastapi import APIRouter, Query

from anyget.api.deps import ERROR_RESPONSES, ServicesDep
from anyget.handlers.archive_org import (
    ArchiveItem,
    ArchiveOrgHandler,
    SearchPage,
    build_query,
    downloadable,
    format_summary,
    scrape,
    search,
)
from anyget.handlers.wayback import SnapshotList, list_snapshots

router = APIRouter(tags=["archive"])


def _archive(services: ServicesDep) -> ArchiveOrgHandler:
    handler = services.registry.get("archive_org")
    assert isinstance(handler, ArchiveOrgHandler)  # noqa: S101 (registered in services)
    return handler


class ArchiveItemOut(ArchiveItem):
    thumbnail_url: str
    formats: list[dict[str, object]]
    details_url: str


@router.get("/archive/search", operation_id="archiveSearch", responses=ERROR_RESPONSES)
async def archive_search(
    services: ServicesDep,
    q: Annotated[str, Query(max_length=500)] = "",
    mediatype: Annotated[str | None, Query(max_length=40)] = None,
    collection: Annotated[str | None, Query(max_length=100)] = None,
    year_from: Annotated[int | None, Query(ge=0, le=9999)] = None,
    year_to: Annotated[int | None, Query(ge=0, le=9999)] = None,
    language: Annotated[str | None, Query(max_length=40)] = None,
    creator: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1, le=100)] = 1,
    rows: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
    deep: bool = False,
) -> SearchPage:
    """First pages use advancedsearch; `deep=true` or a `cursor` walks with the scrape API."""
    query = build_query(
        q,
        mediatype=mediatype,
        collection=collection,
        year_from=year_from,
        year_to=year_to,
        language=language,
        creator=creator,
    )
    if deep or cursor:
        return await scrape(services.net, query, cursor=cursor)
    return await search(services.net, query, page=page, rows=rows)


@router.get("/archive/items/{identifier}", operation_id="archiveItem", responses=ERROR_RESPONSES)
async def archive_item(identifier: str, services: ServicesDep) -> ArchiveItemOut:
    item = await _archive(services).item(identifier)
    files = downloadable(item)
    return ArchiveItemOut(
        **item.model_dump(exclude={"files"}),
        files=files,
        thumbnail_url=item.thumbnail,
        formats=format_summary(files),
        details_url=f"https://archive.org/details/{item.identifier}",
    )


@router.get("/wayback/snapshots", operation_id="waybackSnapshots", responses=ERROR_RESPONSES)
async def wayback_snapshots(
    services: ServicesDep,
    url: Annotated[str, Query(min_length=1, max_length=2000)],
    year_from: Annotated[int | None, Query(ge=1990, le=2100)] = None,
    year_to: Annotated[int | None, Query(ge=1990, le=2100)] = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
) -> SnapshotList:
    target = url.strip()
    await services.net.check(target if "://" in target else f"https://{target}")
    return await list_snapshots(
        services.net, target, year_from=year_from, year_to=year_to, limit=limit
    )
