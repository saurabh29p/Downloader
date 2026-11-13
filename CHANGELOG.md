# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [2.0.0] - 2026-11-13

The v2 release: owner sign-in, Connections, universal search, Sections, the optional AI helper, the Reading Room look, in-app previews and the audio player.

### Fixed (v2 Phase 7 — polish)
- **Empty files** (0 bytes) are saved instead of failing with an internal error.
- **Downloads on phones:** a long technical error no longer pushes the page sideways. Unexpected errors show a plain message with the server's text under Details; only "the server answered …" stays inline.
- **Screen readers:** each download's title on Downloads is now a level-2 heading, so heading navigation no longer skips a level (Lighthouse accessibility 98 → 100).
- **Collapsible sections:** archive.org's Filters and the video page's automatic captions show their open/close arrow again (they looked like empty headings).
- **Keys and accounts point to Connections:**
  - The video page's sign-in hint now links to Connections, not Settings.
  - "Needs a key" notes on Libraries and Books link to that site's Connections entry instead of naming an environment variable.
  - The Code page and the "needs a key" error say "Connections" instead of `ANYGET_GITHUB_TOKEN` or a `.env` file.
- **Lighthouse script** (`pnpm --filter @anyget/web lighthouse`) works in containers: Chrome gets `--disable-gpu --disable-dev-shm-usage`, and a page whose trace fails to record is retried up to 3 times.

### Changed (v3 Phase 1 — product wording)
- Home's tagline reads "private, legal, no ads" (it said "free"). The Legal page says the rules apply on every plan, and the README describes the coming desktop and Android apps. The personal-use rules are unchanged.

### Docs (v3 launch plan)
- `docs/business-plan.md`: how AnyGet is sold (desktop app + Android app, free tier, Plus $19/year, Lifetime $39, Pro $79, no ads), who it is for, how people adopt it, costs and break-even, mobile, distribution, launch and legal risks, and the owner's checklist.
- `prompts/v3-phase-01…07`: one build prompt per launch phase (finish v2, licences and plan limits, desktop app, phone, website and checkout, opt-in telemetry and support, beta and launch).
- `CLAUDE.md`: v3 checklist and "Commercial rules".

### Added (previews, audio player, retention, honest AI states)
- **Open files in AnyGet** (Downloads and Library): the server checks a file's real type (first bytes, not only the name) and AnyGet picks a viewer:
  - **Video:** speed, subtitles from `.srt`/`.vtt` files next to it, and resume.
  - **PDF** (pdf.js, loaded on demand, byte ranges): pages, zoom, search.
  - **EPUB:** contents, font size, saved position. Chapters arrive as plain text blocks; the book's own HTML never runs.
  - **Text:** paged, with search. **Pictures:** zoom, fit, full screen, previous/next, keyboard.
  - Everything else gets a clear reason plus Download / Open.
- **Audio player** that keeps playing across in-app navigation (one `<audio>` in the app shell), with a mini-player, Media Session lock-screen controls and resume. Starting any player pauses the others.
- **Retention** (`ANYGET_RETENTION_DAYS`, default 7, 0 = off): removes old downloads daily.
  - Grace period, then only indexed files inside the downloads folder.
  - Never touches active downloads or files tagged `keep`, never follows symlinks.
  - Library entries stay with Download again.
  - `GET /api/retention`, `POST /api/retention/run` (dry run by default), `anyget cleanup [--apply]`.
- API: `/api/library/{id}/info`, `/text`, `/epub`, `/epub/{n}`, `/subtitles/{n}`, `/api/library/by-job/{job_id}`.

### Changed
- **AI helper:** OpenRouter failures are told apart: no key, bad key, no credits, refused, rate limited, provider error, network, daily limit, bad answer.
  - Settings and the search page show the reason; no answer card is ever made without AI.
  - 429 is no longer retried with long back-offs; after "no credits" or a refused key, AI pauses for 10 minutes.
- **TMDB:** a refused key reports "check the saved key" instead of "add a key".
- **Retry** also downloads again a file that retention removed.

### Fixed
- **Downloads:** the page no longer shows 0 for All/Done while the list is loading or the live connection reconnects.
  - Stream events are reconciled with list responses that were in flight: no lost, duplicated or resurrected jobs.
  - A failed background refresh keeps the last list.

