# Phase 0 — Prerequisites

Do this yourself on your computer (no Claude Code needed). Full guide: `docs/setup.md`.

1. Install Docker Desktop (WSL2 backend on Windows), Git, Node 24 LTS + pnpm 10 (`corepack enable`), uv (it installs Python 3.12), ffmpeg, Deno 2.9+, and Claude Code.
2. Create a private GitHub repo and clone it.
3. Copy `CLAUDE.md` into the repo root and commit it: `docs: add CLAUDE.md`.

**Acceptance check:** every command in the "Check versions" block of `docs/setup.md` prints a version; `CLAUDE.md` is committed.
