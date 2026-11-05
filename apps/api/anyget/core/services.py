"""Wires the engine together. Used by the API (lifespan) and the CLI."""

from dataclasses import dataclass

from anyget.core.db import Database
from anyget.core.events import EventBus
from anyget.core.jobs import JobStore
from anyget.core.net import Net
from anyget.core.queue import DownloadQueue
from anyget.core.router import Router
from anyget.core.settings import Settings
from anyget.handlers.ai_resources import AiResourcesHandler
from anyget.handlers.archive_org import ArchiveOrgHandler
from anyget.handlers.books import BooksHandler
from anyget.handlers.cloud_share import CloudShareHandler
from anyget.handlers.convert import ConvertHandler
from anyget.handlers.gallery import GalleryHandler
from anyget.handlers.git_code import GitCodeHandler
from anyget.handlers.http_generic import HttpGenericHandler
from anyget.handlers.iiif_library import IiifLibraryHandler
from anyget.handlers.registry import (
    PRIORITY_AI,
    PRIORITY_ARCHIVE,
    PRIORITY_BOOKS,
    PRIORITY_CLOUD,
    PRIORITY_CONVERT,
    PRIORITY_FALLBACK,
    PRIORITY_GALLERY,
    PRIORITY_GIT,
    PRIORITY_IIIF,
    PRIORITY_YTDLP,
    Registry,
)
from anyget.handlers.wayback import WaybackHandler
from anyget.handlers.ytdlp import YtDlpHandler


def build_registry(net: Net, settings: Settings, store: JobStore | None = None) -> Registry:
    registry = Registry()
    if store is not None:
        registry.register(ConvertHandler(settings, store), PRIORITY_CONVERT)
    archive = ArchiveOrgHandler(net)
    registry.register(archive, PRIORITY_ARCHIVE)
    registry.register(WaybackHandler(net), PRIORITY_ARCHIVE)
    registry.register(GitCodeHandler(net, settings), PRIORITY_GIT)
    registry.register(CloudShareHandler(net), PRIORITY_CLOUD)
    registry.register(IiifLibraryHandler(net, settings), PRIORITY_IIIF)
    registry.register(BooksHandler(net, settings, archive), PRIORITY_BOOKS)
    registry.register(AiResourcesHandler(net, settings), PRIORITY_AI)
    registry.register(YtDlpHandler(settings), PRIORITY_YTDLP)
    registry.register(GalleryHandler(net), PRIORITY_GALLERY)
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
        registry = build_registry(net, settings, store)
        router = Router(registry, net)
        queue = DownloadQueue(settings, store, bus, router)
        return cls(settings, db, store, bus, net, registry, router, queue)

    async def start(self, recover: bool = True) -> None:
        await self.queue.start(recover=recover)

    async def stop(self) -> None:
        await self.queue.stop()
        await self.net.aclose()
        self.db.dispose()
