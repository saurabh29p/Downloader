# Phase 8 — Library, watch, settings (daily-use app)

Read `CLAUDE.md` first.

Deliverables:
- `anyget/library/`: index of downloaded files with source metadata, tags, search; previews for video, audio, images, PDF and EPUB; open folder, re-download.
- Auto-organize with folder templates by type and source; dedupe by hash or source ID.
- `anyget/watch/`: schedules for channels and archive.org collections; only new items get queued (download archive / last-seen IDs).
- Clipboard watcher (desktop option in the CLI): copied links appear as suggested jobs.
- Settings: download folder, folder templates, concurrency, speed limit, proxy, per-host limits, API keys (masked), language, theme, auto-update yt-dlp, cookies.txt import (own accounts only).
- Help and Legal pages (the rules from `CLAUDE.md`).
- Web: Library, Watch, Settings, Help pages.

**Acceptance check:** previews work for each file type; a watch run only queues new items.
Commit: `feat: phase 8 library, watch and settings`.
