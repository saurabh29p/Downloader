# v3 Phase 2 — Licences, plans and the free engine updater

Read `CLAUDE.md` (security, commercial rules) and section 6 of `docs/business-plan.md` first.

Deliverables:
- `anyget/licensing/`: Ed25519-signed licence keys checked **offline** (public key in the app, private key never in the repo); payload = plan (`plus`, `lifetime`, `pro`), email hash, issued/expiry dates, device limit. `Entitlements` derived from the plan; no key → Free. Store the key in `data/` (0600), never log it.
- Enforce Free limits only through `Entitlements`, at the places that already decide them: quality choices in `handlers/ytdlp_support/formats.py` (≤1080p), parallel downloads via `DownloadQueue.reconfigure` (2 vs 5), playlist/channel expansion (≤25 items, rest listed as "Plus"), watch creation in `watch/`, batch import, and the `convert` handler (MP3 stays free; other conversions and OCR need Plus). CLI and plugins check the Pro flag.
- API: `GET /api/licence` (plan, limits, expiry), `POST /api/licence` (activate), `DELETE /api/licence`. Errors use a `plan_limit` code with the plan that unlocks it; run `make gen`.
- Web: a "Licence" group in Settings and one calm upgrade card wherever a limit is hit (no pop-ups, no nagging). Translate in en/hi/ar.
- Engine updater (free on every plan): checks PyPI for a newer yt-dlp (and yt-dlp-ejs) daily, verifies the hash, installs into `data/engine/`, loads it on the next job; one-click roll back. Re-run `tests/test_net_guard.py` against the updated engine before switching to it.
- Tests for key parsing, tampered keys, expiry, each limit, and the updater (mocked PyPI).

**Acceptance check:** with no key a 60-item playlist queues 25 items and shows the Plus card; a valid Plus key queues all 60; a tampered key is refused; a newer yt-dlp is picked up without an app release.
Commit: `feat: licences, plans and engine updater`.
