# AnyGet: research and build plan (reference)

The research tables from the original "Universal Downloader: Research and Build Plan", kept in the repo so every phase can refer to them. Rules and the roadmap live in `CLAUDE.md`.

## archive.org

| Feature | Endpoint / tool | Notes |
|---|---|---|
| Search | `https://archive.org/advancedsearch.php?q=...&fl[]=identifier&output=json` | filters: mediatype, collection, year, language, creator |
| Deep paging | `https://archive.org/services/search/v1/scrape?q=...&fields=...` | cursor based, for big collections |
| Item metadata | `https://archive.org/metadata/<identifier>` | all files with format, size, md5 |
| Download file | `https://archive.org/download/<identifier>/<file>` | supports Range resume; verify md5 |
| Bulk / filters | `ia download <id> --glob="*.mp3"` | pick by format: Original, VBR MP3, PDF, EPUB, DjVu |
| Collections | search `collection:<name>` | browse, then queue selected items |
| Wayback list | `https://web.archive.org/cdx/search/cdx?url=...&output=json&collapse=digest` | snapshots on a timeline |
| Wayback raw | `https://web.archive.org/web/<timestamp>id_/<url>` | `id_` gives the original file without the toolbar |
| Save page now | `web.archive.org/save` (needs login keys) | optional, later phase |

UI: search box, filters, result cards, item page with file table and checkboxes, "download all of format X".

## YouTube (yt-dlp options)

| Feature | How |
|---|---|
| Single video | probe with `extract_info`, download chosen format; merge video+audio with ffmpeg |
| Quality picker | best, 2160p, 1440p, 1080p, 720p, 480p, audio only; `-f "bv*[height<=1080]+ba/b"` style selectors |
| MP3 extraction | `-x --audio-format mp3 --audio-quality 0`, embed thumbnail and tags |
| Playlists | expand entries, select all or some, keep playlist order in filenames |
| Channels | Videos, Shorts and Live tabs; date range and max count; `--download-archive` to skip already saved |
| Shorts | like normal videos; vertical format kept |
| Subtitles | manual and auto captions, pick languages, save `.srt` or embed |
| Metadata | title, uploader, date, description, chapters, thumbnail, `info.json` |

Keep yt-dlp updated. Own uploads, Creative Commons or permitted content only. Members-only and paid content is out of scope.

## Books: rare, old and lost

One search by title, author or ISBN asks all sources at once, merges results, and ranks the best legal downloadable copy: full-view first, then best format (EPUB → text PDF → scanned PDF → page images), then scan quality and completeness.

| Source | Access | Best for |
|---|---|---|
| Internet Archive texts | advancedsearch + metadata APIs | old scans; open items only, borrow-only skipped |
| Open Library | `openlibrary.org/search.json`, ISBN API | editions by ISBN; links to IA scans; borrow-only not downloadable |
| Project Gutenberg | Gutendex (`gutendex.com/books`) | clean public-domain EPUB and text |
| Standard Ebooks | OPDS feed | well-formatted public-domain EPUB |
| Wikisource (all languages) | MediaWiki API, EPUB export | transcribed old texts |
| HathiTrust | Bibliographic API, full view only | public-domain academic books |
| Google Books | Books API `filter=free-ebooks` | public-domain scans with download allowed |
| Library of Congress, DPLA, Europeana, Gallica | JSON APIs and IIIF | US and European rare books |
| NDL Japan, National Digital Library of India | search API and IIIF where open | Asian rare and old books |
| Biodiversity Heritage Library | BHL API (free key) | old science and natural history |
| Wayback Machine | CDX + `id_` raw | lost web texts and dead ebook links |

Handler: `handlers/books.py` with one adapter per source in `anyget/books/` and a ranker. In-copyright out-of-print books are shown as "not legally downloadable" with library or buy links.

## Worldwide sources by region

Many national libraries publish IIIF manifests, so one IIIF handler (download every page image at full size, optionally merge to PDF) covers most. Some APIs need a free key, stored in Settings.

| Region | Libraries and archives | Access |
|---|---|---|
| Global | Internet Archive, Wayback, Library of Congress (incl. World Digital Library), UNESCO archives, Wikimedia Commons, HathiTrust (PD), Project Gutenberg, Open Library | archive.org APIs, loc.gov `?fo=json`, IIIF, MediaWiki API |
| Europe | Gallica, Europeana, British Library, Deutsche Digitale Bibliothek, Delpher, Biblioteca Digital Hispánica / BNE, Internet Culturale, Russian State Library public domain | IIIF, Gallica SRU, Europeana API (free key), DDB API (free key) |
| Asia | NDL Japan, National Library of Korea, National Digital Library of India, China public digital libraries where openly accessible, NLB Singapore | NDL IIIF and search API, IIIF where offered, page handler fallback |
| Oceania | Trove (Australia), Papers Past / DigitalNZ | Trove API v3 (free key), DigitalNZ API (free key) |
| Middle East and Africa | Qatar Digital Library, WDL items on LoC, Bibliotheca Alexandrina, Endangered Archives (BL), Digital Innovation South Africa | IIIF, page handler |
| Americas | Library of Congress, DPLA, Biblioteca Nacional Digital Brasil, BDH items, Canadiana, Mexico and Argentina national libraries | DPLA API (free key), IIIF, page handler |
| Regional video and music | Bilibili, Niconico, VK, Youku, Dailymotion, Vimeo, SoundCloud, Bandcamp, Mixcloud, Rutube, NHK and many broadcasters | yt-dlp extractors (`yt-dlp --list-extractors`) |

