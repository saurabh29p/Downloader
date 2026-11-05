"""Watches: channels, playlists and archive.org collections checked on a schedule."""

from fastapi import APIRouter, HTTPException, Response, status

from anyget.api.deps import ERROR_RESPONSES, ServicesDep, UserDep
from anyget.core.users import OWNER_ID
from anyget.watch.models import WatchIn, WatchOut, WatchPatch, WatchRunResult
from anyget.watch.runner import out

router = APIRouter(tags=["watch"])


def _missing() -> HTTPException:
    return HTTPException(
        status.HTTP_404_NOT_FOUND, {"code": "not_found", "message": "no such watch"}
    )


def _owned(services: ServicesDep, watch_id: str, user: str) -> None:
    watch = services.watches.get(watch_id)
    if watch is None or (watch.user_id or OWNER_ID) != user:
        raise _missing()


@router.get("/watches", operation_id="listWatches")
async def list_watches(services: ServicesDep, user: UserDep) -> list[WatchOut]:
    return [out(w) for w in services.watches.all(user)]


@router.post(
    "/watches",
    operation_id="createWatch",
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def create_watch(body: WatchIn, services: ServicesDep, user: UserDep) -> WatchOut:
    return out(await services.watches.create(body, user))


@router.patch("/watches/{watch_id}", operation_id="updateWatch", responses=ERROR_RESPONSES)
async def update_watch(
    watch_id: str, body: WatchPatch, services: ServicesDep, user: UserDep
) -> WatchOut:
    _owned(services, watch_id, user)
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
async def delete_watch(watch_id: str, services: ServicesDep, user: UserDep) -> Response:
    _owned(services, watch_id, user)
    if not services.watches.delete(watch_id):
        raise _missing()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/watches/{watch_id}/run", operation_id="runWatch", responses=ERROR_RESPONSES)
async def run_watch(watch_id: str, services: ServicesDep, user: UserDep) -> WatchRunResult:
    _owned(services, watch_id, user)
    return await services.watches.run(watch_id)
