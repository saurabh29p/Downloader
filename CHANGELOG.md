# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added (Phase 5 — archive.org and Wayback)
- archive.org handler: item metadata (cached), file picker, "all of format X", best-format defaults per media type, multi-file downloads into a folder with Range resume and per-file md5 checks; restricted, lending-library and dark items are explained, never downloaded.
- Search API with filters (type, collection, creator, years), advancedsearch paging and scrape-API cursor paging; item API.
- Wayback handler: raw `id_` downloads (HTML captures kept), CDX snapshot API grouped by year.
- Web: archive.org page (search, filters, results, item page with format shortcuts and file table) and Wayback page (year timeline, raw download); Home "More sources" links and Ctrl+K entries; en/hi/ar.
- Live tests: a Gutenberg PDF on archive.org with md5, a 2005 snapshot of example.com.

### Added (Phase 4 — YouTube and media)
- yt-dlp handler (YouTube, Vimeo, Bilibili, SoundCloud and 1,800+ sites) running in a worker thread: probe with normalized formats, quality presets (best, 2160–360, audio), mp4/mkv/webm, mp3/m4a/opus at best quality, embedded thumbnail, metadata and chapters, subtitles (manual and auto, srt or embedded), optional info.json, live progress over SSE, pause/cancel.
- Playlists and channels (Videos, Shorts, Live tabs) with flat probing, item selection, date range and first-N, numbered files in a folder, per-source download archive so saved items are skipped.
- Clear reasons for DRM, members-only, paid, private, age-restricted, sign-in, bot-check, region-blocked, unfinished live and removed videos. Nothing is bypassed.
- Private-network guard for yt-dlp's own connections (all handlers, connect time) and for ffmpeg inputs; geo bypass forced off.
- Optional cookies.txt in Settings (0600, never returned or logged).
- `/api/health` reports yt-dlp, yt-dlp-ejs, Deno and ffmpeg versions.
- Website: YouTube page (video card with format picker, playlist/channel table with select all, Shorts grid, tabs), the same picker in the Home preview drawer, Settings page, YouTube nav item; en/hi/ar strings.
- CLI: `anyget get URL -q 720` / `-x mp3`; playlists expand into numbered items.
- Docker `test` image + `make live`; manual "Live tests" GitHub workflow.

### Changed
- `POST /api/jobs` accepts `items` (each with its own options) and returns `skipped`; `POST /api/probe` accepts `options`.
- Jobs gain `note` and `files`; old databases are migrated automatically.
- `Button` no longer supports `asChild` (smaller first-load JS).
- Finished-download toasts that arrive together are grouped ("Downloaded 3 files").

### Added
- Phase 0: `CLAUDE.md` project memory, `docs/plan.md`, `docs/setup.md`, phase prompts 0–10.
- Phase 1: monorepo skeleton — pnpm + Turborepo workspace, FastAPI `anyget` package with `/api/health` and `/api/version`, handler contract, Typer CLI, Next.js 16 web app (Tailwind 4 tokens, shadcn/ui, next-intl en/hi/ar with RTL, TanStack Query), `@anyget/shared` typed client generated from OpenAPI, Dockerfiles, Docker Compose with healthchecks on 127.0.0.1, Cloudflare Tunnel compose stub, Makefile, pre-commit, GitHub Actions CI.
- Phase 2: download engine — SSRF guard (DNS + redirect checks and a connect-time IP check that defeats DNS rebinding), safe Unicode filenames and path containment, SQLite job store, asyncio queue with global and per-host limits, pause/resume/retry/cancel, SSE events, URL normalizer with tracking-param stripping and short-link expansion, handler registry, generic HTTP handler with Range resume and md5/sha1 checks, REST API (`/api/probe`, `/api/jobs…`, `/api/events`), CLI `get`/`probe`/`jobs`.
- Phase 3: website foundation — app shell (header nav, phone bottom nav, theme and language menus, Ctrl/⌘+K quick menu), Home paste box (one or many links, clipboard, .txt drop/open) with source detection and preview drawer, recent downloads, Downloads page with live SSE progress, filters, pause/resume/retry/cancel/remove and "Save file", toasts, loading/empty/error states, dark mode, en/hi/ar with RTL. Playwright paste-to-done, batch, pause/resume, keyboard-only and axe tests; Lighthouse script; first-load JS budget test.

### Fixed
- SSE stream cleanup raised errors when a browser disconnected.
- Live progress could be dropped by the browser after a page refresh (stale timestamps); job times are now always sent as UTC.
- API container could not create its database when Docker created the `data` folder as root (CI Docker job). The container now adopts `PUID`/`PGID` and fixes folder ownership before dropping privileges.
