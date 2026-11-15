# Development setup

For running AnyGet you only need Docker: see [install.md](install.md). This page is for
working on AnyGet's code.

## Tools

| Tool | Version | Install |
|---|---|---|
| Git | any recent | https://git-scm.com/downloads |
| Node.js | 24 LTS | https://nodejs.org/ or `fnm install 24` |
| pnpm | 10 | `corepack enable && corepack prepare pnpm@10 --activate` |
| uv (+ Python 3.12) | latest | https://docs.astral.sh/uv/, then `uv python install 3.12` |
| FFmpeg | any recent | `winget install ffmpeg` / `brew install ffmpeg` / `sudo apt install ffmpeg` |
| Deno | 2.3 or newer | https://deno.com/ (yt-dlp needs it for full YouTube support) |
| poppler | any recent | `brew install poppler` / `sudo apt install poppler-utils` (PDF thumbnails and their tests) |
| Docker | latest | Optional: `make up`, the live tests and image builds |

On Windows, work inside WSL2 (Ubuntu) and keep the repository in the Linux file system
(`~/anyget`), not under `/mnt/c`.

Check the versions:

```sh
git --version
node --version     # v24.x
pnpm --version     # 10.x
uv --version && uv run --python 3.12 python --version
ffmpeg -version | head -1
deno --version
```

## Run it

```sh
make setup     # uv sync + pnpm install
make dev       # API on http://127.0.0.1:8000 (reload), website on http://127.0.0.1:3000
```

`.env` is optional; copy `.env.example` if you want to change settings.

## Checks and tests

```sh
make check     # lint + typecheck + unit tests (Python and web): run before every commit
make e2e       # Playwright end-to-end tests with axe accessibility checks
make live      # real downloads of public-domain / CC media in the Docker test image
make gen       # regenerate the typed API client after changing the API's shapes
make notices   # regenerate THIRD_PARTY_NOTICES.md after changing dependencies
make cli-docs  # regenerate docs/cli.md after changing the command line
```

`make e2e` starts its own fixture file server (:8200), API (:8100) and production website
(:3100). If Playwright's Chromium is missing, set `PW_CHROMIUM_PATH=/path/to/chrome`.
Lighthouse budgets: build the website, start it, then
`pnpm --filter @anyget/web lighthouse http://127.0.0.1:3000` (`CHROME_PATH` for the browser).

Tests mock every HTTP request (respx) and fake DNS, so `make check` needs no internet. Tests
that need the real internet are marked `live` and run only with `make live` or the manual
"Live tests" GitHub workflow.

## Working with an AI assistant

[`CLAUDE.md`](../CLAUDE.md) holds the project's rules and gotchas. Claude Code reads it
automatically; other assistants (and people) can read it too. The prompts used to build
AnyGet phase by phase are in [`docs/dev/prompts/`](dev/prompts/).

Read [CONTRIBUTING.md](../CONTRIBUTING.md) before opening a pull request.
