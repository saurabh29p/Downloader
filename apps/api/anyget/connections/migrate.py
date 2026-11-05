"""Move v1's plain-text secrets into encrypted Connections (runs at every start).

- API keys saved in Settings (the `setting` table) become key connections.
- data/cookies.txt is split into one connection per known site, then deleted, so no
  plain-text cookies stay on disk. Cookies for other sites in that file are dropped.
"""

import logging

from anyget.connections.sites import SITES
from anyget.connections.store import ConnectionStore, ConnectionValueError
from anyget.core.settings import Settings
from anyget.core.settings_store import SettingsStore
from anyget.core.users import OWNER_ID

log = logging.getLogger("anyget.connections")


def migrate_v1(settings: Settings, store: ConnectionStore, saved: SettingsStore) -> list[str]:
    moved: list[str] = []
    legacy = saved.pop_legacy_secrets()
    for site in SITES:
        if site.kind != "key" or not any(name in legacy for name in site.settings):
            continue
        values = {
            field: legacy.get(setting) or str(getattr(settings, setting) or "")
            for field, setting in zip(site.fields, site.settings, strict=True)
        }
        try:
            store.save_fields(OWNER_ID, site, values)
            moved.append(site.id)
        except ConnectionValueError:
            log.warning("v1 key for %s is incomplete; not moved", site.id)
    cookies = settings.data_dir / "cookies.txt"
    if cookies.is_file():
        try:
            moved += store.import_cookies(OWNER_ID, cookies.read_text(errors="replace"))
        except ConnectionValueError:
            log.warning("data/cookies.txt is not a cookies.txt file; removed")
        cookies.unlink(missing_ok=True)
    if moved:
        log.info("moved into Connections: %s", ", ".join(sorted(set(moved))))
    return moved
