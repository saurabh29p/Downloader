# AnyGet — project memory for Claude Code

One tool: paste any public link, get the file. A FastAPI core (URL router → handlers → SQLite job queue with SSE progress), a Next.js website and a Typer CLI. Runs on the user's own computer with Docker Compose (`make up`), or hosted (web on Vercel `downloader-web`, API on Railway `anyget-api` with a `/data` volume) behind the owner sign-in; Cloudflare Tunnel + Access and Tailscale remain options. Free tools only, personal use, no billing or ads. **LLM is optional** (v2: OpenRouter, Phase 5): every feature must work without a key, and no cookies, secrets or file contents are ever sent to it.

Read this file at the start of every session. The full research doc lives in `docs/plan.md`; phase prompts live in `prompts/`.

## Current status

- [x] Phase 0 — prerequisites, CLAUDE.md
- [x] Phase 1 — monorepo skeleton
- [x] Phase 2 — core and security
- [x] Phase 3 — website foundation
- [x] Phase 4 — YouTube and media
- [x] Phase 5 — archive.org and Wayback
- [x] Phase 6 — code, cloud, images, AI
- [x] Phase 7 — books, libraries, search
- [x] Phase 8 — library, watch, settings
- [x] Phase 9 — PWA, extension, plugins
- [x] Phase 10 — deploy and release (v1.0.0)

v2 (prompt: "AnyGet v2 — Final Build Prompt"; one PR per phase from `feat/v2-universal-search`):
- [x] v2 Phase 1 — owner sign-in, per-user rows, bug fixes
- [ ] v2 Phase 2 — Connections (encrypted cookies/keys per site)
- [ ] v2 Phase 3 — universal search engine
- [ ] v2 Phase 4 — Sections (Movies, Books, Music, Video, Declassified, More)
- [ ] v2 Phase 5 — OpenRouter brain (optional)
- [ ] v2 Phase 6 — "The Reading Room" UI
- [ ] v2 Phase 7 — polish and ship

Update this checklist at the end of every phase.

## Stack and locked versions (checked 4 Nov 2026)

| Part | Version | Note |
|---|---|---|
| Next.js | 16.4.x | App Router, `output: "standalone"` |
| React / TypeScript | 19.x / 5.9.x | TS 7 is out; stay on 5.x until Next.js documents support |
| Tailwind CSS | 4.3.x | CSS-first config, `@tailwindcss/postcss` |
| shadcn CLI | 4.x | `pnpm dlx shadcn@latest add <component>` from `apps/web` |
| TanStack Query / next-intl | 5.x / 4.x | RTL via logical CSS properties |
| Vitest / Playwright | 5.x / 1.64.x | plus `@axe-core/playwright` |
| Node / pnpm | 24 LTS / 10 | Next.js needs Node 20.9+ |
| Python / FastAPI | 3.12 / 0.162.x | yt-dlp needs Python 3.11+ |
| yt-dlp | 2026.10.26 `[default]` extra | installs matching yt-dlp-ejs |
| Deno | 2.9.8 | needed by yt-dlp for full YouTube support (min 2.3) |
| gallery-dl / internetarchive | 1.32.19 / 5.12.1 | |
| cloudflared image | 2026.10.7 | token based, `tunnel --no-autoupdate run` |

Engines: yt-dlp (video/audio, 1,800+ sites), ffmpeg (merge/convert/embed), gallery-dl (image galleries), internetarchive `ia` (archive.org), httpx (direct files with Range resume), git + GitHub REST (code), huggingface_hub (AI resources), optional OCRmyPDF/Tesseract, optional libtorrent. aria2 and cobalt are **not** used in v1.

**License rule:** `ia` is AGPL and gallery-dl is GPL. Call them as **separate CLI processes** (subprocess), not imported libraries, unless the project is relicensed GPL-compatible.

## Repository layout

