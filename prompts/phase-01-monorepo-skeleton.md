# Phase 1 — Monorepo skeleton

Read `CLAUDE.md` first. Build the base and tooling only; no download logic.

Deliverables:
- Root: pnpm workspace + Turborepo, `Makefile` (setup, dev, gen, lint, typecheck, test, check, e2e, up, down, logs, up-public), `.env.example`, `.editorconfig`, `.gitignore`, pre-commit hooks.
- `apps/api`: uv project, package `anyget`, FastAPI `create_app()` with `GET /api/health` and `GET /api/version`, pydantic-settings, handler Protocol in `handlers/base.py`, Typer CLI (`anyget version`, `anyget health`), ruff + mypy strict + pytest.
- `apps/web`: Next.js 16 App Router, TypeScript strict, Tailwind 4 tokens, shadcn/ui, next-intl (en, hi, ar with RTL), TanStack Query, Home placeholder showing API status, `/api/*` rewrite to the API, Vitest + Playwright + axe.
- `packages/shared`: types generated from the API OpenAPI schema with openapi-typescript + an openapi-fetch client.
- Dockerfiles (api: python:3.12-slim + ffmpeg + git + Deno; web: Node 24 standalone), `docker-compose.yml` with healthchecks and `127.0.0.1` ports, `docker-compose.tunnel.yml` stub.
- GitHub Actions CI: lint, typecheck, tests, build, codegen check, Playwright, Docker build.

**Acceptance check:** `make check` and `make e2e` green; `docker compose up` shows both containers healthy.
Commit: `feat: phase 1 monorepo skeleton`.
