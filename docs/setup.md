# Phase 0: set up your computer

AnyGet runs on Windows (WSL2), macOS or Linux. Install these once.

| Tool | Version | Install |
|---|---|---|
| Docker Desktop | latest | https://docs.docker.com/desktop/ (Windows: enable the WSL2 backend) |
| Git | any recent | https://git-scm.com/downloads |
| Node.js | 24 LTS | https://nodejs.org/ or `fnm install 24` |
| pnpm | 10 | `corepack enable && corepack prepare pnpm@10 --activate` |
| uv (+ Python 3.12) | latest | https://docs.astral.sh/uv/ then `uv python install 3.12` |
| ffmpeg | any recent | `winget install ffmpeg` / `brew install ffmpeg` / `sudo apt install ffmpeg` |
| Deno | 2.9+ | https://deno.com/ (`curl -fsSL https://deno.land/install.sh \| sh`) |
| Claude Code | latest | https://code.claude.com/ |

On Windows, run everything inside WSL2 (Ubuntu) and keep the repo in the Linux filesystem (`~/anyget`), not under `/mnt/c`.

ffmpeg and Deno are only needed locally if you run the API outside Docker; the API image already includes them.

## Check versions

```sh
docker --version && docker compose version
git --version
node --version     # v24.x
pnpm --version     # 10.x
uv --version && uv run --python 3.12 python --version
ffmpeg -version | head -1
deno --version
claude --version
```

## Create the repo

1. Create a **private** GitHub repo and clone it.
2. Make sure `CLAUDE.md` is at the root and committed.
3. Copy `.env.example` to `.env` (never commit `.env`).
4. `make setup` installs all dependencies; `make check` should be green.

## Running each phase with Claude Code

1. Start `claude` in the repo and paste the matching `prompts/phase-NN-*.md`.
2. Read the summary, run `make check` (and `make e2e`), try the app, ask Claude to fix anything failing.
3. Commit with a clear message (for example `feat: phase 2 core and security`) and push.
4. Start the next phase in a fresh session (`/clear`). Repeat until phase 10.