```
.
├── CLAUDE.md                 # this file
├── Makefile                  # every common command
├── docker-compose.yml        # api + web, ports bound to 127.0.0.1
├── docker-compose.tunnel.yml # cloudflared (phase 10)
├── package.json              # pnpm workspaces + Turborepo
├── apps/
│   ├── api/                  # FastAPI, uv project, Python package `anyget`
│   │   ├── anyget/
│   │   │   ├── main.py       # create_app()
│   │   │   ├── openapi.py    # dumps the OpenAPI schema for codegen
│   │   │   ├── core/         # settings, router, db, jobs, queue, events, filenames, net, auth
│   │   │   ├── handlers/     # base, registry, http_generic, ytdlp, archive_org, wayback,
│   │   │   │                 # git_code, cloud_share, gallery, ai_resources, webpage,
│   │   │   │                 # books, iiif_library, torrent
│   │   │   ├── books/        # one adapter per book source + ranker
│   │   │   ├── libraries/    # worldwide library registry (region table)
│   │   │   ├── library/      # offline library browser (phase 8)
│   │   │   ├── watch/        # scheduled watch downloads (phase 8)
│   │   │   ├── convert/      # ffmpeg, img2pdf, OCR (phase 7)
│   │   │   ├── api/          # FastAPI routers
│   │   │   └── cli/          # Typer + Rich CLI (`anyget ...`)
│   │   └── tests/            # pytest + respx; fixtures/ for offline JSON
│   ├── web/                  # Next.js
│   │   ├── app/[locale]/(app)/<section>/page.tsx
│   │   ├── components/ui     # shadcn parts
│   │   ├── components/<feature>
│   │   ├── lib/              # api client, providers, utils
│   │   ├── messages/         # en.json, hi.json, ar.json
│   │   ├── i18n/             # next-intl routing + request config
│   │   ├── styles/globals.css# design tokens
│   │   └── e2e/              # Playwright specs
│   └── extension/            # browser extension (phase 9)
├── packages/shared/          # OpenAPI types (openapi-typescript) + openapi-fetch client
├── prompts/                  # one Claude Code prompt per phase
├── docs/                     # setup, plan, deploy guides
└── examples/
```

## Commands

| Command | What it does |
|---|---|
| `make setup` | install all deps (uv sync + pnpm install) |
| `make dev` | run api (:8000) and web (:3000) locally with reload |
| `make gen` | regenerate `packages/shared` from the API's OpenAPI schema |
| `make lint` / `make typecheck` / `make test` | ruff+eslint+prettier / mypy+tsc / pytest+vitest |
| `make check` | lint + typecheck + test (run before every commit) |
| `make e2e` | Playwright end-to-end + axe (starts a fixture file server on :8200, api on :8100, production web build on :3100) |
| `pnpm --filter @anyget/web lighthouse <url>` | Lighthouse budgets against a running production build (`CHROME_PATH` for the browser) |
| `make up` / `make down` / `make logs` | Docker Compose |
| `make up-public` | Compose + Cloudflare Tunnel |
| `uv run anyget get URL… [-i list.txt]` | download in-process with progress bars; Ctrl+C pauses, rerun resumes |
| `uv run anyget probe URL` / `anyget jobs` | inspect a link / list jobs |
| `uv run anyget get URL -q 720` / `-x mp3` | video at a quality / audio only; playlists expand into numbered items |
| `make live` | live network tests (YouTube, Vimeo) in the Docker `test` image with ffmpeg + Deno; also the manual "Live tests" GitHub workflow |
| `make gen-api` | alias of `make gen` |
| `uv run anyget search "title" [--type libraries]` | best legal copy across book sources / library search |
| `uv run anyget convert JOB --to ocr\|pdf\|mp3…` | convert a finished download (OCR needs OCRmyPDF + Tesseract) |
| `uv run anyget library [--scan]` / `anyget watch add\|list\|run` | the offline library / scheduled watches |
| `uv run --extra desktop anyget watch-clipboard [--auto]` | offer copied links as downloads (desktop) |
| `make extension` | build the browser extension zips (`apps/extension/dist/`) |
| `make backup` / `make restore FILE=…` | back up / restore `data/` (stop AnyGet before restoring) |
| `git tag vX.Y.Z && git push origin vX.Y.Z` | release: images to ghcr.io + GitHub release (`.github/workflows/release.yml`) |
| `cd examples/anyget-plugin-example && uv run pytest` | example plugin tests (also part of `make test`) |

## Architecture rules

### Handler contract
Every handler lives in one file in `apps/api/anyget/handlers/` and implements `anyget.handlers.base.Handler`:

- `name: str`
- `can_handle(url) -> bool` — cheap, no network unless unavoidable
- `probe(url) -> Probe` — title, size, thumbnail, and `choices` (formats/files/items)
- `download(job, options, progress_cb) -> DownloadResult`

Adding a new site = adding one handler file and registering it. Plugins (phase 9) load extra handlers via the `anyget.handlers` Python entry point group.

