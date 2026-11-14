# Phase 2 — Core and security (download engine)

Read `CLAUDE.md` (handler contract, routing order, security rules) first.

Deliverables:
- `core/net.py`: SSRF guard — http/https only; resolve DNS; block private, loopback, link-local, CGNAT, multicast, metadata IPs (IPv4 + IPv6) on the first request and every redirect. Shared httpx client with a clear User-Agent, per-host rate limiting and 429/503 backoff.
- `core/filenames.py`: NFC normalize, keep original scripts, strip OS-illegal chars and reserved names, 180-byte limit, ID fallback; `safe_join(root, *parts)` that refuses anything outside the downloads root.
- `core/db.py`, `core/jobs.py`: SQLModel jobs table (url, handler, state, progress, bytes, total, path, error, options, timestamps). States: queued, probing, downloading, paused, done, failed.
- `core/queue.py`: asyncio worker pool, global limit (default 3) and per-host limits (archive.org 2); pause/resume/retry/cancel.
- `core/events.py`: in-process pub/sub; `GET /api/jobs/{id}/events` and `GET /api/events` as SSE.
- `core/router.py`: normalize (trim, expand short links via guarded HEAD, strip tracking params) + the 10-step routing order using the handler registry.
- `handlers/registry.py`, `handlers/http_generic.py`: Range resume into `.part` files, Content-Disposition filenames, md5/sha1 verify when given.
- API: `POST /api/probe`, `POST /api/jobs` (single or batch list), `GET /api/jobs`, `GET /api/jobs/{id}`, `POST /api/jobs/{id}/{pause|resume|retry|cancel}`, `DELETE /api/jobs/{id}`.
- CLI: `anyget get <url>... [-i list.txt]` with Rich progress bars, `anyget jobs`, `anyget probe <url>`.
- Tests (pytest + respx): SSRF (private IPs, DNS rebinding to private, redirect to metadata IP, non-http schemes), traversal (`../`, absolute paths, Windows reserved names), resume after interrupted download, routing order, queue concurrency.
- Run `make gen` so `packages/shared` has the new endpoints.

**Acceptance check:** an interrupted download resumes; SSRF and traversal tests pass; `make check` green.
Commit: `feat: phase 2 core and security`.