- Multi-language: UI strings in i18n files; search queries sent as UTF-8; language filter in archive.org and Europeana search.
- Geo-blocks: show a clear "not available in your region" message. No bypass.

## Smart extras

| Extra | What it does | Phase |
|---|---|---|
| Batch URL lists | paste many links or import a `.txt` | 2 |
| Checksum verification | md5/sha1 when the source gives one | 2 |
| Universal search | one box: archive.org, books, YouTube, libraries | 7 |
| Conversion | ffmpeg for media; img2pdf; EPUB→PDF via Calibre if installed | 7 |
| OCR for scanned books | Tesseract via OCRmyPDF, many languages | 7 |
| Clipboard watcher | desktop: copied links appear as suggested jobs | 8 |
| Scheduled watch downloads | new channel uploads, new items in a collection | 8 |
| Auto-organize and dedupe | folder templates by type/source; skip duplicates by hash or ID | 8 |
| Tags and metadata | tag jobs and files; store source metadata in SQLite | 8 |
| Offline library browser | browse, search, preview saved video, audio, images, PDF, EPUB | 8 |
| Proxy and rate limits | global proxy, speed limit, per-host limits | 8 |
| Android share-to-app and Termux | PWA share target, or Termux script | 9 |
| Browser extension | right-click / toolbar sends the page to the local app | 9 |
| Plugin system | handler plugins via Python entry points | 9 |

## Download manager features

| Feature | How |
|---|---|
| Queue | SQLite jobs table: queued, probing, downloading, paused, done, failed |
| Concurrency | global limit (default 3) plus per-host limit (archive.org 2) |
| Resume | HTTP Range with `.part` files; yt-dlp continues partial files |
| Format and quality picker | probe first: best video, 1080p, 720p, audio mp3/m4a, subtitles |
| Playlists and channels | expand to items, select all or some, date range filter |
| Metadata | `info.json`, embedded thumbnail and tags, archive.org `_meta.xml` |
| History | searchable list, open folder, re-download, skip duplicates |
| Integrity | md5/sha1 when provided |
| Cookies (own account) | optional `cookies.txt` import for sites the user is legally logged in to |
| Settings | download folder, folder templates, speed limit, proxy, API keys, language, theme, auto-update yt-dlp |

## Website

### Sitemap

| Page | Purpose |
|---|---|
| Home | one universal paste box with auto-detect chip, batch drop, recent jobs |
| Search | one query across all sources, tabs by type |
| YouTube | videos, playlists, channels, Shorts, MP3, subtitles, quality |
| archive.org | search, filters, item page with file picker, collections |
| Wayback | snapshot timeline, raw `id_` download |
| Books | title/author/ISBN search; best legal copy card |
| Code and AI | repos, files, releases, Hugging Face, prompt repos |
| Images | galleries with grid preview |
| Libraries | worldwide libraries by region |
| Downloads | live queue, pause, resume, retry |
| Library | offline browser with previews, tags |
| Watch | schedules for channels and collections |
| Settings | folders, limits, proxy, keys, language, theme |
| Help and Legal | guides and the legal rules |

### Key user flows
1. **Paste and download:** paste link → auto-detect source → preview drawer → choose format/quality → Download → live progress → open in Library.
2. **Book to best legal copy:** search title/author/ISBN → ranked results, best copy card on top → download EPUB or PDF → optional OCR.
3. **archive.org item to files:** search with filters → open item → tick files or "all of format X" → queue → verify md5.

## Testing and packaging
- pytest + respx (mocked HTTP) for the router and every handler; fixture JSON for archive.org metadata and CDX so tests run offline.
- Small `live` suite with public-domain/CC links only, run manually.
- Web: Vitest, Playwright, axe.
- Docker: api image `python:3.12-slim` + ffmpeg + git + Deno (optional Tesseract); web image Next.js standalone on Node 24; healthchecks; ports `127.0.0.1:3000` and `127.0.0.1:8000`.
- Bind mounts `./downloads` and `./data`. One command start: `make up`.
- Android: install the site as a PWA or use Termux for the CLI.

## Worldwide access (deployment) — phase 10

> **Before changing nameservers:** export every DNS record at the current registrar (A, CNAME, MX, TXT for SPF, DKIM, DMARC). Website and email depend on them. Check Cloudflare imported all of them before switching.

1. Add the domain to Cloudflare (Free). Compare imported records with the export; keep mail records DNS-only.
2. Change nameservers at the registrar (e.g. Hostinger hPanel → Domains → DNS / Nameservers → custom). Turn off DNSSEC first if on.
3. Create a tunnel: Zero Trust → Networks → Tunnels → Cloudflared → Docker; put the token in `.env` as `TUNNEL_TOKEN`.
4. Routes: `dl.<domain>` path `api/*` → `http://api:8000`, everything else → `http://web:3000`.
5. Protect with Access: self-hosted app for `dl.<domain>`, allow your email, One-time PIN (free plan covers up to 50 users).
6. `make up-public`, check the tunnel shows Healthy, open on a phone over mobile data.

No router ports are opened. Fallback without a domain: Tailscale on computer and phone, with `tailscale serve` for HTTPS.

## Key links
- yt-dlp: https://github.com/yt-dlp/yt-dlp
- gallery-dl: https://github.com/mikf/gallery-dl
- internetarchive: https://github.com/jjjake/internetarchive
- Internet Archive developer docs: https://archive.org/developers/
- IIIF: https://iiif.io/
- Europeana APIs: https://pro.europeana.eu/page/apis
