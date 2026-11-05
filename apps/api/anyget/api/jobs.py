"""Job endpoints: create (single or batch), list, control, delete, fetch the file."""

import re
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, model_validator

from anyget.api.deps import ERROR_RESPONSES, ServicesDep, UserDep
from anyget.core.events import sse_stream
from anyget.core.filenames import UnsafePathError, ensure_inside
from anyget.core.jobs import JobOut, JobState
from anyget.core.net import BlockedURLError
from anyget.core.router import normalize
from anyget.core.users import OWNER_ID
from anyget.handlers.ytdlp_support.archive import archive_path, contains

router = APIRouter(tags=["jobs"])

SSE_HEADERS = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}


class JobItem(BaseModel):
    """One link with its own options (e.g. a playlist entry with its index)."""

    url: str = Field(min_length=1, max_length=8192)
    options: dict[str, Any] = Field(default_factory=dict)


class CreateJobs(BaseModel):
    """Either `urls` (all share `options`) or `items` (each has its own), or both."""

    urls: list[str] = Field(default_factory=list, max_length=500)
    items: list[JobItem] = Field(default_factory=list, max_length=1000)
    options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _not_empty(self) -> "CreateJobs":
        if not self.urls and not self.items:
            raise ValueError("give at least one url or item")
        return self


class RejectedUrl(BaseModel):
    url: str
    code: str
    message: str


class CreateJobsResult(BaseModel):
    jobs: list[JobOut]
    rejected: list[RejectedUrl]
    # Items already in their download archive (saved before), not queued again.
    skipped: list[RejectedUrl] = Field(default_factory=list)


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, {"code": "not_found", "message": "no such job"})


def _owned(services: Any, job_id: str, user: str) -> Any:
    """The job if it belongs to this user; someone else's job is "not found"."""
    job = services.store.get(job_id)
    if job is None or (job.user_id or OWNER_ID) != user:
        raise _not_found()
    return job


@router.post(
    "/jobs",
    operation_id="createJobs",
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def create_jobs(body: CreateJobs, services: ServicesDep, user: UserDep) -> CreateJobsResult:
    jobs: list[JobOut] = []
    rejected: list[RejectedUrl] = []
    skipped: list[RejectedUrl] = []
    seen: set[str] = set()
    pending = [(raw, _public(body.options)) for raw in body.urls] + [
        (item.url, _public({**body.options, **item.options})) for item in body.items
    ]
    for raw, options in pending:
        if not raw.strip():
            continue
        try:
            url = normalize(raw)
            if not url.startswith("magnet:"):
                await services.net.check(url)
        except BlockedURLError as exc:
            rejected.append(RejectedUrl(url=raw, code="blocked_url", message=str(exc)))
            continue
        if url in seen:
            continue
        seen.add(url)
        if _already_saved(services, options):
            skipped.append(
                RejectedUrl(url=raw, code="already_downloaded", message="saved before; skipped")
            )
            continue
        job = services.queue.submit(url, options, user)
        jobs.append(JobOut.model_validate(job))
    return CreateJobsResult(jobs=jobs, rejected=rejected, skipped=skipped)


def _public(options: dict[str, Any]) -> dict[str, Any]:
    """Keys starting with "_" are internal (e.g. auth headers set by handlers)."""
    return {k: v for k, v in options.items() if not k.startswith("_")}


def _already_saved(services: Any, options: dict[str, Any]) -> bool:
    """True if a media item's archive id is already in its download archive."""
    key, entry = options.get("archive"), options.get("archive_id")
    if not isinstance(key, str) or not isinstance(entry, str):
        return False
    if not re.fullmatch(r"[\w.-]{1,160}", key):
        return False
    return contains(archive_path(services.settings.data_dir, key), entry)


@router.get("/jobs", operation_id="listJobs")
async def list_jobs(
    services: ServicesDep,
    user: UserDep,
    state: Annotated[list[JobState] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[JobOut]:
    jobs = services.store.list_jobs(set(state) if state else None, limit=limit, user_id=user)
    return [JobOut.model_validate(job) for job in jobs]


@router.get("/jobs/{job_id}", operation_id="getJob", responses=ERROR_RESPONSES)
async def get_job(job_id: str, services: ServicesDep, user: UserDep) -> JobOut:
    return JobOut.model_validate(_owned(services, job_id, user))


@router.post("/jobs/{job_id}/pause", operation_id="pauseJob", responses=ERROR_RESPONSES)
async def pause_job(job_id: str, services: ServicesDep, user: UserDep) -> JobOut:
    _owned(services, job_id, user)
    return JobOut.model_validate(await services.queue.pause(job_id))


@router.post("/jobs/{job_id}/resume", operation_id="resumeJob", responses=ERROR_RESPONSES)
async def resume_job(job_id: str, services: ServicesDep, user: UserDep) -> JobOut:
    _owned(services, job_id, user)
    return JobOut.model_validate(services.queue.resume(job_id))


@router.post("/jobs/{job_id}/retry", operation_id="retryJob", responses=ERROR_RESPONSES)
async def retry_job(job_id: str, services: ServicesDep, user: UserDep) -> JobOut:
    _owned(services, job_id, user)
    return JobOut.model_validate(services.queue.retry(job_id))


@router.post("/jobs/{job_id}/cancel", operation_id="cancelJob", responses=ERROR_RESPONSES)
async def cancel_job(job_id: str, services: ServicesDep, user: UserDep) -> JobOut:
    _owned(services, job_id, user)
    return JobOut.model_validate(await services.queue.cancel(job_id))


@router.delete(
    "/jobs/{job_id}",
    operation_id="deleteJob",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERROR_RESPONSES,
)
async def delete_job(
    job_id: str, services: ServicesDep, user: UserDep, delete_file: bool = False
) -> Response:
    _owned(services, job_id, user)
    await services.queue.delete(job_id, delete_file=delete_file)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/jobs/{job_id}/file",
    operation_id="getJobFile",
    response_class=FileResponse,
    responses=ERROR_RESPONSES,
)
async def get_job_file(job_id: str, services: ServicesDep, user: UserDep) -> FileResponse:
    job = _owned(services, job_id, user)
    if job.state != JobState.done or not job.rel_path:
        raise _not_found()
    root = services.settings.downloads_dir
    try:
        path = ensure_inside(root, root / job.rel_path)
    except UnsafePathError as exc:
        raise _not_found() from exc
    if not path.is_file():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, {"code": "not_found", "message": "the file was removed"}
        )
    return FileResponse(path, filename=path.name)


@router.get(
    "/jobs/{job_id}/events",
    operation_id="jobEvents",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def job_events(job_id: str, services: ServicesDep, user: UserDep) -> StreamingResponse:
    _owned(services, job_id, user)
    return StreamingResponse(
        sse_stream(services.bus, job_id, user_id=user),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.get(
    "/events",
    operation_id="allEvents",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def all_events(services: ServicesDep, user: UserDep) -> StreamingResponse:
    return StreamingResponse(
        sse_stream(services.bus, user_id=user), media_type="text/event-stream", headers=SSE_HEADERS
    )
