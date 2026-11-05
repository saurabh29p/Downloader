"""Wires the engine together. Used by the API (lifespan) and the CLI."""

from dataclasses import dataclass

from anyget.core.db import Database
from anyget.core.events import EventBus
from anyget.core.jobs import JobStore
from anyget.core.net import Net
from anyget.core.queue import DownloadQueue
from anyget.core.router import Router
from anyget.core.settings import Settings
from anyget.handlers.http_generic import HttpGenericHandler
from anyget.handlers.registry import PRIORITY_FALLBACK, PRIORITY_YTDLP, Registry
from anyget.handlers.ytdlp import YtDlpHandler


def build_registry(net: Net, settings: Settings) -> Registry:
    registry = Registry()
    registry.register(YtDlpHandler(settings), PRIORITY_YTDLP)
    registry.register(HttpGenericHandler(net), PRIORITY_FALLBACK)
    return registry


@dataclass
class Services:
    settings: Settings
    db: Database
    store: JobStore
    bus: EventBus
    net: Net
    registry: Registry
    router: Router
    queue: DownloadQueue

    @classmethod
    def build(cls, settings: Settings, net: Net | None = None) -> "Services":
        settings.downloads_dir.mkdir(parents=True, exist_ok=True)
        db = Database(settings)
        db.create_all()
        store = JobStore(db)
        bus = EventBus()
        net = net or Net(settings)
        registry = build_registry(net, settings)
        router = Router(registry, net)
        queue = DownloadQueue(settings, store, bus, router)
        return cls(settings, db, store, bus, net, registry, router, queue)

    async def start(self, recover: bool = True) -> None:
        await self.queue.start(recover=recover)

    async def stop(self) -> None:
        await self.queue.stop()
        await self.net.aclose()
        self.db.dispose()
