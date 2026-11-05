# AnyGet

Paste any public link, get the file. A personal universal downloader that runs on your own computer.

- **Core:** FastAPI + SQLite job queue with live progress (SSE), a URL router that sends each link to the best handler (yt-dlp, archive.org, gallery-dl, git, IIIF libraries, plain HTTP …).
- **Website:** Next.js + Tailwind + shadcn/ui, English / Hindi / Arabic (RTL), installable as a phone app.
- **CLI:** `anyget` (Typer + Rich).
- **Access from anywhere:** Cloudflare Tunnel + Access (email login). Nothing is exposed on your router.

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
- `docs/deploy.md`, `docs/tailscale.md`, `docs/termux.md`: reaching AnyGet from elsewhere
- `docs/plan.md`: research tables: sources, endpoints, features
- `prompts/`: one prompt per build phase
- `CHANGELOG.md`: what changed in each version

## Status

Version 1.0.0. All ten build phases are done. See `CHANGELOG.md`.
