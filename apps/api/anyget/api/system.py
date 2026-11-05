"""Health and version endpoints."""

import platform
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from anyget import __version__
from anyget.core.tools import ToolVersions, tool_versions

router = APIRouter(tags=["system"])


class Health(BaseModel):
    status: Literal["ok"]
    components: ToolVersions


class VersionInfo(BaseModel):
    name: str
    version: str
    python: str


@router.get("/health", operation_id="getHealth")
async def health() -> Health:
    return Health(status="ok", components=tool_versions())


@router.get("/version", operation_id="getVersion")
async def version() -> VersionInfo:
    return VersionInfo(name="anyget", version=__version__, python=platform.python_version())
