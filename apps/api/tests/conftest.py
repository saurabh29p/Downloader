"""Shared fixtures. All DNS is faked: hosts resolve to a public IP unless a test says otherwise."""

from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path

import pytest

from anyget.core import net
from anyget.core.services import Services
from anyget.core.settings import Settings, get_settings

PUBLIC_IP = "93.184.215.14"


class FakeDNS:
    def __init__(self) -> None:
        self.records: dict[str, list[str] | Callable[[], list[str]]] = {}
        self.calls: list[str] = []

    def set(self, host: str, *ips: str) -> None:
        self.records[host] = list(ips)

    def resolve_sync(self, host: str, port: int) -> list[str]:
        self.calls.append(host)
        record = self.records.get(host, [PUBLIC_IP])
        return record() if callable(record) else list(record)

    async def resolve(self, host: str, port: int) -> list[str]:
        return self.resolve_sync(host, port)


@pytest.fixture(autouse=True)
def fake_dns(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> FakeDNS:
    dns = FakeDNS()
    if request.node.get_closest_marker("live"):
        return dns  # live tests use real DNS
    monkeypatch.setattr(net, "resolve_host", dns.resolve)
    monkeypatch.setattr(net, "resolve_host_sync", dns.resolve_sync)
    return dns


@pytest.fixture(autouse=True)
def no_backoff_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(net, "_sleep", fake_sleep)
    return slept


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        downloads_dir=tmp_path / "downloads",
        data_dir=tmp_path / "data",
        _env_file=None,
    )


@pytest.fixture
async def services(settings: Settings) -> AsyncIterator[Services]:
    svc = Services.build(settings)
    await svc.start()
    try:
        yield svc
    finally:
        await svc.stop()


@pytest.fixture
def env_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """For code that calls get_settings() itself (CLI)."""
    monkeypatch.setenv("ANYGET_DOWNLOADS_DIR", str(tmp_path / "downloads"))
    monkeypatch.setenv("ANYGET_DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()
