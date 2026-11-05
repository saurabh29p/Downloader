"""Health and version endpoints."""

import platform
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from anyget import __version__
from anyget.api.deps import ServicesDep
from anyget.core.tools import ToolVersions, tool_versions
from anyget.handlers.torrent import load_libtorrent
from anyget.plugins import PluginInfo

router = APIRouter(tags=["system"])


class Health(BaseModel):
    status: Literal["ok"]
    components: ToolVersions
    plugins: list[PluginInfo] = []
    torrent: bool = False


class VersionInfo(BaseModel):
    name: str
    version: str
    python: str


@router.get("/health", operation_id="getHealth")
async def health(services: ServicesDep) -> Health:
    return Health(
        status="ok",
        components=tool_versions(),
        plugins=services.plugins,
        torrent=services.settings.torrent_enabled and load_libtorrent() is not None,
    )


@router.get("/version", operation_id="getVersion")
async def version() -> VersionInfo:
    return VersionInfo(name="anyget", version=__version__, python=platform.python_version())
