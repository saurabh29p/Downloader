# AnyGet — project memory for Claude Code

One tool: paste any public link, get the file. A FastAPI core (URL router → handlers → SQLite job queue with SSE progress), a Next.js website and a Typer CLI. Runs on the user's own computer with Docker Compose (`make up`); reachable worldwide only through Cloudflare Tunnel + Access (Tailscale as fallback). Free tools only. **No LLM at runtime** — Claude Code only writes the code.

Read this file at the start of every session. The full research doc lives in `docs/plan.md`; phase prompts live in `prompts/`.

## Current status

- [x] Phase 0 — prerequisites, CLAUDE.md
- [x] Phase 1 — monorepo skeleton
- [x] Phase 2 — core and security
- [x] Phase 3 — website foundation
- [ ] Phase 4 — YouTube and media (next)
- [ ] Phases 5–10 — see roadmap below

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

### Frontend gotchas
- First-load JS is at the 170 KB budget (≈169.6 KB on Home). `e2e/budget.spec.ts` fails CI if it goes over: lazy-load anything not needed on first paint (`next/dynamic`, like the preview sheet and command palette).
- No `tailwind-merge`: `cn()` is plain `clsx`, so components must not receive classes that conflict with their own (add a prop instead, see `NativeSelect.iconOnlyOnPhone`).
- Toasts are our own (`lib/toast.ts` + `components/ui/toaster.tsx`), not sonner. Language and theme use styled native `<select>` (`components/ui/native-select.tsx`), not Radix menus.
- next-intl messages are precompiled at build time (`next.config.ts`); ICU plurals need all Arabic forms (zero, one, two, few, many, other).
- RTL: wrap LTR values (sizes, speeds, hosts) with `isolate()` from `lib/format.ts`; don't rely on `<bdi>` auto-direction for strings that mix Arabic with numbers (Chrome resolves them as LTR).
- Live updates: one EventSource in `JobEventsBridge` writes into the TanStack Query `["jobs"]` cache; refetches are merged by `updated_at` (`mergeJobs`) so they never undo a newer live event.
- The shadcn registry may be unreachable from sandboxes; components in `components/ui` are written by hand in shadcn style.
- E2E downloads come from `e2e/fixture-server.mjs` (Range, Content-MD5, `?slow=1`), reachable because Playwright starts the API with `ANYGET_NET_ALLOWLIST=127.0.0.1:8200`.

## Working agreement for each phase
1. Read this file and `prompts/phase-NN-*.md`.
2. Build only that phase's deliverables. Keep handlers one-per-file.
3. Run `make check` (and `make e2e` when web changed). Fix everything red.
4. Update `CHANGELOG.md` and the status checklist above.
5. Commit with a Conventional Commit message (e.g. `feat: phase 2 core and security`).
