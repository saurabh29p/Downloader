# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added (Phase 7 — books, libraries, search, OCR, conversion)
- Books: one search asks many free sources at once and ranks the best legal copy first: downloadable full view, then the closest match, then EPUB > text PDF > scanned PDF > page images > text, whole works before chapters.
  - Sources: Standard Ebooks, Project Gutenberg (Gutendex, self-hostable via `ANYGET_GUTENDEX_URL`), Internet Archive, Open Library, Wikisource (any language, EPUB export), Google Books free ebooks, HathiTrust (by ISBN/OCLC), Library of Congress, Gallica, NDL Japan, Europeana, DPLA, BHL, Trove, DigitalNZ, DDB, and the Wayback Machine for dead ebook links.
  - The National Digital Library of India has no open API, so it is a search link.
  - Borrow-only and in-copyright books are never downloaded. They are shown as "not legally downloadable", with library (Open Library, WorldCat) and buy links.
- Book page links (Gutenberg, Standard Ebooks, Open Library, Wikisource) list their formats to pick from.
- IIIF libraries: Presentation v2 and v3 manifests, and item links from Gallica, Library of Congress, NDL, Europeana and the Qatar Digital Library. Every page is saved at full size, with an optional PDF merge (img2pdf). Items marked "In Copyright" and closed items are refused.
- A registry of about 40 libraries and archives across six regions (`GET /api/libraries`).
- Universal search (`GET /api/search`) over books, libraries, archive.org and videos (yt-dlp `ytsearch`), with a time limit and a status for each source.
- Conversions as jobs (`POST /api/convert`, `anyget convert JOB --to …`):
  - page images to PDF
  - OCR to a searchable PDF with a text sidecar (OCRmyPDF/Tesseract, many languages)
  - audio/video formats with ffmpeg (local files only)
  - EPUB to PDF when Calibre is installed

  `/api/health` lists the tools that are available.
- API keys for Europeana, DPLA, Trove, DigitalNZ, BHL and DDB live in settings and are never returned. `GET /api/settings/keys` shows only which keys are set. `.env.example` lists every optional key.
- Docker:
  - `ANYGET_WITH_OCR=1` builds the API image with OCR.
  - The live test image always has OCR.
- CLI: `anyget search "title"` (`--type libraries`, `--lang`), `anyget convert`.
- Web:
  - A Books page (best-copy card, format downloads, source status).
  - A Libraries page (regions, library cards, paste an item link, page grid, "merge into PDF").
  - A Search page with tabs.
  - "Convert…" on finished PDFs, images and media in Downloads (shown only when the tool exists).
  - Home and Ctrl+K entries; en/hi/ar.
- Live tests:
  - the best copy of "Pride and Prejudice"
  - Gutenberg EPUB (global), Gallica (Europe), NDL (Asia), Library of Congress (Americas), plus QDL when `ANYGET_LIVE_QDL_ITEM` is set
  - OCR on a rendered page in the test image

### Added (Phase 6 — code, cloud, images, AI, web pages)
- Code hosts (GitHub, GitLab, Codeberg, Bitbucket, gists): whole repo as a zip, folders (GitHub tree API, other hosts a zip), single files via raw URLs, release assets, releases with every asset plus the source zip. No `git` process; optional `ANYGET_GITHUB_TOKEN` for API limits.
- Cloud links: Google Drive files (large-file confirm, Docs/Sheets/Slides exported as PDF/XLSX), Dropbox (`dl=1`), OneDrive/SharePoint shares. MEGA through `megatools` when installed (now in the API image); a sign-in page is never saved as the file.
- Image galleries through gallery-dl, run as a separate process (GPL): it only lists the images, and every image is fetched through AnyGet's guarded HTTP with per-file resume.
- AI resources: Hugging Face models, datasets and Spaces (file list with sizes and sha256 checks, gated repos ask for your own `ANYGET_HF_TOKEN`), Civitai model files (sha256), Kaggle datasets with your own API key.
- Web page fallback: HTML links are no longer "unsupported" — save the page itself and/or pick the documents, images, audio, video and archives it links to.
- Multi-file downloads share one helper (`handlers/multi.py`): files go into one folder, progress is summed, md5/sha1/sha256 checked per file.
- Web: a file picker in the Home preview for any link with several files (image grid for galleries), new Code and Image galleries pages, Home "More sources" and Ctrl+K entries; en/hi/ar.
- Live tests: octocat/Hello-World repo zip and README, a Flickr Commons album (first two images), a tiny Hugging Face test model; a public Drive file when `ANYGET_LIVE_DRIVE_URL` is set.

### Fixed (Phase 6)
- Downloads ask for `Accept-Encoding: identity`; a server that compresses anyway no longer fails the size check (raw.githubusercontent.com sends gzip with the compressed length).
- IPv4 addresses are tried before IPv6, so a host without a working IPv6 route doesn't use up the connect timeout (seen on archive.org storage hosts in CI).
- archive.org downloads fall back to the item's other storage servers (`d2`, `d1`) when one can't be reached; the live run showed a storage host stalling in the TLS handshake.

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
