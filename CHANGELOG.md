# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Phase 0: `CLAUDE.md` project memory, `docs/plan.md`, `docs/setup.md`, phase prompts 0–10.
- Phase 1: monorepo skeleton — pnpm + Turborepo workspace, FastAPI `anyget` package with `/api/health` and `/api/version`, handler contract, Typer CLI, Next.js 16 web app (Tailwind 4 tokens, shadcn/ui, next-intl en/hi/ar with RTL, TanStack Query), `@anyget/shared` typed client generated from OpenAPI, Dockerfiles, Docker Compose with healthchecks on 127.0.0.1, Cloudflare Tunnel compose stub, Makefile, pre-commit, GitHub Actions CI.
