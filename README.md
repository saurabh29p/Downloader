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

## Docs

- `CLAUDE.md` — architecture, rules and roadmap (also read by Claude Code)
- `docs/setup.md` — install the tools (phase 0)
- `docs/plan.md` — research tables: sources, endpoints, features
- `prompts/` — one prompt per build phase

## Status

Phase 4 (YouTube and media) is in review. Direct file links and video/audio sites work from the website and the CLI.
