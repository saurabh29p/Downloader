"""Library v2: full-text search (OCR sidecars, EPUB, HTML, PDF text) and filters."""

import shutil
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from pikepdf import Dictionary, Name, Pdf

from anyget.core.jobs import JobState
from anyget.core.services import Services
from anyget.core.settings import Settings
from anyget.library.fulltext import fts_query, text_of
from tests.test_phase8 import make_epub


@pytest.fixture
async def services(settings: Settings) -> AsyncIterator[Services]:
    svc = Services.build(settings)
    yield svc
    await svc.stop()


def test_text_of_each_kind(tmp_path: Path) -> None:
    (tmp_path / "scan.pdf").write_bytes(b"%PDF-1.4 not real")
    (tmp_path / "scan.txt").write_text("Shah Jahan ordered the tomb", encoding="utf-8")
    assert text_of(tmp_path / "scan.pdf") == "Shah Jahan ordered the tomb"  # OCR sidecar
    (tmp_path / "page.html").write_text(
        "<html><head><script>evil()</script></head><body><p>Mughal  gardens</p></body></html>"
    )
    assert text_of(tmp_path / "page.html") == "Mughal gardens"
    book = make_epub(tmp_path / "b.epub", ["गोदान की कहानी", "Second chapter"])
    assert "गोदान" in text_of(book) and "Second chapter" in text_of(book)
    (tmp_path / "x.bin").write_bytes(b"\x00\x01")
    assert text_of(tmp_path / "x.bin") == ""


def test_fts_query_is_always_safe() -> None:
    assert fts_query('taj "mahal') == '"taj" "mahal"*'
    assert fts_query("NEAR(a b) OR c*") == '"NEAR" "a" "b" "OR" "c"*'
    assert fts_query("  !!  ") == ""


async def test_full_text_search_finds_words_inside_files(services: Services) -> None:
    root = services.settings.downloads_dir
    root.mkdir(parents=True, exist_ok=True)
    (root / "Report (OCR).pdf").write_bytes(b"%PDF-1.4")
    (root / "Report (OCR).txt").write_text("The Apollo guidance computer was tested at night.")
    make_epub(root / "Godan.epub", ["होरी और धनिया गाँव में रहते थे"])
    (root / "unrelated.mp4").write_bytes(b"x" * 100)
    await services.library.scan()

    page = services.library.search(q="guidance")
    titles = sorted(i.title for i in page.items)
    assert titles == ["Report (OCR)", "Report (OCR)"]  # the PDF (sidecar) and the .txt itself
    assert all(i.snippet and "guidance" in i.snippet for i in page.items)
    hindi = services.library.search(q="धनिया")
    assert [i.title for i in hindi.items] == ["Godan"]
    assert services.library.search(q="unrel").items[0].snippet is None  # title match only
    assert services.library.search(q='apollo" *').total == 2  # odd input never errors
    assert services.library.search(q='apollo" OR (').total == 0  # every word must match

    epub = hindi.items[0]
    services.library.delete(epub.id)
    assert services.library.search(q="धनिया").total == 0


async def test_scan_indexes_files_saved_before_full_text(services: Services) -> None:
    root = services.settings.downloads_dir
    root.mkdir(parents=True, exist_ok=True)
    (root / "notes.txt").write_text("remember the archive etiquette")
    await services.library.scan()
    with services.db.engine.begin() as conn:
        conn.exec_driver_sql("DELETE FROM library_text")
    assert services.library.search(q="etiquette").total == 0
    await services.library.scan()
    assert services.library.search(q="etiquette").total == 1


async def test_section_source_and_licence_filters(services: Services) -> None:
    root = services.settings.downloads_dir
    root.mkdir(parents=True, exist_ok=True)
    (root / "gita.epub").write_bytes(b"PK fake")
    (root / "film.mp4").write_bytes(b"v" * 50)
    (root / "odd.pdf").write_bytes(b"%PDF")
    book = services.store.create(
        "https://archive.org/download/gita/gita.epub",
        {"section": "books", "licence": "public_domain"},
    )
    services.store.update(book.id, state=JobState.done, rel_path="gita.epub", title="Gita")
    film = services.store.create("https://www.youtube.com/watch?v=x")
    services.store.update(film.id, state=JobState.done, rel_path="film.mp4", title="Film")
    odd = services.store.create(
        "https://x.test/odd.pdf", {"section": "torrents", "licence": "free"}
    )
    services.store.update(odd.id, state=JobState.done, rel_path="odd.pdf", title="Odd")
    for job in (book, film, odd):
        await services.library.add_job(services.store.get(job.id))  # type: ignore[arg-type]

    everything = services.library.search()
    by_title = {i.title: i for i in everything.items}
    assert by_title["Gita"].section == "books" and by_title["Gita"].licence == "public_domain"
    assert by_title["Film"].section == "video" and by_title["Film"].source == "youtube.com"
    assert by_title["Odd"].licence == "unknown"  # unknown values are dropped
    assert by_title["Odd"].section == "books"  # a PDF, so Books
    assert everything.sources == ["archive.org", "x.test", "youtube.com"]
    assert everything.sections == ["books", "video"]
    assert everything.licences == ["public_domain", "unknown"]
    assert [i.title for i in services.library.search(section="video").items] == ["Film"]
    assert [i.title for i in services.library.search(source="archive.org").items] == ["Gita"]
    assert services.library.search(licence="public_domain").total == 1


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="needs poppler's pdftotext")
async def test_pdf_text_layer_is_searchable(services: Services) -> None:
    root = services.settings.downloads_dir
    root.mkdir(parents=True, exist_ok=True)
    pdf = Pdf.new()
    page = pdf.add_blank_page(page_size=(200, 200))
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)
    )
    page.Resources = Dictionary(Font=Dictionary(F1=font))
    page.Contents = pdf.make_stream(b"BT /F1 12 Tf 20 100 Td (Chronicling America) Tj ET")
    pdf.save(root / "paper.pdf")
    await services.library.scan()
    assert [i.title for i in services.library.search(q="chronicling").items] == ["paper"]
