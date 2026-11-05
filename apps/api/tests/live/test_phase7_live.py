"""Live tests for books, worldwide libraries and OCR (real network, public domain only).

- Best legal copy of "Pride and Prejudice" (1813): an EPUB from Standard Ebooks or
  Project Gutenberg should come first.
- Books from 4 regions: Project Gutenberg (global), Gallica (Europe), NDL Japan (Asia),
  Library of Congress (Americas). The first library hit with page images is
  probed and its first two pages are saved. ANYGET_LIVE_QDL_ITEM adds a Qatar
  Digital Library item (Middle East) when set.
- OCR (needs OCRmyPDF + Tesseract, present in the Docker test image): render a
  line of text, merge it into a PDF, OCR it, and find the words in the text layer.
"""

import os
import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from anyget.books.base import BookHit
from anyget.books.search import search_books
from anyget.convert.ocr import available, ocr_pdf
from anyget.convert.pdf import images_to_pdf
from anyget.core.net import Net
from anyget.core.settings import Settings
from anyget.handlers.base import JobContext
from anyget.handlers.iiif_library import IiifLibraryHandler

pytestmark = [pytest.mark.live]


async def test_best_copy_of_a_classic(settings: Settings) -> None:
    net = Net(settings)
    result = await search_books(net, settings, "Pride and Prejudice Jane Austen", limit=5)
    await net.aclose()
    assert result.best is not None, [s.model_dump() for s in result.sources]
    assert result.best.source in ("standard_ebooks", "gutendex"), result.best
    assert result.best.formats[0].kind == "epub"


async def _two_pages(settings: Settings, hit: BookHit, job_id: str) -> list[Path]:
    net = Net(settings)
    handler = IiifLibraryHandler(net, settings)
    url = hit.formats[0].url
    probe = await handler.probe(url)
    assert probe.extra["count"] >= 1
    first_two = [c.id for c in probe.choices[:2]]
    job = JobContext(id=job_id, url=url, output_dir=settings.downloads_dir / job_id)
    result = await handler.download(job, {"files": first_two}, lambda _p: None)
    await net.aclose()
    for path in result.paths:
        head = path.read_bytes()[:4]
        assert head.startswith(b"\xff\xd8") or head == b"\x89PNG", path
    return result.paths


@pytest.mark.parametrize(
    ("source", "query"),
    [
        ("gallica", "Hugo Les misérables"),
        ("ndl", "源氏物語"),
        ("loc", "Alice's adventures in wonderland"),
    ],
)
async def test_library_pages_by_region(settings: Settings, source: str, query: str) -> None:
    net = Net(settings)
    result = await search_books(
        net, settings, query, kind="libraries", sources=[source], limit=10, time_limit=45
    )
    await net.aclose()
    status = result.sources[0]
    assert status.status == "ok", status
    with_pages = [h for h in result.results if h.downloadable and h.formats[0].kind == "images"]
    seen = [(h.access.value, h.details_url) for h in result.results[:5]]
    assert with_pages, f"{source}: no open item with page images for {query!r}; got {seen}"
    errors = []
    for hit in with_pages[:3]:  # an item may still be closed online; try the next one
        try:
            assert len(await _two_pages(settings, hit, f"live-{source}")) >= 1
            return
        except Exception as exc:  # any failure: try the next item, report all
            errors.append(f"{hit.details_url}: {exc}")
    pytest.fail("; ".join(errors))


async def test_gutenberg_epub_downloads(settings: Settings) -> None:
    from anyget.handlers.archive_org import ArchiveOrgHandler
    from anyget.handlers.books import BooksHandler

    net = Net(settings)
    handler = BooksHandler(net, settings, ArchiveOrgHandler(net))
    url = "https://www.gutenberg.org/ebooks/1342"
    job = JobContext(id="live-gb", url=url, output_dir=settings.downloads_dir)
    result = await handler.download(job, {"files": ["epub"]}, lambda _p: None)
    await net.aclose()
    assert result.paths[0].suffix == ".epub"
    assert result.paths[0].read_bytes()[:2] == b"PK"


async def test_qatar_digital_library_item(settings: Settings) -> None:
    item = os.environ.get("ANYGET_LIVE_QDL_ITEM")
    if not item:
        pytest.skip("set ANYGET_LIVE_QDL_ITEM to a Qatar Digital Library archive item URL")
    hit = BookHit.model_validate(
        {
            "source": "qdl",
            "id": item,
            "title": "QDL item",
            "access": "full_view",
            "formats": [{"kind": "images", "url": item}],
            "details_url": item,
        }
    )
    assert await _two_pages(settings, hit, "live-qdl")


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size=size)


async def test_ocr_makes_a_searchable_pdf(settings: Settings, tmp_path: Path) -> None:
    if not available():
        if shutil.which("ocrmypdf") is None and not os.environ.get("ANYGET_REQUIRE_OCR"):
            pytest.skip("OCRmyPDF/Tesseract not installed (the Docker test image has them)")
        pytest.fail("OCR tools expected but missing")
    page = Image.new("RGB", (1700, 600), "white")
    ImageDraw.Draw(page).text((80, 220), "PUBLIC DOMAIN LIBRARY", fill="black", font=_font(110))
    image = tmp_path / "page.png"
    page.save(image, dpi=(300, 300))
    scanned = images_to_pdf([image], tmp_path / "scan.pdf")
    searchable = await ocr_pdf(scanned, tmp_path / "scan (OCR).pdf", "eng")
    assert searchable.read_bytes().startswith(b"%PDF")
    text = searchable.with_suffix(".txt").read_text(encoding="utf-8").upper()
    assert "PUBLIC" in text and "LIBRARY" in text, text
