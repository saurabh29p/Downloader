"""Handler registry: handlers are asked in priority order (see CLAUDE.md routing order)."""

from dataclasses import dataclass, field

from anyget.handlers.base import Handler

# Priorities follow the routing steps in CLAUDE.md; lower runs first.
PRIORITY_CONVERT = 10  # internal anyget: links only
PRIORITY_TORRENT = 20
PRIORITY_ARCHIVE = 30
PRIORITY_GIT = 40
PRIORITY_CLOUD = 50
PRIORITY_IIIF = 60
PRIORITY_BOOKS = 65
PRIORITY_AI = 70
PRIORITY_YTDLP = 80
PRIORITY_GALLERY = 90
PRIORITY_FALLBACK = 1000


@dataclass(order=True)
class _Entry:
    priority: int
    order: int
    handler: Handler = field(compare=False)


class Registry:
    def __init__(self) -> None:
        self._entries: list[_Entry] = []

    def register(self, handler: Handler, priority: int) -> None:
        if any(entry.handler.name == handler.name for entry in self._entries):
            raise ValueError(f"handler {handler.name!r} is already registered")
        self._entries.append(_Entry(priority, len(self._entries), handler))
        self._entries.sort()

    @property
    def handlers(self) -> list[Handler]:
        return [entry.handler for entry in self._entries]

    def get(self, name: str) -> Handler | None:
        return next((h for h in self.handlers if h.name == name), None)

    def find(self, url: str) -> Handler | None:
        return next((h for h in self.handlers if h.can_handle(url)), None)