### Added (v2 Phase 6 — "The Reading Room" UI)
- **New look:** Paper (light) and Ink (dark) themes with a saffron accent and indigo links, and a tint per section (stripes and line art only, never text colour). Every text colour pair meets WCAG AA.
- **Type:** Fraunces for headings, Inter for the interface, JetBrains Mono for file facts, plus Noto Sans Devanagari and Noto Naskh Arabic. All fonts are self-hosted; the script fonts load only on pages that use them.
- **Layout:**
  - A left rail on desktop (Home, Sections, Downloads, Library, Watches, Connections, Settings, plus a "Jump to…" button for Ctrl+K).
  - A five-item bottom bar on phones. The YouTube tab is gone (Video lives under Sections).
  - Content is up to 1280 px wide.
- **Home:**
  - A large universal bar with rotating example searches (CSS only, still under reduced motion) and mode chips (All, Movies, Books, Music, Video, Declassified, More) that search inside a section.
  - The sections drawn as card-catalogue drawers (Declassified gets a red stamp).
  - "Continue" shows your latest downloads; "Try these" offers example searches.
  - The "videos coming soon" copy is gone.
- **Interactions:**
  - A step indicator while a link is checked: Reading link → Finding formats → Ready.
  - Drop a link or a `.txt` list anywhere in the app.
  - Toasts can carry an Undo button: removing a download waits for the toast, so Undo brings it back.
  - Downloads has a compact queue, ETA in mono, and "Retry all failed".
- **Index cards** for search results and book results: a call number (kind · source · year), a serif title, and a red rule.
- **Library:**
  - Full-text search inside files: OCR text, PDF text layers (`pdftotext`), EPUBs, HTML and text files, through an SQLite FTS5 index, with snippets.
  - Filters by section, source site and licence; tags are shown as "Collections".
  - Downloads started from search remember their section and licence.
- **Settings** are grouped General, Downloads, AI helper, Connections and Advanced. Server details (download folder, proxy, per-site limits, torrents, yt-dlp) and env variable names appear only under Advanced.
- **Server status** moved from Home to Help.

### Changed
- `@anyget/shared`'s `createApiClient` is now a small fetch wrapper typed with openapi-fetch's types. The API is the same (`{ data } | { error }` plus `response`), and it saves ~2.5 KB on every page.

### Added (v2 Phase 5 — optional AI helper)
- **OpenRouter brain** (`anyget/llm/`), used only when an OpenRouter key is set (Connections or `OPENROUTER_API_KEY`); everything works without it.
  - Calls go through the SSRF-guarded client.
  - Each call sends the fallback `models` list, `provider: {require_parameters, sort: latency}` and a strict JSON-schema answer format.
  - Answers are validated with Pydantic, with one retry; after that AnyGet falls back to the keyword search.
- **What it does:**
  - Understands searches and questions in English, Hindi, Hinglish and Arabic.
  - Re-ranks results.
  - Writes a short answer card with numbered sources for questions, in the language you asked in.
  - Suggests searches on section pages.
- **Models** follow the v2 prompt: router `gemini-2.5-flash-lite` → `gpt-5-nano` → `gemma-4-31b-it:free`; answers `gemini-3.1-flash-lite` → `deepseek-v3.2`.
  - `ANYGET_LLM_ROUTER_MODELS` / `ANYGET_LLM_SUMMARY_MODELS` override them.
  - **Free mode** (Settings) uses only `:free` models.
  - `anyget llm-models` checks the IDs against OpenRouter, and CI runs it as an informational step.
- **Limits and cost:** a daily cap (`ANYGET_LLM_DAILY_LIMIT`, default 500); 24 h caching of plans, answers and suggestions in SQLite; Settings → AI helper shows today's calls and the cost OpenRouter reports.
- **Privacy:** prompts carry only what you typed and result metadata (titles, sources, years). A test checks that no keys or tokens reach the payload.
- **API:**
  - `/api/universal` adds `rerank` and `answer` events.
  - New: `GET /api/sections/{id}/suggestions` and `GET /api/llm`.

### Added (v2 Phase 4 — Sections)
- **Sections:** Movies, Books, Music, Video, Declassified and More (Maps, Newspapers, Photos, Manuscripts, plus archive.org, Wayback, Code, Images and Libraries).
  - They appear on Home, at `/sections` and in Ctrl+K.
  - Each section has a hero, ready-made searches and a search scoped to the section.
  - Each also has "Also search on" links to official sites that have no open API, with your query filled in.
