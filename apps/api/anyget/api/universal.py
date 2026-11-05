"""One box for everything: GET/POST /api/universal streams a plan, results, then done.

Server-Sent Events, in order:
- `plan`: the RouterPlan (kind, intent, media, language, queries; `urls` for links)
- `source`: one per source as it answers: SourceDone with ResultCards (best first)
- `done`: UniversalDone with counts per media
Links (kind "url") end after `plan`: the web probes them as before.
"""

from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from anyget.api.deps import ServicesDep
from anyget.core.events import SSE_HEADERS, format_sse
from anyget.handlers.ytdlp import YtDlpHandler
from anyget.universal.engine import Engine
from anyget.universal.keyword_router import plan as keyword_plan
from anyget.universal.models import UniversalDone

router = APIRouter(tags=["universal"])

SectionId = Literal[
    "movies",
    "books",
    "music",
    "video",
    "declassified",
    "maps",
    "newspapers",
    "photos",
    "manuscripts",
    "more",
]
SSE_RESPONSE: dict[int | str, dict[str, Any]] = {200: {"content": {"text/event-stream": {}}}}


class UniversalIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    section: SectionId | None = None


def _engine(services: ServicesDep) -> Engine:
    handler = services.registry.get("ytdlp")
    videos = handler.search_videos if isinstance(handler, YtDlpHandler) else None
    return Engine(services.net, services.settings, videos)


def _stream(services: ServicesDep, text: str, section: str | None) -> StreamingResponse:
    planned = keyword_plan(text, section)
    allowed = set(services.settings.universal_sources)
    if allowed:
        planned.queries = [q for q in planned.queries if q.source in allowed]

    async def events() -> AsyncIterator[str]:
        yield format_sse("plan", planned.model_dump(mode="json"))
        if planned.kind == "url":
            yield format_sse("done", UniversalDone(total=0, counts={}).model_dump())
            return
        async for part in _engine(services).stream(planned):
            name = "done" if isinstance(part, UniversalDone) else "source"
            yield format_sse(name, part.model_dump(mode="json"))

    return StreamingResponse(events(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.get(
    "/universal",
    operation_id="universalStream",
    response_class=StreamingResponse,
    responses=SSE_RESPONSE,
)
async def universal_get(
    services: ServicesDep,
    q: Annotated[str, Query(min_length=1, max_length=2000)],
    section: SectionId | None = None,
) -> StreamingResponse:
    """The same stream as POST, for EventSource (which can only GET)."""
    return _stream(services, q, section)


@router.post(
    "/universal",
    operation_id="universalPost",
    response_class=StreamingResponse,
    responses=SSE_RESPONSE,
)
async def universal_post(body: UniversalIn, services: ServicesDep) -> StreamingResponse:
    return _stream(services, body.text, body.section)