### URL routing order (core/router.py)
1. Normalize: trim, expand short links (HEAD, follow redirects through the SSRF guard), strip tracking params (`utm_*`, `fbclid`, `gclid`, `si`, …).
2. `magnet:` or `.torrent` → torrent.
3. `archive.org/details|download|search` → archive_org; `web.archive.org/web/...` → wayback.
4. github.com, gitlab.com, codeberg.org, bitbucket.org, gist.github.com → git_code (repo, folder, file, release asset).
5. Google Drive, Dropbox, OneDrive, MEGA public links → cloud_share (rewrite to direct URLs; MEGA via megatools).
6. Known library hosts (Gallica, Europeana, Trove, NDL, …) or any URL exposing a IIIF manifest → iiif_library.
7. Hugging Face, Civitai, Kaggle, prompt repos → ai_resources.
8. yt-dlp `extract_info(url, download=False)` succeeds → ytdlp.
9. gallery-dl has a matching extractor → gallery.
10. Fallback: HEAD/GET. File Content-Type → http_generic. HTML → webpage (save HTML/PDF, list media/doc links to pick).

### Jobs and queue
- SQLite (SQLModel) at `./data/anyget.db`. States: `queued → probing → downloading → done | failed`, plus `paused` and `canceled`.
- Code: `core/jobs.py` (table + `JobStore`), `core/queue.py` (`DownloadQueue`), `core/events.py` (bus + SSE), `core/services.py` (wires everything; used by the API lifespan and the CLI).
- Partial files are `.anyget-<job id>.part` in the downloads folder (`handlers.base.part_path`), so a paused or interrupted job resumes after restarts.
- asyncio worker pool: global limit 3 (setting), per-host limits (archive.org 2).
- Progress via Server-Sent Events. Resume via HTTP Range into `.part` files; yt-dlp continues partial files.
- Verify md5/sha1 when the source gives one. Dedupe by hash or source ID.

### Security (non-negotiable)
- **SSRF guard** (`core/net.py`): only `http`/`https`; resolve DNS and block private, loopback, link-local, CGNAT, multicast and cloud metadata IPs (incl. IPv6 equivalents) — on the first request **and every redirect**.
- **Path safety** (`core/filenames.py`): sanitize every filename; resolve the final path and assert it is inside the downloads root.
- Filenames: keep the original script (Japanese, Arabic, Devanagari), NFC-normalize, remove only OS-illegal characters, limit to 180 bytes (Windows safe), fall back to the source ID.
- Ports bound to `127.0.0.1` only. Public access only via Cloudflare Access; the API also verifies the Access JWT (`Cf-Access-Jwt-Assertion`). Optional bearer token for CLI and extension.
- Rate limit per client on the API and per host on outgoing requests; back off on 429/503.
- No secrets in the repo. Keys live in `.env` or Settings, masked in UI and logs. CSP + security headers. Dependency audits in CI.

### archive.org etiquette
2–4 parallel downloads max, a clear User-Agent with a contact email (from settings, never hardcoded personal data), back off on 429/503, cache metadata. Skip access-restricted, lending-library and stream-only items.