- **Ready-made searches** come from the v2 prompt (for example "Classic Hindi films (public domain)", "Premchand stories", "1940s Hindi film songs (78rpm)", "NASA mission footage", "JFK assassination files", "Delhi before 1900", "15 August 1947 front pages", "Sanskrit manuscripts"). Some are narrowed to archive.org collections such as Feature Films, Film Noir, Prelinger, the Great 78 Project and Old Time Radio.
- **Movies, where to watch:** with a free TMDB key (Connections or `TMDB_API_KEY`), movie cards show the poster, year, rating, cast, trailer and where to watch in India (stream, free or with ads, rent, buy).
  - Copyrighted films are never offered as downloads.
  - Public-domain classics come from archive.org.
  - There are no torrent, piracy or mirror sources, and a test checks this.
- **Declassified** searches archive.org and links to the CIA Reading Room, FBI Vault, US and UK National Archives, MuckRock and The Black Vault (officially released records only).
- **Photos** search Wikimedia Commons, with each file's licence; downloads keep the original file.
- **API:** `GET /api/sections[/{id}]` (presets, links, `needs_key`). `/api/universal` takes `preset` with `section`.

### Added (v2 Phase 3 — universal search)
- **One box for everything.** `GET/POST /api/universal` streams Server-Sent Events: `plan`, then one `source` event per source as it answers, then `done`.
  - The input is classified as links, a search or a question (English, Hindi, Hinglish, Arabic) and its language detected.
  - A keyword router builds the v2 router plan (kind, intent, media, language, queries, answer_needed) and needs no AI. Phase 5's optional AI router uses the same shape and falls back to it.
- **Sources at once, each with a time limit:** archive.org, free books, worldwide libraries and YouTube search.
  - Results become cards with media type, licence (Public domain, Creative Commons, Rights reserved, Streaming only, or "check the licence"), year, creator, formats, a download link when one is legal, and a relevance score that works across sources.
  - Media words narrow the sources. For example, "taj mahal film" asks archive.org (movies only) and YouTube, for "taj mahal".
- **Search page** (`/search?q=`): results arrive as cards, with tabs per media type and live counts. Each card has Preview, Download, Save to Library (tagged "saved") and Open source; a Retry appears when a source doesn't answer in time.
- **Home:** words that aren't a link open the search. Ctrl+K has "Search for …" for whatever you type.
- `ANYGET_UNIVERSAL_SOURCES` limits which sources are asked (e2e asks only the books stand-in). Jobs accept `tags`, which the Library applies to their files.

### Added (v2 Phase 2 — Connections)
- **Connections page** (in the main nav, replacing the YouTube tab; YouTube stays in Ctrl+K and Home):
  - Sign-in sites by cookies.txt: YouTube, Instagram, X, Facebook, Reddit, Vimeo, Patreon, archive.org.
  - Key sites: GitHub, Hugging Face, Civitai, Kaggle, TMDB, OpenRouter, Europeana, DPLA, Trove, DigitalNZ, BHL, DDB.
  - Each site shows Connected, Expired (from the cookies' own expiry), Set on the server, or Not connected, with the date it was connected.
- **One cookies.txt for many sites:** "Add cookies.txt" keeps only the cookies of the listed sites, one connection each; cookies for any other site are dropped. Each site card also takes its own file.
- **Encrypted at rest** with Fernet (`ANYGET_SECRETS_KEY` from `anyget gen-key`, or a key made once in `data/secrets.key`). Values are never returned or logged; the page shows status and dates only.
- **yt-dlp uses the link's site cookies** when probing and downloading (only that site's cookies, in a 0600 file for the job), and that site's optional proxy (HTTP or SOCKS).
- **Key connections fill the matching settings**, so every source keeps working; removing one brings back the server's environment value. `TMDB_API_KEY` and `OPENROUTER_API_KEY` are read too.
- **Test** checks GitHub, Hugging Face, TMDB and OpenRouter keys with one small request each; cookie connections are checked from their expiry dates, with no request.
- "Connect your <site> account" on a failed download links to that site's card (`/connections#youtube`).

### Changed
- API keys and cookies are no longer part of Settings. On the first start, keys saved there and `data/cookies.txt` move into Connections, and the plain-text copies are deleted.
- `/api/settings/cookies` and `/api/settings/keys` are removed (use `/api/connections`).
- Backups include `data/secrets.key` and `data/session.key` when those keys are kept in the data folder.

