"""Full-text search over the library: OCR sidecars, text files, HTML, EPUB and PDF text.

Text lives in an SQLite FTS5 table next to `library_item` (`library_text`, one row
per item; an empty body means "checked, no text"). Only local files are read:
no network, no scripts. PDFs use `pdftotext` (poppler) when it is installed.
"""

import contextlib
import logging
import re
import shutil
import subprocess
import zipfile
from html.parser import HTMLParser
from pathlib import Path

from sqlalchemy import Engine

from anyget.library.epub import epub_preview

log = logging.getLogger("anyget.library")

MAX_CHARS = 1_000_000
MAX_READ = 4 * 1024 * 1024
PDF_PAGES = 300
PLAIN = {".txt", ".md", ".srt", ".vtt", ".csv", ".json", ".xml"}
HTML = {".html", ".htm"}


class _Html(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "head"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "head") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def _read_text(path: Path) -> str:
    with path.open("rb") as fh:
        return fh.read(MAX_READ).decode("utf-8", errors="replace")


def _pdf_text(path: Path) -> str:
    tool = shutil.which("pdftotext")
    if tool is None:
        return ""
    try:
        done = subprocess.run(  # noqa: S603 - fixed tool, local file, no shell
            [tool, "-q", "-l", str(PDF_PAGES), "-enc", "UTF-8", str(path), "-"],
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return done.stdout.decode("utf-8", errors="replace")


def text_of(path: Path) -> str:
    """The searchable text of a file ('' if it has none)."""
    suffix = path.suffix.lower()
    try:
        sidecar = path.with_suffix(".txt")
        if suffix != ".txt" and sidecar.is_file():  # OCRmyPDF's text, next to the PDF
            text = _read_text(sidecar)
        elif suffix in PLAIN:
            text = _read_text(path)
        elif suffix in HTML:
            parser = _Html()
            parser.feed(_read_text(path))
            text = " ".join(parser.parts)
        elif suffix == ".epub":
            text = epub_preview(path, max_chars=MAX_CHARS).text
        elif suffix == ".pdf":
            text = _pdf_text(path)
        else:
            return ""
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        log.info("no text for %s: %s", path.name, type(exc).__name__)
        return ""
    return re.sub(r"\s+", " ", text).strip()[:MAX_CHARS]


def fts_query(q: str) -> str:
    """Words as quoted FTS5 terms (all must match; the last one as a prefix)."""
    words = re.findall(r"\w+", q, flags=re.UNICODE)[:12]
    if not words:
        return ""
    terms = [f'"{w}"' for w in words]
    terms[-1] += "*"
    return " ".join(terms)


class FullText:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.enabled = True
        try:
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS library_text USING fts5("
                    "item_id UNINDEXED, body, tokenize='unicode61 remove_diacritics 2')"
                )
        except Exception:
            log.warning("SQLite has no FTS5: library full-text search is off")
            self.enabled = False

    def put(self, item_id: str, path: Path) -> None:
        if not self.enabled:
            return
        body = text_of(path)
        with self.engine.begin() as conn:
            conn.exec_driver_sql("DELETE FROM library_text WHERE item_id = ?", (item_id,))
            conn.exec_driver_sql(
                "INSERT INTO library_text (item_id, body) VALUES (?, ?)", (item_id, body)
            )

    def drop(self, item_id: str) -> None:
        if self.enabled:
            with self.engine.begin() as conn:
                conn.exec_driver_sql("DELETE FROM library_text WHERE item_id = ?", (item_id,))

    def known(self) -> set[str]:
        if not self.enabled:
            return set()
        with self.engine.begin() as conn:
            return {row[0] for row in conn.exec_driver_sql("SELECT item_id FROM library_text")}

    def search(self, q: str, limit: int = 500) -> dict[str, str]:
        """item id → a short snippet around the match."""
        query = fts_query(q)
        if not self.enabled or not query:
            return {}
        with contextlib.suppress(Exception), self.engine.begin() as conn:
            rows = conn.exec_driver_sql(
                "SELECT item_id, snippet(library_text, 1, '', '', '…', 16) FROM library_text "
                "WHERE library_text MATCH ? ORDER BY rank LIMIT ?",
                (query, limit),
            )
            return {row[0]: row[1] for row in rows}
        return {}