## Legal and fair use (non-negotiable)
Personal use only. Download only what the user owns, what is public domain or openly licensed, or what the site allows.
- **DRM content is out of scope** (Netflix, Spotify, Prime, Apple Music, paid ebooks). Never add support.
- **Shadow libraries** (LibGen, Z-Library, Anna's Archive and similar) are excluded and will never be a source.
- Never bypass geo-blocks, lending/borrow restrictions, paywalls or members-only content. Show a clear message instead ("not available in your region", "borrow-only — not downloadable").
- In-copyright out-of-print books are shown as "not legally downloadable" with library/buy links.
- Optional `cookies.txt` import only for sites the user is legally logged in to.

## Frontend rules
- Next.js App Router, TypeScript strict, Tailwind 4 tokens in `styles/globals.css` (color, type scale, 4px grid, radius, shadow, motion; light + dark, system default).
- Fonts: Inter plus Noto Sans fallbacks for CJK, Arabic, Devanagari.
- shadcn/ui parts (button, dialog, drawer, tabs, table, toast, command palette) plus custom paste box, format picker, job row, file picker, previewers.
- Every screen has loading skeletons, helpful empty states, and error states with retry.
- WCAG 2.2 AA: keyboard, focus rings, labels, `aria-live` progress, contrast, reduced motion. axe must be clean.
- i18n with next-intl (English, Hindi, Arabic first). RTL via logical properties (`ms-`, `pe-`, `start-`…), never `left/right`.
- Mobile-first, works at 360px, bottom nav on phone; PWA with Android share target (phase 9).
- Talk to the API only through `@anyget/shared` (generated client). Run `make gen` after any API schema change.
- Budgets: LCP < 2.5s (mobile 4G), INP < 200ms, CLS < 0.1, first-load JS < 170 KB gzip, Lighthouse Performance 90+, Accessibility 100.

## Code quality
- Python: ruff (lint + format), mypy strict, pytest + respx (mock all HTTP). Live-network tests are marked `@pytest.mark.live`, use only public-domain/CC links, and are skipped by default.
- Offline fixtures (archive.org metadata, CDX, etc.) live in `apps/api/tests/fixtures/`.
- Web: ESLint, Prettier, Vitest (unit), Playwright + axe (e2e).
- Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`…), semantic versions, `CHANGELOG.md` in Keep a Changelog format.
- CI (GitHub Actions) runs lint, typecheck, tests, build, codegen check, Playwright and Docker builds on every push/PR.

## Build roadmap

| Phase | Goal | Deliverables | Acceptance check |
|---|---|---|---|
| 0 Prerequisites | Machine ready | Docker Desktop (WSL2), Git, Node 24, uv + Python 3.12, ffmpeg, Deno, Claude Code, private repo | all version commands work; CLAUDE.md committed |
| 1 Monorepo skeleton | Base and tooling | apps/web, apps/api, packages/shared, Dockerfiles, Compose, CI | `make check`, `make e2e` green; both containers healthy |
| 2 Core and security | Download engine | router, handlers base/registry/http_generic, SQLite queue, SSE, HTTP resume, SSRF + path safety, CLI | resume works; SSRF and traversal tests pass |
| 3 Website foundation | Design system + core flow | tokens, app shell, Home paste box, preview drawer, Downloads queue, i18n + RTL | Playwright paste-to-done; axe clean; Lighthouse 90+/100 |
| 4 YouTube and media | yt-dlp + ffmpeg | formats, MP3, subtitles, playlists, channels, Shorts, YouTube page | CC video as 720p and MP3; 3-item playlist |
| 5 archive.org + Wayback | Archive section | search, item file picker, collections, CDX timeline, `id_` raw | PDF from a Gutenberg item, md5 ok; 2005 snapshot |
| 6 Code, cloud, images, AI | Wider coverage | git hosts, Drive/Dropbox, gallery-dl, Hugging Face, web page fallback | repo, single file, Drive file, Flickr CC album |
| 7 Books, libraries, search | Books + worldwide | book adapters + ranker, IIIF libraries by region, universal search, OCR, conversion | best copy found; books from 4 regions; OCR works |
| 8 Library, watch, settings | Daily-use app | offline library with previews, tags, dedupe, schedules, clipboard, settings, Help and Legal | previews work; watch only queues new items |
| 9 PWA, extension, plugins | Phone and browser | PWA share target, Termux doc, browser extension, plugin system, optional torrent | share opens preview; example plugin loads |
| 10 Deploy and release | Worldwide access | cloudflared service, Access JWT check, deploy + Tailscale docs, backups, v1.0.0 | `https://dl.<domain>` opens after email code |

## Gotchas
- `API_URL` is read when the web app is **built** (Next.js rewrites are baked in). Compose builds with `http://api:8000`; local dev uses `http://127.0.0.1:8000`.
- Next.js 16 uses `proxy.ts` (formerly `middleware.ts`) for next-intl locale routing. Keep `api` and `healthz` excluded from its matcher.
- `/healthz` on web is liveness only; `/api/health` goes through the rewrite to FastAPI.
- If Playwright's bundled Chromium is missing, set `PW_CHROMIUM_PATH=/path/to/chrome`.
- Vitest 5: when mocking a module function that must reject, use a plain async function instead of `vi.fn().mockRejectedValue` (the latter fails the test).

- All outgoing HTTP goes through `core/net.Net` (never a bare `httpx` client): it re-checks every redirect hop and its connection pool refuses private IPs at connect time (`GuardedBackend`). Legacy IPv4 forms (`2130706433`, `0x7f.1`) are treated as IPs.
- `ANYGET_NET_ALLOWLIST=host:port,…` lets tests/e2e reach local fixture servers. Never set it in normal use.
- The API container starts as root only to match `PUID`/`PGID` (default 1000; `make up` passes your ids) and make `/data` and `/downloads` writable, then drops to the `anyget` user (`apps/api/docker-entrypoint.sh`). Without it, Docker-created bind-mount folders are root-owned and SQLite cannot open.
- `ANYGET_PROXY` is the only proxy used (env `HTTP(S)_PROXY` is ignored on purpose). With a proxy, only the pre-flight DNS check runs.
- Tests fake DNS (`tests/conftest.py::fake_dns`): every host resolves to a public IP unless a test sets it. Use `respx` for HTTP.
- Stream bodies with `response.aiter_bytes()` (no chunk size) so data reaches disk before a dropped connection; buffered chunks are lost.

### Media (yt-dlp) gotchas
- `handlers/ytdlp.py` + `handlers/ytdlp_support/` (formats, options, errors, archive). yt-dlp runs in a worker thread; progress hooks raise `DownloadCancelled` when the job is paused/canceled, and the coroutine waits for the thread to stop.
- Safety params live in `ytdlp_support/options.SAFETY_PARAMS` and must never be user-controlled: `geo_bypass: False` (yt-dlp's default fakes X-Forwarded-For), no unplayable/DRM formats, `external_downloader: {"default": "native"}` so ffmpeg never fetches URLs.
- yt-dlp's sockets are guarded by `core/net_guard.py` (patches yt-dlp's `create_connection` everywhere it is referenced, plus urllib3's; checks ffmpeg inputs). `tests/test_net_guard.py` proves it with real yt-dlp; rerun it after every yt-dlp upgrade.
- The probe's raw info is cached for 10 minutes so the download does not extract twice (re-extracted when cookies are used).
- Per-source download archives: `data/archives/<extractor>-<source id>.txt`; single videos share `<extractor>-videos.txt`. Playlist items are queued one job each with `folder`, `index`, `archive`, `archive_id`; `POST /api/jobs` returns already-saved items in `skipped`.
- Unavailable reasons are mapped in `ytdlp_support/errors.py` (fixtures: `tests/fixtures/ytdlp/errors.json`). New codes need a translation in `Errors` and an entry in `lib/errors.ts`.
- Cookies: `data/cookies.txt` (0600), never returned or logged; copied per job into the job's temp folder and deleted afterwards.
- New job columns (`note`, `files`) are added to old databases by `Database._add_missing_columns` (nullable additions only).
- Tests fake DNS for both resolvers (`resolve_host`, `resolve_host_sync`); tests marked `live` use real DNS.
- Live tests: YouTube bot-checks CI runners ("confirm you're not a bot") and Vimeo now asks for sign-in. Set the `ANYGET_LIVE_COOKIES` secret (a cookies.txt from your own account) or run `make live` from home. The PeerTube CC video needs no account. Never add `curl_cffi` impersonation: it uses libcurl sockets that bypass `net_guard`.

### archive.org / Wayback gotchas
- `handlers/archive_org.py` uses the public HTTP APIs only (metadata, advancedsearch, scrape); the AGPL `ia` tool is not imported. Item metadata is cached 10 minutes. Restricted items map to `restricted`, lending-library items (`inlibrary`/`printdisabled` + `access-restricted-item`) to `borrow_only` (HTTP 403 from `/api/probe`), dark items to `unavailable`.
- Multi-file items download into `downloads/<identifier>/` through `HttpGenericHandler` (Range resume, md5 per file); partials live in that folder and `remove_partials` cleans one level of subfolders.
- `handlers/wayback.py` downloads `<ts>id_/<url>` (raw bytes, no toolbar); `HttpGenericHandler.probe(..., {"allow_html": True})` lets it keep HTML captures.
- APIs: `GET /api/archive/search` (`deep=true`/`cursor` → scrape API), `GET /api/archive/items/{id}`, `GET /api/wayback/snapshots?url=`. Web calls live in `lib/api-archive.ts` so Home never loads them.

### Code / cloud / gallery / AI gotchas
- `JobOut.connect` (computed, `core/sites.connect_site`) names the site whose account would fix a failed job (`login_required`, `bot_check`, `age_restricted`, `forbidden`); the web shows "Connect your <site> account" from it. Phase 2 grows `core/sites.py` into the Connections registry.
- `handlers/wikimedia.py` (priority 75, before yt-dlp whose "Wikimedia" extractor saves File: pages as video): MediaWiki `imageinfo` → original file through `HttpGenericHandler` with its sha1. The router also sends any image-suffix link that would go to `ytdlp`/`gallery` to `http` (`router.is_image_link`). Image probes have `extra.kind == "image"` and `thumbnail`.
- Multi-file handlers (archive.org, git_code, gallery, ai_resources, web pages) build `RemoteFile`s and call `handlers/multi.download_many`; the user's pick arrives as `options["files"]` (choice ids).
- Handler-only request headers (tokens, Referer) go in `options["_headers"]` / `RemoteFile.headers`. The API drops every option key that starts with `_`, so users can't set them.
- `HttpGenericHandler.probe` returns a `kind: "webpage"` probe for HTML (unless `allow_html`); `download` then runs `webpage.download_page`. A cloud link that lands on an HTML page (sign-in, quota) fails with `login_required`; it is never saved as the file.
- gallery-dl is GPL: run only as `python -m gallery_dl` subprocess, for listing (`-J`). It never downloads; images come through `Net`. `gallery_hosts()` reads `--list-extractors` once (cached) for `can_handle`. Its own requests during listing are outside `net_guard` (separate process) — the URL is pre-checked and only sites with a gallery-dl extractor reach it.
- Downloads send `Accept-Encoding: identity`; with a `Content-Encoding` response the length is unknown (no size check).
- Live tests: GitHub works from the sandbox; Flickr and Hugging Face need CI. `ANYGET_LIVE_DRIVE_URL` / `ANYGET_LIVE_FLICKR_ALBUM` are optional repo variables for the Live tests workflow.

### Books / libraries / convert gotchas
- Standard Ebooks download links need `?source=download` (without it: an HTML "Your Download Has Started" page). `HttpGenericHandler` refuses HTML for links ending in a file suffix (`is_file_link`) and whenever the probe expected a non-HTML file but the GET answers HTML (`not_a_file`).
- `GET /api/books/search/stream` (SSE): `source` events (`{source, results}`, unranked) as each adapter answers, then `done` (ranked `BookSearch`). The web falls back to `/api/books/search` if the stream fails. `sources=` limits a search to some adapters (per-source retry).
- Word matching for titles uses `core/text.words` (keeps Devanagari/Arabic marks inside words; strips only Latin accents). archive.org hits in `/api/search` are re-ranked by `universal/relevance.rank_hits` (title/subject match, media intent words in en/hi/hinglish/ar, artist-name-only music matches pushed down).
- `anyget/books/<source>.py` each export `ADAPTER` (name, label, region, `search(ctx, query, limit)`, optional `key_setting`, `search_url` for link-only sources); `books/sources.py` lists them; `books/search.search_books` fans out with a per-source time limit and returns a status per source (`ok`, `needs_key`, `timeout`, `error`, `link_only`). Keyless adapters are skipped, never failed.
- Ranking is `books/ranker.rank` (pure). Access states: `full_view` (downloadable), `view_online`, `borrow_only`, `in_copyright`; anything but a full-view hit with formats gets library/buy links (`find_links`). Never add shadow libraries (`test_no_shadow_libraries_are_sources`).
- Standard Ebooks' OPDS feeds need a Patrons login, so the adapter reads the public search page and builds `/downloads/<author>_<title>.epub`. HathiTrust is lookup-by-ISBN/OCLC only and full view is "read online" (whole-book PDFs need a member login). NDLI is a search link only.
- `ANYGET_BOOK_SOURCES=gutendex,…` limits sources; `ANYGET_GUTENDEX_URL` points at a self-hosted Gutendex (e2e uses the fixture server's stand-in).
- `handlers/iiif_library.py` maps item pages to manifests (`manifest_url_for`) and refuses `rightsstatements.org/vocab/InC` items. Pages are `NNNN.jpg` in `downloads/<title>/`; `options.pdf` merges them (PDF is the job's main file). Library hosts get per-host limit 2.
- Conversions are jobs with the internal link `anyget:convert?job=…&to=…&lang=…`; the router passes `anyget:` links straight to the `convert` handler (no network). Inputs must be inside the downloads root; ffmpeg runs with `-protocol_whitelist file`. OCR writes `<name> (OCR).pdf` plus a `.txt` sidecar.
- defusedxml parses every XML answer (Gallica SRU, NDL OpenSearch). img2pdf/pikepdf/Pillow are Python deps; OCRmyPDF/Tesseract/Calibre are optional system tools (Docker `WITH_OCR=1`).
- Live tests for these hosts can't run in the sandbox (DNS); they run in the Live tests workflow. Status on GitHub runners (Nov 2026): book search, Gutenberg EPUB and OCR pass; Gallica answers 403, loc.gov answers 429 (search works, item JSON/manifests throttled), NDL search works (`dpid=ndl-dl-online`) but `www.dl.ndl.go.jp/api/iiif/<pid>/manifest.json` answered 404 for the hits found — verify the NDL manifest URL from a home connection before changing it again.

### Library / watch / settings gotchas
- Thumbnails (`library/thumbs.py`): made on the first `GET /api/library/{id}/thumb`, cached as `data/thumbs/<id>.webp` (a `.none` marker means "no picture", not retried). ffmpeg (`-protocol_whitelist file`) for video frames and audio covers, `pdftoppm` (poppler) for PDFs, Pillow for raster images; SVGs use the file itself. CI's API job installs ffmpeg + poppler for these tests.
- Tables: `library_item`, `watch`, `setting` live in the same SQLite file; `Database.create_all` imports their models. New nullable columns are still added by `_add_missing_columns`.
- `DownloadQueue.on_done` hooks (the library indexer) run as separate tasks after a job is `done`; `queue.stop()` waits for them (`wait_hooks`, 60 s). Never await slow work inside the job task: cancelling it resets the job to `queued`.
- Folder templates (`core/templates.py`) are rendered once per job after the probe and stored in `job.options["_folder"]`; `queue.job_dir(job)` is where its files and partials live. Conversions (`anyget:` links) don't use templates.
- `SettingsStore.load()` runs in `Services.build` and overrides env with saved values; only `settings_store.EDITABLE` fields can be saved. Secrets are write-only (`SettingsView.secrets` is a set/unset map). Concurrency changes call `queue.reconfigure()` (new jobs only); proxy changes need a restart (`restart_needed`).
- Watches: `watch/runner.WatchService.run` holds a lock, queues `initial` items on the first run (the rest become `seen_ids`), later at most 50 per run. Media watches also treat `entry.saved` (download archive) as seen. The scheduler (`WatchScheduler`) starts only in the API (`Services.start(recover=True)`) and when `watch_enabled`.
- Library files are served with `content_disposition_type="inline"` and `Content-Security-Policy: sandbox`; keep that header if you change the endpoint.
- The Settings page reserves the form's height in its skeleton (CLS); update `h-[166rem] sm:h-[115rem]` if the form grows a lot.

### PWA / extension / plugins / torrent gotchas
- PWA: `app/manifest.ts` (served at `/manifest.webmanifest`), icons in `public/icons/`, `public/sw.js`. The service worker is registered by the static inline `lib/pwa.ts` script in the root layout (production builds only, no React JS in the shell). It caches only `/_next/static/`, icons and the favicon, **never `/api/`**; bump `VERSION` in `sw.js` if its logic changes. The web Dockerfile must copy `public/`.
- Share target: the manifest's `share_target` posts GET `/share?title&text&url`; `[locale]/(app)/share/page.tsx` redirects to `/<locale>?url=…`, and `PasteBox` reads `?url=` once, clears it, and probes. Keep `/share` free of client JS.
- The install button reads `window.__anygetInstall` (the saved `beforeinstallprompt`) through `useSyncExternalStore`.
- Extension: plain ES modules, no bundler. `src/lib.js` is pure and tested; `scripts/build.mjs` writes `dist/chrome` and `dist/firefox` (only the `background` key and Firefox's gecko id differ) and store-only zips. Host permissions are localhost only; other addresses are requested at runtime (`optional_host_permissions`). Headless smoke test: Playwright `launchPersistentContext` with `channel: "chromium"` (the headless shell can't load extensions).
- Plugins (`anyget/plugins.py`): entry point group `anyget.handlers`, factory `make(net, settings)`, optional `priority` (default 85). Load only with `ANYGET_PLUGINS` (env only, not a UI setting: plugins are code). Results are in `Services.plugins` and `/api/health`.
- Torrent (`handlers/torrent.py`): always registered so magnet links get a clear message; `probe`/`download` require `settings.torrent_enabled` (UI setting) and libtorrent (`--extra torrent`). Peer traffic is outside the SSRF guard by nature; LSD/UPnP/NAT-PMP are off. Paths from metadata go through `safe_parts` (no `..`, no absolute). Tests use a fake libtorrent module.
- The Libraries page reserves the list height in its skeleton (`h-[77rem] sm:h-[39rem]`) and Settings reserves `h-[178rem] sm:h-[124rem]` (CLS). When measuring Lighthouse locally, build the web with the same `API_URL` the API listens on, or pages show their error state and CLS numbers are wrong.

### Deploy / auth gotchas
- **v2 owner sign-in** (`core/session.py`, `api/auth.py`, `docs/hosted.md`): `ANYGET_OWNER_EMAIL` + `ANYGET_OWNER_PASSWORD_HASH` (argon2id, `anyget hash-password`). The cookie `anyget_session` is HMAC-signed with a key mixed from the session secret and the password hash. `Settings.login_required` is true when an owner is set, `auth_mode=always`, or hosted (`Settings.hosted`: `ANYGET_PUBLIC` or a platform env var such as `RAILWAY_ENVIRONMENT`). Hosted without an owner or token → every request 401 `owner_required` (fail closed). Public paths: `/api/health`, `/api/auth/login|logout|me`.
- Cookie-signed writes need `X-Requested-With: anyget` (`CSRF_HEADERS` in `@anyget/shared`'s `createApiClient`); raw `fetch` writes in the web must add it too. Bearer-token clients (CLI, extension) don't need it.
- The middleware puts the user in `scope["state"]["user"]`; routes read it with `UserDep` (`api/deps.py`). Jobs, library items and watches have `user_id` (`core/users.OWNER_ID` = "owner" today); single-row routes answer 404 for another user's row. `core/ownership.adopt_rows` runs at every start: library/watch rows without a user go to the owner; jobs without a user are deleted when hosted or owner-protected (old public list), kept otherwise.
- Web: `proxy.ts` redirects to `/<locale>/login?next=` when there is no session cookie and `GET /api/auth/me` says `login_required` (cached 60 s, `lib/auth-gate.ts`; `API_URL` is read at run time there). `lib/api.call()` sends any 401 to the sign-in page. Tests that need a signed-in client use `tests/test_owner_auth.py`'s pattern.
- `core/auth.SecurityMiddleware` (pure ASGI, outermost) does access control, rate limits and security headers. It reads `app.state.services`, so it answers 503 until the lifespan has started; tests must use `with TestClient(...)`.
- "Through Cloudflare" means the request has `Cf-Connecting-Ip`, `Cf-Ray` or `Cf-Access-Jwt-Assertion`. Those requests need a valid Access JWT or the bearer token; everything else is local (ports are bound to 127.0.0.1) and allowed in `auth_mode=auto`. Next.js rewrites forward these headers to the API (`e2e/pwa.spec.ts` checks this). Don't add a proxy that strips them.
- JWKS: `https://<team>/cdn-cgi/access/certs` through `Net`, cached 1 h, re-read once (at most every 60 s) for an unknown `kid`.
- Rate limits apply to remote clients only (keyed by `Cf-Connecting-Ip`); the owner's local requests aren't limited, which keeps e2e and the web UI fast.
- API responses get `X-Frame-Options: DENY` unless they set their own: library file responses set `SAMEORIGIN` so the PDF preview iframe works.
- Web CSP lives in `next.config.ts` (production only; dev needs eval) and covers pages, not `/api/*`. Images may come from any https host (thumbnails); scripts are same-origin plus `'unsafe-inline'` for the theme/PWA inline scripts and Next's bootstrap.
- Backups (`anyget/backup.py`) use SQLite's online backup API; restore uses `tarfile` `filter="data"` plus its own path checks, and removes stale `-wal`/`-shm` files.

### Frontend gotchas
- First-load JS is at the 170 KB budget (Home ≈169.4 KB, Settings ≈169.3, Downloads ≈168.6, others ≈162–169). `e2e/budget.spec.ts` checks every page and fails CI if one goes over. Downloads was already ≈169.9 KB with real jobs before v2 (the convert menu's lazy chunk counts); keep `lib/api-convert.ts` separate from `lib/api-books.ts` and the 401 redirect lazily imported (`lib/sign-in.ts`). Do not add client JS to the shell (nav, layout): new sections go in the Ctrl+K menu and in Home's server-rendered "More sources" list; lazy-load anything not needed on first paint (`next/dynamic`, like the preview sheet, media preview, files preview, convert menu, format picker, video card and playlist view).
- `Button` has no `asChild` (Radix Slot was dropped to save bytes): style links with `buttonVariants()`.
- Media pills (`components/media/choice.tsx`) are native radios/checkboxes hidden inside labels; in Playwright click the label (`pick()` in `e2e/youtube.spec.ts`), not the input.
- No `tailwind-merge`: `cn()` is plain `clsx`, so components must not receive classes that conflict with their own (add a prop instead, see `NativeSelect.iconOnlyOnPhone`).
- Toasts are our own (`lib/toast.ts` + `components/ui/toaster.tsx`), not sonner. Language and theme use styled native `<select>` (`components/ui/native-select.tsx`), not Radix menus.
- next-intl messages are precompiled at build time (`next.config.ts`); ICU plurals need all Arabic forms (zero, one, two, few, many, other).
- RTL: wrap LTR values (sizes, speeds, hosts) with `isolate()` from `lib/format.ts`; don't rely on `<bdi>` auto-direction for strings that mix Arabic with numbers (Chrome resolves them as LTR).
- Live updates: one EventSource in `JobEventsBridge` writes into the TanStack Query `["jobs"]` cache; refetches are merged by `updated_at` (`mergeJobs`) so they never undo a newer live event. It refetches the list on every (re)connect, so a job that changed between the list request and the connection is not left stale.
- The shadcn registry may be unreachable from sandboxes; components in `components/ui` are written by hand in shadcn style.
- E2E downloads come from `e2e/fixture-server.mjs` (Range, Content-MD5, `?slow=1`), reachable because Playwright starts the API with `ANYGET_NET_ALLOWLIST=127.0.0.1:8200`.

## Working agreement for each phase
1. Read this file and `prompts/phase-NN-*.md`.
2. Build only that phase's deliverables. Keep handlers one-per-file.
3. Run `make check` (and `make e2e` when web changed). Fix everything red.
4. Update `CHANGELOG.md` and the status checklist above.
5. Commit with a Conventional Commit message (e.g. `feat: phase 2 core and security`).