### Security (v2 Phase 1 — lock it down)
- **Owner sign-in.** Set `ANYGET_OWNER_EMAIL` and `ANYGET_OWNER_PASSWORD_HASH` (from `anyget hash-password`, argon2id). `POST /api/auth/login` sets a signed, HTTP-only session cookie (30 days; `ANYGET_SESSION_SECRET`, or a random key kept in `data/session.key`). Changing the password signs every session out.
- **Every `/api/*` route needs a sign-in** (the session cookie, `Authorization: Bearer ANYGET_API_TOKEN`, or Cloudflare Access) except `/api/health` and `/api/auth/*`. Before this, a hosted AnyGet (Vercel → Railway) treated every request as local, so its API was open.
- **Fails closed when hosted.** On Railway and similar platforms (detected from their env vars, or `ANYGET_PUBLIC=1`), an AnyGet without an owner refuses every request with a message saying what to set.
- **CSRF:** cookie-signed writes must send `X-Requested-With: anyget` (the website always does). Sign-in attempts are limited to 5 a minute per client and 30 a minute in total.
- **Private by user.** Jobs, library items and watches carry a `user_id`; lists, files, live events and actions only show the signed-in user's own. On a hosted or owner-protected AnyGet, the old shared job list is cleared once; files stay on disk and in the Library.
- **Website:** a sign-in page (`/<locale>/login`), visitors without a session are sent there, any 401 returns there, and Settings has Sign out.

### Fixed
- **Images keep their format.** Wikimedia Commons/Wikipedia `File:` pages download the original file (new `wikimedia` handler, SHA-1 checked, licence shown) instead of being taken by yt-dlp and saved as `.mp4`. Direct image links never go to yt-dlp or gallery-dl. The preview shows the picture and a "Download image" button.
- **No web pages saved as books.** Standard Ebooks links use `?source=download` (the old link opened a "Your Download Has Started" page). A link to a book or file that answers with HTML fails with `not_a_file`, and nothing is saved.
- **Plain error messages with a fix.** 403s, bot checks and sign-in walls (YouTube, X, Reddit, Vimeo, Instagram, Facebook) show a short message and a "Connect your <site> account" link; the raw yt-dlp text is under "Details".
- **Library thumbnails** for videos (a frame), PDFs (first page), audio (cover art) and images (resized), made on first view and cached in `data/thumbs/`.
- **OCR works on Railway:** the API image always has OCRmyPDF, Tesseract (English, Hindi, Arabic) and poppler. `WITH_OCR=1` adds more languages.
- **Book search streams** each source's results as they arrive (`GET /api/books/search/stream`, SSE) with a "Retry" for sources that timed out or failed (`sources=` parameter).
- **Search relevance:** archive.org results are ranked by title and subject match and by the media the words ask for, so "Taj Mahal" finds the monument before the musician's concerts. Hindi and Arabic words are no longer split into single letters when matching titles.

## [1.0.0] - 2026-11-05

First release: everything below, plus worldwide access.

### Added (Phase 10 — deploy and release)
- **Access control in the API:**
  - Cloudflare Access JWTs are verified: RS256 against the team's published keys (cached, re-read once when the key id changes), with AUD, issuer and expiry checked.
  - A bearer token (`ANYGET_API_TOKEN`) is accepted for the CLI, the extension and scripts.
  - Requests from this computer are allowed. Requests that came through Cloudflare without Access are refused (fail closed). `ANYGET_AUTH_MODE=always` requires sign-in everywhere.
- **Per-client rate limits** for requests from outside (all requests and writes separately, `Retry-After` on 429).
- **Security headers:**
  - The API sends `nosniff`, `X-Frame-Options`, `Referrer-Policy`, `COOP`, `Permissions-Policy` and a strict `default-src 'none'` CSP. Swagger has its own CSP, and library files stay sandboxed and frameable only by AnyGet itself.
  - Website pages (production builds) send a CSP with same-origin scripts and no `eval`, plus the same headers.
- **Cloudflare Tunnel:** `docker-compose.tunnel.yml` (cloudflared 2026.10.7, unprivileged), `make up-public`, and `docs/deploy.md`. The guide covers exporting DNS first, Cloudflare and Hostinger nameservers, the tunnel and route, Access with One-time PIN, tokens for the CLI and extension, and troubleshooting.
- **Tailscale fallback** with `tailscale serve`: `docs/tailscale.md`.
- **Backups:** `make backup` / `make restore FILE=…` and `anyget backup create|restore`.
  - Backups take a consistent online SQLite copy, plus cookies and download archives (optionally `.env`), and are written 0600.
  - Restore refuses unsafe paths and foreign archives, and won't run while the containers are up.
