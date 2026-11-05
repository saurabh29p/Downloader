"""Settings endpoints. Cookies and API keys live in Connections (api/connections.py)."""

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from anyget.api.deps import ERROR_RESPONSES, ServicesDep
from anyget.core.net import BlockedURLError
from anyget.core.settings_store import SettingsUpdate, SettingsView
from anyget.core.tools import tool_versions

router = APIRouter(tags=["settings"])


@router.get("/settings", operation_id="getSettings")
async def get_settings_view(services: ServicesDep) -> SettingsView:
    """Current settings (API keys and cookies are in Connections)."""
    return services.settings_store.view()


@router.put("/settings", operation_id="putSettings", responses=ERROR_RESPONSES)
async def put_settings(body: SettingsUpdate, services: ServicesDep) -> SettingsView:
    changed = services.settings_store.save(body)
    if {"max_concurrent_downloads", "max_per_host", "host_limits"} & set(changed):
        services.queue.reconfigure()
    return services.settings_store.view()


class YtDlpVersion(BaseModel):
    installed: str | None
    latest: str | None
    update_available: bool
    command: str


@router.get("/settings/ytdlp", operation_id="checkYtDlp")
async def ytdlp_version(services: ServicesDep) -> YtDlpVersion:
    """Compare the installed yt-dlp with PyPI. AnyGet never updates itself."""
    installed = tool_versions().yt_dlp
    latest = None
    try:
        response = await services.net.request("GET", "https://pypi.org/pypi/yt-dlp/json")
        if response.status_code == 200:
            latest = str(response.json().get("info", {}).get("version") or "") or None
    except (httpx.HTTPError, ValueError, BlockedURLError):
        latest = None
    return YtDlpVersion(
        installed=installed,
        latest=latest,
        update_available=bool(installed and latest and installed != latest),
        command="docker compose build --pull api && docker compose up -d  (or: uv lock -P yt-dlp)",
    )
