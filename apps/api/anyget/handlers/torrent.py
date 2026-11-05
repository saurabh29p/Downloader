"""Torrents (magnet links and .torrent files) with libtorrent. Off by default.

Personal use only: download what you are allowed to share (Linux images, public
domain films, Creative Commons releases…). Torrent peers are arbitrary internet
addresses, so this traffic is outside AnyGet's SSRF guard; that is why it must be
turned on in Settings (ANYGET_TORRENT_ENABLED) and needs the optional extra:
`uv sync --extra torrent`. The .torrent file itself is fetched through Net.

After the download AnyGet stops sharing unless "keep seeding" is on.
"""

import asyncio
import contextlib
import importlib
import shutil
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any
from urllib.parse import parse_qs, urlsplit

from anyget.core.filenames import UnsafePathError, ensure_inside, safe_join, sanitize_filename
from anyget.core.net import Net
from anyget.core.settings import Settings
from anyget.handlers.base import (
    Choice,
    DownloadResult,
    HandlerError,
    JobRef,
    Probe,
    Progress,
    ProgressCallback,
    work_dir,
)

METADATA_TIMEOUT = 90.0
MAX_TORRENT_FILE = 10 * 1024 * 1024
POLL = 1.0


def load_libtorrent() -> ModuleType | None:
    try:
        return importlib.import_module("libtorrent")
    except ImportError:
        return None


def is_torrent_link(url: str) -> bool:
    if url.lower().startswith("magnet:?"):
        return True
    parts = urlsplit(url)
    return parts.scheme in ("http", "https") and parts.path.lower().endswith(".torrent")


def magnet_name(url: str) -> str | None:
    query = parse_qs(url.split("?", 1)[1]) if "?" in url else {}
    names = query.get("dn") or []
    return names[0] if names else None


def safe_parts(path: str) -> list[str]:
    """A file path from torrent metadata, refused if it tries to leave the folder."""
    pure = PurePosixPath(path.replace("\\", "/"))
    if pure.is_absolute() or any(part in ("..", "") for part in pure.parts):
        raise HandlerError("unsafe_path", f"the torrent lists an unsafe path: {path}")
    return list(pure.parts)


class TorrentHandler:
    name = "torrent"

    def __init__(self, net: Net, settings: Settings) -> None:
        self.net = net
        self.settings = settings
        self._lt: ModuleType | None = None
        self._session: Any = None

    def can_handle(self, url: str) -> bool:
        return is_torrent_link(url)

    # ----- libtorrent ------------------------------------------------------

    def _lib(self) -> ModuleType:
        if not self.settings.torrent_enabled:
            raise HandlerError(
                "unsupported",
                "torrents are turned off; turn them on in Settings (personal use only)",
            )
        if self._lt is None:
            self._lt = load_libtorrent()
        if self._lt is None:
            raise HandlerError("tool_missing", "torrents need libtorrent: uv sync --extra torrent")
        return self._lt

    def _ses(self) -> Any:
        lt = self._lib()
        if self._session is None:
            self._session = lt.session(
                {
                    "listen_interfaces": "0.0.0.0:6881,[::]:6881",
                    "enable_dht": True,
                    "enable_lsd": False,  # no local-network peer discovery
                    "enable_upnp": False,
                    "enable_natpmp": False,
                    "alert_mask": 0,
                }
            )
        return self._session

    async def _params(self, url: str, save_path: Path) -> Any:
        lt = self._lib()
        if url.lower().startswith("magnet:"):
            params = lt.parse_magnet_uri(url)
        else:
            await self.net.check(url)
            response = await self.net.request("GET", url)
            if response.status_code >= 400:
                raise HandlerError("upstream", f"the .torrent link answered {response.status_code}")
            if len(response.content) > MAX_TORRENT_FILE:
                raise HandlerError("unsupported", "that .torrent file is too large")
            params = lt.add_torrent_params()
            params.ti = lt.torrent_info(lt.bdecode(response.content))
        params.save_path = str(save_path)
        return params

    async def _metadata(self, handle: Any) -> Any:
        waited = 0.0
        while not handle.status().has_metadata:
            if waited >= METADATA_TIMEOUT:
                raise HandlerError("upstream", "no peers sent this torrent's file list in time")
            await asyncio.sleep(POLL)
            waited += POLL
        return handle.torrent_file()

    @staticmethod
    def _files(info: Any) -> list[tuple[int, str, int]]:
        storage = info.files()
        return [
            (index, storage.file_path(index), int(storage.file_size(index)))
            for index in range(storage.num_files())
        ]

    # ----- contract --------------------------------------------------------

    async def probe(self, url: str, options: dict[str, Any] | None = None) -> Probe:
        ses = self._ses()
        scratch = work_dir(self.settings.downloads_dir, "torrent-probe")
        scratch.mkdir(parents=True, exist_ok=True)
        params = await self._params(url, scratch)
        handle = ses.add_torrent(params)
        try:
            info = await self._metadata(handle)
        finally:
            ses.remove_torrent(handle, 1)  # 1 = delete files: nothing was meant to download
            shutil.rmtree(scratch, ignore_errors=True)
        files = self._files(info)
        for _, path, _ in files:
            safe_parts(path)
        return Probe(
            url=url,
            handler=self.name,
            title=str(info.name() or magnet_name(url) or "torrent"),
            size=sum(size for _, _, size in files),
            choices=[
                Choice(id=str(index), label=path, kind="file", size=size, default=True)
                for index, path, size in files
            ],
            extra={"kind": "torrent", "files": len(files), "personal_use_only": True},
        )

    async def download(
        self, job: JobRef, options: dict[str, Any], progress_cb: ProgressCallback
    ) -> DownloadResult:
        ses = self._ses()
        root = Path(job.output_dir)
        params = await self._params(job.url, root)
        handle = ses.add_torrent(params)
        finished = False
        try:
            info = await self._metadata(handle)
            files = self._files(info)
            for _, path, _ in files:
                safe_parts(path)
            wanted = options.get("files")
            chosen = {str(w) for w in wanted} if isinstance(wanted, list) and wanted else None
            priorities = [4 if chosen is None or str(i) in chosen else 0 for i, _, _ in files]
            if not any(priorities):
                raise HandlerError("not_found", "none of the chosen files are in this torrent")
            handle.prioritize_files(priorities)
            while True:
                status = handle.status()
                total = int(status.total_wanted) or None
                progress_cb(Progress(downloaded=int(status.total_wanted_done), total=total))
                if status.is_finished or status.is_seeding:
                    break
                await asyncio.sleep(POLL)
            finished = True
        finally:
            if not (finished and self.settings.torrent_seed):
                # Paused/canceled jobs keep their data: libtorrent re-checks and resumes.
                with contextlib.suppress(Exception):
                    ses.remove_torrent(handle)
        paths = []
        for index, path, _ in files:
            if priorities[index] == 0:
                continue
            target = safe_join(root, *[sanitize_filename(p) for p in safe_parts(path)])
            try:
                on_disk = ensure_inside(root, root / Path(*safe_parts(path)))
            except UnsafePathError as exc:
                raise HandlerError(
                    "unsafe_path", "a torrent file landed outside the folder"
                ) from exc
            if on_disk.is_file():
                if on_disk != target:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    on_disk.replace(target)
                paths.append(target)
        return DownloadResult(paths=paths)
