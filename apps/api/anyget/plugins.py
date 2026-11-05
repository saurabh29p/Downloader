"""Plugins: extra handlers installed as Python packages.

A plugin declares an entry point in the `anyget.handlers` group that points at a
factory `make(net, settings) -> handler` (or a handler class taking the same
arguments). A handler may set `priority` (lower runs first; default 85, after the
built-in site handlers and before the generic file fallback).

Plugins are code running inside AnyGet, so none load unless you list them in
ANYGET_PLUGINS (comma separated entry point names, or "*" for all installed).
"""

import logging
from collections.abc import Iterable
from importlib.metadata import EntryPoint, entry_points
from typing import Any

from pydantic import BaseModel

from anyget.core.net import Net
from anyget.core.settings import Settings
from anyget.handlers.registry import Registry

log = logging.getLogger("anyget.plugins")

GROUP = "anyget.handlers"
DEFAULT_PRIORITY = 85


class PluginInfo(BaseModel):
    name: str
    target: str
    loaded: bool
    handler: str | None = None
    priority: int | None = None
    error: str | None = None


def installed() -> list[EntryPoint]:
    return sorted(entry_points(group=GROUP), key=lambda ep: ep.name)


def load_plugins(
    registry: Registry,
    net: Net,
    settings: Settings,
    available: Iterable[EntryPoint] | None = None,
) -> list[PluginInfo]:
    allowed = set(settings.plugins)
    report: list[PluginInfo] = []
    for ep in available if available is not None else installed():
        info = PluginInfo(name=ep.name, target=ep.value, loaded=False)
        report.append(info)
        if "*" not in allowed and ep.name not in allowed:
            info.error = "not enabled (add it to ANYGET_PLUGINS)"
            continue
        try:
            factory: Any = ep.load()
            handler = factory(net, settings)
            for attr in ("name", "can_handle", "probe", "download"):
                if not hasattr(handler, attr):
                    raise TypeError(f"the handler has no {attr!r}")
            priority = int(getattr(handler, "priority", DEFAULT_PRIORITY))
            registry.register(handler, priority)
        except Exception as exc:  # a broken plugin must not stop AnyGet
            log.warning("plugin %s failed to load: %s", ep.name, exc)
            info.error = f"{type(exc).__name__}: {exc}"[:300]
            continue
        info.loaded, info.handler, info.priority = True, str(handler.name), priority
        log.info("plugin %s loaded handler %s (priority %d)", ep.name, handler.name, priority)
    return report
