"""POST /api/probe: what is behind a link, before downloading."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from anyget.api.deps import ERROR_RESPONSES, ServicesDep
from anyget.handlers.base import Choice

router = APIRouter(tags=["probe"])


class ProbeRequest(BaseModel):
    url: str = Field(min_length=1, max_length=8192)
    # Handler-specific, e.g. {"tab": "shorts", "max_entries": 50} for channels.
    options: dict[str, Any] = Field(default_factory=dict)


class ProbeResult(BaseModel):
    url: str
    normalized_url: str
    handler: str
    title: str
    size: int | None
    thumbnail: str | None
    choices: list[Choice]
    extra: dict[str, Any]


@router.post("/probe", operation_id="probeUrl", responses=ERROR_RESPONSES)
async def probe(body: ProbeRequest, services: ServicesDep) -> ProbeResult:
    normalized, handler = await services.router.resolve(body.url)
    result = await handler.probe(normalized, body.options or None)
    return ProbeResult(
        url=body.url,
        normalized_url=normalized,
        handler=result.handler,
        title=result.title,
        size=result.size,
        thumbnail=result.thumbnail,
        choices=result.choices,
        extra=result.extra,
    )
