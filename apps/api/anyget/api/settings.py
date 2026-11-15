"""Settings endpoints. Cookies and API keys live in Connections (api/connections.py)."""

from fastapi import APIRouter
from pydantic import BaseModel

from anyget.api.deps import ERROR_RESPONSES, ServicesDep
from anyget.core import engine
from anyget.core.settings_store import SettingsUpdate, SettingsView

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
    # The yt-dlp this server runs now.
    installed: str | None
    latest: str | None
    update_available: bool
    # The yt-dlp in the image; and one installed by "Update yt-dlp" (data/engine).
    bundled: str | None = None
    updated: str | None = None
    # An update is installed but AnyGet hasn't restarted to use it yet.
    restart_needed: bool = False
    # The other way to update: a newer image.
    command: str


def _version_out(status: engine.EngineStatus) -> YtDlpVersion:
    return YtDlpVersion(
        installed=status.running,
        latest=status.latest,
        update_available=status.update_available,
        bundled=status.bundled,
        updated=status.updated,
        restart_needed=status.restart_needed,
        command="docker compose build --pull api && docker compose up -d  (or: uv lock -P yt-dlp)",
    )


@router.get("/settings/ytdlp", operation_id="checkYtDlp")
async def ytdlp_version(services: ServicesDep) -> YtDlpVersion:
    """Compare the yt-dlp in use with the latest on PyPI."""
    return _version_out(await engine.status(services.net, services.settings.data_dir))


@router.post("/settings/ytdlp/update", operation_id="updateYtDlp", responses=ERROR_RESPONSES)
async def update_ytdlp(services: ServicesDep) -> YtDlpVersion:
    """Install the latest yt-dlp into the data folder (SHA-256 checked, guard checked).
    It is used after AnyGet restarts."""
    return _version_out(await engine.update(services.net, services.settings.data_dir))
