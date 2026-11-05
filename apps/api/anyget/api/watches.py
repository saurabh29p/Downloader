"""Watches: channels, playlists and archive.org collections checked on a schedule."""

from fastapi import APIRouter, HTTPException, Response, status

from anyget.api.deps import ERROR_RESPONSES, ServicesDep
from anyget.watch.models import WatchIn, WatchOut, WatchPatch, WatchRunResult
from anyget.watch.runner import out

router = APIRouter(tags=["watch"])


def _missing() -> HTTPException:
    return HTTPException(
        status.HTTP_404_NOT_FOUND, {"code": "not_found", "message": "no such watch"}
    )


@router.get("/watches", operation_id="listWatches")
async def list_watches(services: ServicesDep) -> list[WatchOut]:
    return [out(w) for w in services.watches.all()]


@router.post(
    "/watches",
    operation_id="createWatch",
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def create_watch(body: WatchIn, services: ServicesDep) -> WatchOut:
    return out(await services.watches.create(body))


@router.patch("/watches/{watch_id}", operation_id="updateWatch", responses=ERROR_RESPONSES)
async def update_watch(watch_id: str, body: WatchPatch, services: ServicesDep) -> WatchOut:
    watch = services.watches.update(watch_id, **body.model_dump(exclude_unset=True))
    if watch is None:
        raise _missing()
    return out(watch)


@router.delete(
    "/watches/{watch_id}",
    operation_id="deleteWatch",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERROR_RESPONSES,
)
async def delete_watch(watch_id: str, services: ServicesDep) -> Response:
    if not services.watches.delete(watch_id):
        raise _missing()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/watches/{watch_id}/run", operation_id="runWatch", responses=ERROR_RESPONSES)
async def run_watch(watch_id: str, services: ServicesDep) -> WatchRunResult:
    if services.watches.get(watch_id) is None:
        raise _missing()
    return await services.watches.run(watch_id)
