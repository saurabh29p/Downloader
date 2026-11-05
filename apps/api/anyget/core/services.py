"""Wires the engine together. Used by the API (lifespan) and the CLI."""

from dataclasses import dataclass

from anyget.connections.migrate import migrate_v1
from anyget.connections.store import ConnectionStore
from anyget.core.auth import AccessVerifier, RateLimiter
from anyget.core.db import Database
from anyget.core.events import EventBus
from anyget.core.jobs import JobStore
from anyget.core.net import Net
from anyget.core.ownership import adopt_rows
from anyget.core.queue import DownloadQueue
from anyget.core.router import Router
from anyget.core.session import Sessions
from anyget.core.settings import Settings
from anyget.core.settings_store import SettingsStore
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
    PRIORITY_TORRENT,
    PRIORITY_WIKIMEDIA,
    PRIORITY_YTDLP,
    Registry,
)
from anyget.handlers.torrent import TorrentHandler
from anyget.handlers.wayback import WaybackHandler
from anyget.handlers.wikimedia import WikimediaHandler
from anyget.handlers.ytdlp import YtDlpHandler
from anyget.library.index import LibraryIndex
from anyget.plugins import PluginInfo, load_plugins
from anyget.watch.runner import WatchScheduler, WatchService


def build_registry(
    net: Net,
    settings: Settings,
    store: JobStore | None = None,
    connections: ConnectionStore | None = None,
) -> Registry:
    registry = Registry()
    if store is not None:
        registry.register(ConvertHandler(settings, store), PRIORITY_CONVERT)
    registry.register(TorrentHandler(net, settings), PRIORITY_TORRENT)
    archive = ArchiveOrgHandler(net)
    registry.register(archive, PRIORITY_ARCHIVE)
    registry.register(WaybackHandler(net), PRIORITY_ARCHIVE)
    registry.register(GitCodeHandler(net, settings), PRIORITY_GIT)
    registry.register(CloudShareHandler(net), PRIORITY_CLOUD)
    registry.register(IiifLibraryHandler(net, settings), PRIORITY_IIIF)
    registry.register(BooksHandler(net, settings, archive), PRIORITY_BOOKS)
    registry.register(AiResourcesHandler(net, settings), PRIORITY_AI)
    registry.register(WikimediaHandler(net), PRIORITY_WIKIMEDIA)
    registry.register(YtDlpHandler(settings, connections), PRIORITY_YTDLP)
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
    settings_store: SettingsStore
    library: LibraryIndex
    watches: WatchService
    scheduler: WatchScheduler
    plugins: list[PluginInfo]
    access: AccessVerifier
    sessions: Sessions
    login_limiter: RateLimiter
    connections: ConnectionStore

    @classmethod
    def build(cls, settings: Settings, net: Net | None = None) -> "Services":
        settings.downloads_dir.mkdir(parents=True, exist_ok=True)
        db = Database(settings)
        db.create_all()
        settings_store = SettingsStore(db, settings)
        settings_store.load()  # saved settings override .env
        adopt_rows(db, settings)  # v2: rows from before sign-in get an owner
        connections = ConnectionStore(db, settings)
        migrate_v1(settings, connections, settings_store)  # v1 plain-text secrets
        connections.apply()  # saved keys fill settings (github_token, tmdb_key…)
        store = JobStore(db)
        bus = EventBus()
        net = net or Net(settings)
        registry = build_registry(net, settings, store, connections)
        plugins = load_plugins(registry, net, settings)
        router = Router(registry, net)
        queue = DownloadQueue(settings, store, bus, router)
        library = LibraryIndex(db, settings.downloads_dir)
        queue.on_done.append(library.add_job)
        watches = WatchService(db, net, router, queue)
        return cls(
            settings,
            db,
            store,
            bus,
            net,
            registry,
            router,
            queue,
            settings_store,
            library,
            watches,
            WatchScheduler(watches),
            plugins,
            AccessVerifier(net, settings),
            Sessions(settings),
            RateLimiter(),
            connections,
        )

    async def start(self, recover: bool = True, watch: bool | None = None) -> None:
        await self.queue.start(recover=recover)
        # The API server runs watches; the CLI (recover=False) does not.
        if (recover if watch is None else watch) and self.settings.watch_enabled:
            self.scheduler.start()

    async def stop(self) -> None:
        await self.scheduler.stop()
        await self.queue.stop()
        await self.net.aclose()
        self.db.dispose()