- **Release workflow:** tags `v*.*.*` build and push `ghcr.io/<owner>/anyget-api` and `anyget-web`, build the extension, and publish a GitHub release with this changelog's notes.

### Changed (Phase 10)
- The browser extension sends the Cloudflare Access cookie with its requests (`credentials: "include"`).
- All packages are version 1.0.0.

### Added (Phase 9 — PWA, extension, plugins, torrent)
- **Installable web app (PWA):**
  - Manifest with icons, a service worker and an "Install the app" button in Settings.
  - The service worker caches only the app's static files (never API answers or downloads) and shows a short offline note when the server is unreachable.
  - Android **Share → AnyGet** works through a Web Share Target: `/share` finds the link in the shared text and opens its preview on Home. Home also accepts `?url=`.
- **Browser extension** (`apps/extension`, Manifest V3, Chrome and Firefox):
  - Right-click a link, image, video or page, or click the toolbar button, to send it to your AnyGet.
  - The options page sets the address and an optional token. A non-local address asks permission for that one site.
  - `make extension` builds both zips. CI uploads them as an artifact.
- **Termux:** `scripts/termux/termux-url-opener` sends links shared to Termux to your AnyGet, or downloads on the phone with the CLI. `docs/termux.md` explains both setups.
- **Plugins:** extra handlers come from installed packages through the `anyget.handlers` entry point group.
  - Only plugins listed in `ANYGET_PLUGINS` load (`*` for all).
  - A broken plugin is reported in `/api/health` and never stops the app.
  - `examples/anyget-plugin-example` (xkcd comics) shows the contract. It has its own tests, which CI runs.
- **Torrents (optional, off by default):** magnet links and `.torrent` files through libtorrent (`uv sync --extra torrent`).
  - Turn them on in Settings, which also has "keep sharing".
  - The file list comes first, so you can pick files.
  - Unsafe paths in torrent metadata are refused, `.torrent` files are fetched through the guarded client, and local peer discovery is off.

### Changed (Phase 9)
- Magnet and `.torrent` links route to the torrent handler, which explains that torrents are off instead of the old "not supported yet".
- `/api/health` lists installed plugins (loaded or not, with the reason) and whether torrents are available.
- The web Docker image now includes `public/` (icons, service worker).

### Added (Phase 8 — library, watch, settings, help)
- **Library:** every finished download (and anything you copy into the downloads folder, after a scan) is indexed with its kind, size, sha256, source and tags.
  - Search, filter by kind or tag, and see which files are copies of others (same sha256, or the same source saved again). Copies are never deleted for you.
  - Previews: video and audio with seeking (HTTP Range), images, PDF in the browser viewer, and an EPUB text preview (standard library only).
  - Files are served inline with `Content-Security-Policy: sandbox`, so a downloaded HTML or SVG file can't run scripts.
  - Re-download from the source, remove from the library with or without the file. CLI: `anyget library [--scan]`.
- **Folder templates:** `{type}/{source}/{year}/{month}/{title}` decide where new downloads go, with every part sanitized. A job keeps its folder when resumed.
- **Watches:** channels and playlists (yt-dlp) and archive.org collections are checked on a schedule (every hour up to every week) and only new items are queued.
  - The first run fetches the newest few and marks the rest as seen. Items already in a download archive count as seen.
  - The API server runs a scheduler. The UI and CLI (`anyget watch add|list|run`) can also run a watch now.
- **Settings saved in the app** (SQLite, overriding `.env`):
  - folder template, downloads at once, per-site limits, speed limit (yt-dlp `ratelimit` and an HTTP read throttle), proxy (applies after restart), contact email, and watches on/off
  - API keys, which are write-only: only "set / not set" is ever returned
- **yt-dlp update check** against PyPI (check only, never self-updating).
- **Clipboard watcher:** `anyget watch-clipboard` offers every link you copy; `--auto` skips the question. Needs the optional `desktop` extra (pyperclip).
- **Web:** Library page (grid, filters, tags, preview sheet), Watches page, a full Settings page (downloads, speed and limits, network, API keys, yt-dlp check, cookies), and server-rendered Help and Legal pages linked from the footer and Ctrl+K. en/hi/ar.

### Fixed (Phase 8)
- After-download work (library indexing) runs in its own task, so stopping the app while a file is being hashed can no longer put a finished job back in the queue.

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

[Unreleased]: https://github.com/saurabh29p/Downloader/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/saurabh29p/Downloader/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/saurabh29p/Downloader/releases/tag/v1.0.0
