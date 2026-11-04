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

Phase 3 done: paste direct file links on the website (or use `uv run anyget get <link>`), watch live progress, pause/resume, and save the file. YouTube and media arrive in phase 4.
