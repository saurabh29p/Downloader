"""Torrent handler with a fake libtorrent (the real one is an optional extra)."""

import types
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from anyget.core.net import Net
from anyget.core.settings import Settings
from anyget.handlers import torrent as torrent_mod
from anyget.handlers.base import HandlerError, JobContext
from anyget.handlers.torrent import TorrentHandler, is_torrent_link, safe_parts

FILES = [("Big Buck Bunny/bunny.mp4", 30), ("Big Buck Bunny/poster.jpg", 10)]


class FakeStatus:
    def __init__(self, handle: "FakeHandle") -> None:
        self.has_metadata = handle.ticks >= 1
        wanted = sum(
            size for (_, size), p in zip(handle.files, handle.priorities, strict=True) if p
        )
        self.total_wanted = wanted
        done = min(wanted, handle.ticks * 20)
        self.total_wanted_done = done
        self.is_finished = done >= wanted and handle.ticks >= 2
        self.is_seeding = False


class FakeStorage:
    def __init__(self, files: list[tuple[str, int]]) -> None:
        self._files = files

    def num_files(self) -> int:
        return len(self._files)

    def file_path(self, i: int) -> str:
        return self._files[i][0]

    def file_size(self, i: int) -> int:
        return self._files[i][1]


class FakeInfo:
    def __init__(self, files: list[tuple[str, int]]) -> None:
        self._files = files

    def files(self) -> FakeStorage:
        return FakeStorage(self._files)

    def name(self) -> str:
        return "Big Buck Bunny"


class FakeHandle:
    def __init__(self, params: Any, files: list[tuple[str, int]]) -> None:
        self.params = params
        self.files = files
        self.priorities = [4] * len(files)
        self.ticks = 0

    def status(self) -> FakeStatus:
        self.ticks += 1
        if self.ticks >= 2:  # "download": write the wanted files where libtorrent would
            for (path, size), prio in zip(self.files, self.priorities, strict=True):
                if prio:
                    target = Path(self.params.save_path) / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(b"x" * size)
        return FakeStatus(self)

    def torrent_file(self) -> FakeInfo:
        return FakeInfo(self.files)

    def prioritize_files(self, priorities: list[int]) -> None:
        self.priorities = priorities


def fake_libtorrent(files: list[tuple[str, int]]) -> types.ModuleType:
    lt = types.ModuleType("libtorrent")
    removed: list[Any] = []

    class Params:
        save_path = ""
        ti = None

    class Session:
        def __init__(self, settings: dict[str, Any]) -> None:
            assert settings["enable_lsd"] is False  # no local network peer discovery

        def add_torrent(self, params: Any) -> FakeHandle:
            return FakeHandle(params, files)

        def remove_torrent(self, handle: Any, flags: int = 0) -> None:
            removed.append(handle)

    lt.session = Session  # type: ignore[attr-defined]
    lt.parse_magnet_uri = lambda uri: Params()  # type: ignore[attr-defined]
    lt.add_torrent_params = Params  # type: ignore[attr-defined]
    lt.bdecode = lambda data: data  # type: ignore[attr-defined]
    lt.torrent_info = lambda decoded: ("info", decoded)  # type: ignore[attr-defined]
    lt.removed = removed  # type: ignore[attr-defined]
    return lt


@pytest.fixture(autouse=True)
def no_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(torrent_mod, "POLL", 0)


def handler(settings: Settings, lt: types.ModuleType | None) -> TorrentHandler:
    settings.torrent_enabled = True
    h = TorrentHandler(Net(settings), settings)
    h._lt = lt
    return h


def test_links_and_paths() -> None:
    assert is_torrent_link("magnet:?xt=urn:btih:abc&dn=x")
    assert is_torrent_link("https://files.test/linux.iso.torrent")
    assert not is_torrent_link("https://files.test/linux.iso")
    assert safe_parts("a/b.txt") == ["a", "b.txt"]
    for bad in ("../etc/passwd", "/abs/x", "a\\..\\b"):
        with pytest.raises(HandlerError):
            safe_parts(bad)


async def test_off_by_default_and_needs_libtorrent(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    off = TorrentHandler(Net(settings), settings)
    with pytest.raises(HandlerError) as info:
        await off.probe("magnet:?xt=urn:btih:abc")
    assert info.value.code == "unsupported"
    monkeypatch.setattr(torrent_mod, "load_libtorrent", lambda: None)
    missing = handler(settings, None)
    with pytest.raises(HandlerError) as info:
        await missing.probe("magnet:?xt=urn:btih:abc")
    assert info.value.code == "tool_missing"


async def test_probe_lists_files(settings: Settings) -> None:
    h = handler(settings, fake_libtorrent(FILES))
    probe = await h.probe("magnet:?xt=urn:btih:abc&dn=Big+Buck+Bunny")
    assert probe.title == "Big Buck Bunny" and probe.size == 40
    assert [c.label for c in probe.choices] == [p for p, _ in FILES]
    assert probe.extra["personal_use_only"] is True


async def test_download_only_chosen_files(settings: Settings) -> None:
    lt = fake_libtorrent(FILES)
    h = handler(settings, lt)
    settings.downloads_dir.mkdir(parents=True)
    job = JobContext(id="t1", url="magnet:?xt=urn:btih:abc", output_dir=settings.downloads_dir)
    seen: list[int] = []
    result = await h.download(job, {"files": ["0"]}, lambda p: seen.append(p.downloaded))
    assert [p.relative_to(settings.downloads_dir).as_posix() for p in result.paths] == [
        "Big Buck Bunny/bunny.mp4"
    ]
    assert seen[-1] == 30
    assert lt.removed  # stopped sharing when done


async def test_unsafe_torrent_paths_are_refused(settings: Settings) -> None:
    h = handler(settings, fake_libtorrent([("../escape.sh", 5)]))
    with pytest.raises(HandlerError) as info:
        await h.probe("magnet:?xt=urn:btih:abc")
    assert info.value.code == "unsafe_path"


@respx.mock
async def test_torrent_files_are_fetched_through_net(settings: Settings) -> None:
    route = respx.get("https://files.test/x.torrent").mock(
        return_value=httpx.Response(200, content=b"d4:infod4:name1:xee")
    )
    h = handler(settings, fake_libtorrent(FILES))
    probe = await h.probe("https://files.test/x.torrent")
    assert route.called and probe.extra["files"] == 2
