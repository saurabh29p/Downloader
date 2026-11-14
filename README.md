# AnyGet

Paste any public link, get the file. A universal downloader and legal-copy finder that runs on your own computer: no ads, no tracking.

AnyGet is free, open-source software (MIT). You run it yourself, on your own computer or server; nothing is sent to us.

- **Core:** FastAPI + SQLite job queue with live progress (SSE), a URL router that sends each link to the best handler (yt-dlp, archive.org, gallery-dl, git, IIIF libraries, plain HTTP …).
- **Website:** Next.js + Tailwind + shadcn/ui, English / Hindi / Arabic (RTL), installable as a phone app.
- **CLI:** `anyget` (Typer + Rich).
- **Search everything:** one box for links, searches and questions, across legal sources, with Sections (Movies, Books, Music, Video, Declassified, More). An optional AI helper (OpenRouter) improves it; everything works without it.
- **Read, watch and listen in the app:** saved files open in AnyGet itself: video (speed, subtitles), PDF, EPUB, text and pictures, and audio in a player that keeps going while you move between pages.
- **Access from anywhere:** hosted (Railway + Vercel, owner sign-in: [docs/hosted.md](docs/hosted.md)), or Cloudflare Tunnel + Access, or Tailscale.

> Personal use only. Download what you own, what is public domain or openly licensed, or what the site allows. No DRM, no shadow libraries, no geo-block or paywall bypass. See `CLAUDE.md`.

## Quick start

```sh
cp .env.example .env
make setup     # install deps (uv + pnpm)
make dev       # api on :8000, web on :3000
# or, with Docker:
make up        # http://127.0.0.1:3000
```

## Video and audio sites

The YouTube page (or `uv run anyget get <link> -q 720`, `-x mp3`) downloads videos, Shorts, playlists and channels from YouTube, Vimeo, Bilibili, SoundCloud and many more through yt-dlp, with ffmpeg for merging/conversion and Deno for YouTube's challenges. Members-only, paid, DRM, private and region-blocked videos are reported, never bypassed.

Sites change often, so keep yt-dlp current:

```sh
cd apps/api && uv lock --upgrade-package yt-dlp && uv sync   # local
make up                                                      # rebuilds the Docker image with the new lock
```

Then run `make live` (real downloads of Creative Commons/test media in the Docker test image) to check it still works.

## Previews and listening

Open a file from **Downloads** or the **Library**:

- **Video:** your browser's player (play, seek, volume, full screen), plus speed, subtitles from `.srt`/`.vtt` files saved next to the video, and "resume where you left off". Some formats (MKV, MOV) don't play in every browser. AnyGet says so and offers Download; it never transcodes on its own.
- **Audio:** plays in a mini-player at the bottom that survives page changes, with lock-screen controls where the browser supports them. On phones, playback with the screen locked depends on the browser and the OS. See Help → Listening and watching.
- **PDF** (pages, zoom, search), **EPUB** (contents, font size, remembers your place; the book's own HTML and scripts never run), **text** (paged, search) and **pictures** (zoom, full screen, previous/next).
- Office files, archives and unknown types get a short reason plus Download / Open.

## How long files are kept

Downloaded files are removed after **7 days** by default (`ANYGET_RETENTION_DAYS`, or Settings → Downloads; `0` keeps them forever).

- The first removals happen 7 days after the policy is switched on, so turning it on never deletes old files at once.
- Files tagged `keep`, and downloads still running, are never removed.
- Only files AnyGet saved and indexed are considered; nothing outside the downloads folder is touched.
- The Library keeps an entry for each removed file, with **Download again**.
- Preview a cleanup with `uv run anyget cleanup` (it lists, deletes nothing); `--apply` runs it.

## Common commands

```sh
make check     # lint + typecheck + tests
make e2e       # Playwright + axe
make gen       # regenerate the typed API client after API changes
make up / make down / make logs
```

## Use it from your phone

- **From anywhere:** Cloudflare Tunnel + Access with an email code: [docs/deploy.md](docs/deploy.md). Then `make up-public`.
- **No domain:** Tailscale: [docs/tailscale.md](docs/tailscale.md).
- **Android:** install the web app (Settings → Install AnyGet) to share links to it, or use Termux: [docs/termux.md](docs/termux.md).
- **Desktop browsers:** the extension in `apps/extension` (`make extension`; releases attach the zips).

## Backups

```sh
make backup                                   # backups/anyget-<date>.tar.gz (keep it private)
make down && make restore FILE=backups/anyget-<date>.tar.gz
```

A backup holds the database (jobs, library, watches, saved settings and keys), cookies.txt and the download archives. It does not hold the downloaded files themselves.

## Plugins

Extra sites can be added as Python packages: see [examples/anyget-plugin-example](examples/anyget-plugin-example). Enable them with `ANYGET_PLUGINS`.

## Docs

- `CLAUDE.md`: architecture, rules and roadmap (also read by Claude Code)
- `docs/setup.md`: install the tools
- `docs/hosted.md`: one hosting example (Railway + Vercel) with the owner sign-in: every variable, and safe checks after a deploy
- `docs/deploy.md`, `docs/tailscale.md`, `docs/termux.md`: reaching AnyGet from elsewhere
- `docs/dev/`: build history: the research tables (`plan.md`) and one prompt per build phase (`prompts/`)
- `CHANGELOG.md`: what changed in each version

## Status

The latest release is 1.0.0. Everything since (sign-in, Connections, universal search, Sections, the optional AI helper, the Reading Room UI, previews, the audio player and retention) is listed under **Unreleased** in `CHANGELOG.md` and goes into the next release.

## Contributing

Contributions are welcome: read [CONTRIBUTING.md](CONTRIBUTING.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md). Found a security problem? Please follow
[SECURITY.md](SECURITY.md) and report it privately.

## Support AnyGet

AnyGet is free and has no ads. If it saves you time, you can support its development:

<!-- TODO(owner): replace the placeholders below (and in .github/FUNDING.yml) before the repository is public. -->
- GitHub Sponsors: `<github-sponsors-username>`
- Buy Me a Coffee: `<bmc-username>`
- Ko-fi: `<kofi-username>`
- Other: `<optional crypto or other donation page URL>`

Starring the repository, reporting bugs and fixing a site that broke help just as much.

## License

AnyGet is released under the [MIT License](LICENSE). It uses many other open-source
projects; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for their licences.

## Disclaimer

- AnyGet is for personal use. Download only what you own, what is public domain or openly
  licensed, or what the site's terms allow.
- It does not and will not remove DRM, get around paywalls, logins, region blocks or
  lending limits, or use shadow libraries.
- You are responsible for what you download, and for following the law where you live and
  each site's terms.
- AnyGet is provided "as is", without warranty of any kind (see [LICENSE](LICENSE)). The
  authors are not affiliated with any site AnyGet can download from; all trademarks belong
  to their owners.
