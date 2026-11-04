# Phase 5 — archive.org and Wayback

Read `CLAUDE.md` (etiquette) and the archive.org table in `docs/plan.md` first.

Deliverables:
- `handlers/archive_org.py`: advancedsearch (filters: mediatype, collection, year, language, creator), scrape API for deep paging, metadata, file download with Range resume and md5 verify, "all of format X" (Original, VBR MP3, PDF, EPUB, DjVu), collections. Use `ia` as a subprocess where it helps (AGPL). Skip restricted, lending and stream-only items with a clear reason. Max 2 parallel per host, contact User-Agent, metadata cache.
- `handlers/wayback.py`: CDX list (`collapse=digest`) → snapshot timeline; raw download via `<timestamp>id_/<url>`.
- API endpoints for search, item, CDX.
- Web: archive.org page (search, filters, result cards, item page with file table + checkboxes), Wayback page (timeline, raw download).
- Offline fixtures for metadata, search and CDX responses.

**Acceptance check:** PDF from a Gutenberg item on archive.org downloads and md5 matches; a 2005 snapshot downloads raw.
Commit: `feat: phase 5 archive.org and wayback`.
