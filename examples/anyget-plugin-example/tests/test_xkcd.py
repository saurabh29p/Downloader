from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import respx

from anyget.core.net import Net
from anyget.core.services import Services
from anyget.core.settings import Settings
from anyget.handlers.base import JobContext
from anyget.plugins import installed, load_plugins
from anyget_plugin_example import XkcdHandler

COMIC = {
    "num": 353,
    "safe_title": "Python",
    "img": "https://imgs.xkcd.com/comics/python.png",
    "alt": "I wrote 20 short programs in Python yesterday.",
}
PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 200


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(downloads_dir=tmp_path / "dl", data_dir=tmp_path / "data", _env_file=None)


@pytest.fixture
async def net(settings: Settings) -> AsyncIterator[Net]:
    n = Net(settings)
    yield n
    await n.aclose()


@pytest.fixture(autouse=True)
def public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    async def resolve(host: str, port: int) -> list[str]:
        return ["93.184.216.34"]

    monkeypatch.setattr("anyget.core.net.resolve_host", resolve)


def test_entry_point_is_installed() -> None:
    assert "xkcd" in {ep.name for ep in installed()}


def test_plugin_loads_only_when_enabled(settings: Settings) -> None:
    services = Services.build(settings)
    assert services.registry.get("xkcd") is None  # not enabled: not loaded
    settings.plugins = ["xkcd"]
    enabled = Services.build(settings)
    assert enabled.registry.find("https://xkcd.com/353/") is enabled.registry.get("xkcd")
    assert [p.loaded for p in enabled.plugins if p.name == "xkcd"] == [True]


def test_broken_plugins_are_reported_not_fatal(settings: Settings, net: Net) -> None:
    from importlib.metadata import EntryPoint

    from anyget.handlers.registry import Registry

    settings.plugins = ["*"]
    broken = EntryPoint("broken", "anyget_plugin_example:does_not_exist", "anyget.handlers")
    report = load_plugins(Registry(), net, settings, [broken])
    assert report[0].loaded is False and "AttributeError" in (report[0].error or "")


@respx.mock
async def test_probe_and_download(net: Net, settings: Settings) -> None:
    respx.get("https://xkcd.com/353/info.0.json").mock(return_value=httpx.Response(200, json=COMIC))
    respx.head(COMIC["img"]).mock(
        return_value=httpx.Response(
            200, headers={"Content-Length": str(len(PNG)), "Content-Type": "image/png"}
        )
    )
    respx.get(COMIC["img"]).mock(return_value=httpx.Response(200, content=PNG))
    handler = XkcdHandler(net)
    assert handler.can_handle("https://xkcd.com/353/") and not handler.can_handle(
        "https://xkcd.com/about"
    )
    probe = await handler.probe("https://xkcd.com/353/")
    assert probe.title == "xkcd 353: Python" and probe.extra["license"] == "CC BY-NC 2.5"
    job = JobContext(id="x1", url="https://xkcd.com/353/", output_dir=settings.downloads_dir)
    settings.downloads_dir.mkdir(parents=True)
    result = await handler.download(job, {}, lambda _p: None)
    assert result.paths[0].name == "xkcd 353 - Python.png"
    assert result.paths[0].read_bytes() == PNG
