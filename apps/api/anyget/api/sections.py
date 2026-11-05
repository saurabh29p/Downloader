"""Sections: GET /api/sections and /api/sections/{id} (pre-built searches and links)."""

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel

from anyget.api.deps import ERROR_RESPONSES, ServicesDep
from anyget.universal.sections import BY_ID, SECTIONS, Section

router = APIRouter(tags=["sections"])


class PresetOut(BaseModel):
    id: str
    query: str


class LinkOut(BaseModel):
    label: str
    url: str


class SectionOut(BaseModel):
    id: str
    media: list[str]
    sources: list[str]
    presets: list[PresetOut]
    links: list[LinkOut]
    parent: str | None = None
    pages: list[str]
    # Sources that need a free key the user hasn't added yet ("tmdb").
    needs_key: list[str]


def _out(section: Section, services: ServicesDep, q: str | None = None) -> SectionOut:
    needs = ["tmdb"] if "tmdb" in section.sources and not services.settings.tmdb_key else []
    # Without `q` the "{q}" placeholder stays, for the web to fill in.
    encoded = quote(q) if q else "{q}"
    return SectionOut(
        id=section.id,
        media=list(section.media),
        sources=list(section.sources),
        presets=[PresetOut(id=p.id, query=p.query) for p in section.presets],
        links=[
            LinkOut(label=link.label, url=link.url.replace("{q}", encoded))
            for link in section.links
        ],
        parent=section.parent,
        pages=list(section.pages),
        needs_key=needs,
    )


@router.get("/sections", operation_id="listSections")
async def list_sections(services: ServicesDep) -> list[SectionOut]:
    return [_out(s, services) for s in SECTIONS]


@router.get("/sections/{section_id}", operation_id="getSection", responses=ERROR_RESPONSES)
async def get_section(
    services: ServicesDep,
    section_id: Annotated[str, Path(pattern=r"^[a-z]{2,20}$")],
    q: Annotated[str | None, Query(max_length=300)] = None,
) -> SectionOut:
    """One section; with `q`, its "Search on …" links carry that query."""
    section = BY_ID.get(section_id)
    if section is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, {"code": "not_found", "message": "no such section"}
        )
    return _out(section, services, q)
