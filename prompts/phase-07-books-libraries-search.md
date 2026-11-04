# Phase 7 — Books, worldwide libraries, universal search, OCR, conversion

Read `CLAUDE.md` (legal rules) and the books + regions tables in `docs/plan.md` first.

Deliverables:
- `anyget/books/`: one adapter per source (Internet Archive, Open Library, Gutenberg/Gutendex, Standard Ebooks OPDS, Wikisource, HathiTrust, Google Books free-ebooks, LoC, DPLA, Europeana, Gallica, NDL, NDLI, BHL, Wayback) + a ranker: full-view first, then EPUB → text PDF → scanned PDF → page images, then quality/completeness. `handlers/books.py` ties them together. In-copyright books show "not legally downloadable" with library/buy links. No shadow libraries, ever.
- `handlers/iiif_library.py`: detect IIIF Presentation v2/v3 manifests; download every page at full size; optional merge to PDF (img2pdf). `anyget/libraries/` holds the region registry.
- Universal search endpoint + Search page with tabs by type (archive.org, books, YouTube, libraries).
- `anyget/convert/`: ffmpeg conversions, images → PDF, EPUB → PDF via Calibre if installed, OCR via OCRmyPDF/Tesseract (many languages) when installed.
- API keys (Europeana, DPLA, Trove, DigitalNZ, BHL, DDB) stored in settings, masked.
- Web: Books page (best copy card on top), Libraries page by region.

**Acceptance check:** best legal copy found for a classic title; books from 4 regions download; OCR produces a searchable PDF.
Commit: `feat: phase 7 books, libraries and search`.
