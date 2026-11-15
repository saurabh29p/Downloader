# Phase 9 — PWA, browser extension, plugins

Read `CLAUDE.md` first.

Deliverables:
- PWA: manifest, icons, service worker, install prompt, Android Web Share Target that opens the preview for the shared link.
- `docs/termux.md` + a Termux script that receives shared links and calls the CLI or API.
- `apps/extension`: Manifest V3 extension (Chrome + Firefox) — context menu and toolbar button send the current page/link to the local app, with configurable base URL and bearer token.
- Plugin system: extra handlers loaded from the `anyget.handlers` entry point group; `examples/anyget-plugin-example/` that loads and passes tests.
- Optional torrent handler (`handlers/torrent.py`, libtorrent) for magnet links and `.torrent` files, off by default.

**Acceptance check:** sharing a link on Android opens the preview; the example plugin loads.
Commit: `feat: phase 9 pwa, extension and plugins`.
