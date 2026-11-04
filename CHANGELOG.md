# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Phase 0: `CLAUDE.md` project memory, `docs/plan.md`, `docs/setup.md`, phase prompts 0–10.
- Phase 1: monorepo skeleton — pnpm + Turborepo workspace, FastAPI `anyget` package with `/api/health` and `/api/version`, handler contract, Typer CLI, Next.js 16 web app (Tailwind 4 tokens, shadcn/ui, next-intl en/hi/ar with RTL, TanStack Query), `@anyget/shared` typed client generated from OpenAPI, Dockerfiles, Docker Compose with healthchecks on 127.0.0.1, Cloudflare Tunnel compose stub, Makefile, pre-commit, GitHub Actions CI.
- Phase 2: download engine — SSRF guard (DNS + redirect checks and a connect-time IP check that defeats DNS rebinding), safe Unicode filenames and path containment, SQLite job store, asyncio queue with global and per-host limits, pause/resume/retry/cancel, SSE events, URL normalizer with tracking-param stripping and short-link expansion, handler registry, generic HTTP handler with Range resume and md5/sha1 checks, REST API (`/api/probe`, `/api/jobs…`, `/api/events`), CLI `get`/`probe`/`jobs`.
- Phase 3: website foundation — app shell (header nav, phone bottom nav, theme and language menus, Ctrl/⌘+K quick menu), Home paste box (one or many links, clipboard, .txt drop/open) with source detection and preview drawer, recent downloads, Downloads page with live SSE progress, filters, pause/resume/retry/cancel/remove and "Save file", toasts, loading/empty/error states, dark mode, en/hi/ar with RTL. Playwright paste-to-done, batch, pause/resume, keyboard-only and axe tests; Lighthouse script; first-load JS budget test.

### Fixed
- SSE stream cleanup raised errors when a browser disconnected.
- Live progress could be dropped by the browser after a page refresh (stale timestamps); job times are now always sent as UTC.
- API container could not create its database when Docker created the `data` folder as root (CI Docker job). The container now adopts `PUID`/`PGID` and fixes folder ownership before dropping privileges.
