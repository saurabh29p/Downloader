# Contributing to AnyGet

Thank you for helping. AnyGet is free, open-source software (MIT); by contributing you
agree that your contribution is licensed under the same [MIT License](LICENSE).

Please read the [Code of Conduct](CODE_OF_CONDUCT.md). For security problems, follow
[SECURITY.md](SECURITY.md) instead of opening an issue.

## The rules that matter most

AnyGet only downloads what people are allowed to download. **Pull requests that add any of
these are closed:**

- removing or working around DRM (paid streaming, music services, paid ebooks);
- shadow libraries (LibGen, Z-Library, Anna's Archive and similar) or piracy, torrent or
  mirror sources in search;
- getting around region blocks, paywalls, logins, members-only content or lending limits;
- anything that sends a user's cookies, keys, passwords or file contents to someone else
  (including the optional AI helper).

Also: no ads, no tracking, nothing that phones home. Downloads always run on the user's own
machine.

[`CLAUDE.md`](CLAUDE.md) is the full rulebook: architecture, security, legal and frontend
rules, and the gotchas we learned the hard way. It is written for AI coding assistants
(Claude Code reads it automatically), and it works just as well for people.

## Set up

You need Git, Node 24 with pnpm 10, Python 3.12 with [uv](https://docs.astral.sh/uv/),
and FFmpeg. Deno (2.3 or newer) is needed for full YouTube support, and poppler for the
PDF thumbnail tests. Docker is optional (it is the easiest way to run AnyGet, but not
needed for development). `docs/setup.md` has install steps per OS.

```sh
make setup   # install everything (uv sync + pnpm install)
make dev     # API on http://127.0.0.1:8000, website on http://127.0.0.1:3000
```

## Before you open a pull request

```sh
make check   # lint + typecheck + tests (Python and web); must be green
make e2e     # Playwright + axe, whenever apps/web changes
```

If Playwright's Chromium is missing, set `PW_CHROMIUM_PATH=/path/to/chrome`.

- Write tests for what you change. Every HTTP request in tests is mocked with
  [respx](https://lundberg.github.io/respx/); offline fixtures live in
  `apps/api/tests/fixtures/`. Tests that need the real internet are marked
  `@pytest.mark.live` and are skipped by default.
- After changing the API's request or response shapes, run `make gen` to regenerate the
  typed client in `packages/shared`.
- User-facing text goes into `apps/web/messages/en.json`, `hi.json` and `ar.json` (all
  three; use logical CSS like `ms-`/`pe-`, never left/right, so Arabic works).
- Keep the performance budgets: first-load JS under 170 KB on every page
  (`e2e/budget.spec.ts`), Lighthouse 90+ and accessibility 100.
- Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`,
  `docs:`, `chore:`…) and add a line to `CHANGELOG.md` under **Unreleased**.

## Add a site

Every site lives in one handler file in `apps/api/anyget/handlers/` that implements
`anyget.handlers.base.Handler`:

- `name`: a short id;
- `can_handle(url)`: cheap, no network if possible;
- `probe(url)`: title, size, thumbnail and the choices (formats, files, items);
- `download(job, options, progress_cb)`: does the work and returns the saved paths.

Then register it with a priority in `anyget/core/services.py` (see the routing order in
`CLAUDE.md` and the priorities in `handlers/registry.py`), and add tests with respx
fixtures (look at `tests/test_http_generic.py` or `tests/test_archive_org.py`).

All outgoing HTTP must go through `anyget.core.net.Net` (it blocks private addresses on
every redirect), and every file name must go through `anyget.core.filenames`. If yt-dlp or
gallery-dl already support the site, a new handler is usually not needed.

Not everything belongs in AnyGet itself: a [plugin](examples/anyget-plugin-example) can add
a handler from its own package.

## Reporting a site that stopped working

Most "site stopped working" problems are fixed by updating yt-dlp (sites change often).
Please try that first; the issue template explains how.
