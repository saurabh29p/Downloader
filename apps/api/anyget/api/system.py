"""Health and version endpoints."""

import platform
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from anyget import __version__

router = APIRouter(tags=["system"])


class Health(BaseModel):
    status: Literal["ok"]


class VersionInfo(BaseModel):
    name: str
    version: str
    python: str


@router.get("/health", operation_id="getHealth")
async def health() -> Health:
    return Health(status="ok")


@router.get("/version", operation_id="getVersion")
async def version() -> VersionInfo:
    return VersionInfo(name="anyget", version=__version__, python=platform.python_version())
