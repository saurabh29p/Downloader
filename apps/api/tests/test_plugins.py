"""The plugin loader: allowlist, priority, broken plugins."""

from importlib.metadata import EntryPoint
from pathlib import Path

import pytest

from anyget.core.net import Net
from anyget.core.settings import Settings
from anyget.handlers.registry import Registry
from anyget.plugins import DEFAULT_PRIORITY, load_plugins

PLUGIN = """
class Echo:
    name = "echo"
    def can_handle(self, url): return url.startswith("https://echo.test/")
    async def probe(self, url, options=None): raise NotImplementedError
    async def download(self, job, options, cb): raise NotImplementedError

class Early(Echo):
    name = "early"
    priority = 5

def make(net, settings): return Echo()
def make_early(net, settings): return Early()
def broken(net, settings): raise RuntimeError("boom")
not_a_handler = lambda net, settings: object()
"""


@pytest.fixture
def plugin_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    (tmp_path / "fake_anyget_plugin.py").write_text(PLUGIN, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    return "fake_anyget_plugin"


def eps(module: str, *pairs: tuple[str, str]) -> list[EntryPoint]:
    return [EntryPoint(name, f"{module}:{attr}", "anyget.handlers") for name, attr in pairs]


def test_plugins_need_to_be_enabled(plugin_module: str, settings: Settings) -> None:
    registry = Registry()
    report = load_plugins(registry, Net(settings), settings, eps(plugin_module, ("echo", "make")))
    assert report[0].loaded is False and "ANYGET_PLUGINS" in (report[0].error or "")
    assert registry.get("echo") is None


def test_enabled_plugins_load_with_priority(plugin_module: str, settings: Settings) -> None:
    settings.plugins = ["echo", "early"]
    registry = Registry()
    found = eps(plugin_module, ("echo", "make"), ("early", "make_early"))
    report = load_plugins(registry, Net(settings), settings, found)
    assert [(p.handler, p.priority) for p in report] == [
        ("echo", DEFAULT_PRIORITY),
        ("early", 5),
    ]
    assert [h.name for h in registry.handlers] == ["early", "echo"]


def test_broken_plugins_are_reported(plugin_module: str, settings: Settings) -> None:
    settings.plugins = ["*"]
    found = eps(
        plugin_module,
        ("boom", "broken"),
        ("weird", "not_a_handler"),
        ("missing", "nope"),
    )
    report = load_plugins(Registry(), Net(settings), settings, found)
    assert [p.loaded for p in report] == [False, False, False]
    assert "boom" in (report[0].error or "") and "no 'name'" in (report[1].error or "")


def test_plugins_setting_reads_a_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANYGET_PLUGINS", "xkcd, other")
    assert Settings(_env_file=None).plugins == ["xkcd", "other"]
