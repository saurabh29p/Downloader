"""Plain-text preview of an EPUB: the first chapters, read with the standard library.

Only parsing (no scripts, no network): container.xml → OPF spine → XHTML text.
XML goes through defusedxml; chapter HTML through HTMLParser.
"""

import posixpath
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import ClassVar

import defusedxml.ElementTree as SafeET
from pydantic import BaseModel

MAX_CHARS = 20_000
MAX_MEMBER = 5 * 1024 * 1024


class EpubPreview(BaseModel):
    title: str | None
    text: str
    truncated: bool


class _Text(HTMLParser):
    BLOCK: ClassVar[set[str]] = {"p", "div", "br", "h1", "h2", "h3", "h4", "li", "tr", "section"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "head"):
            self._skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "head") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _read(book: zipfile.ZipFile, name: str) -> bytes:
    info = book.getinfo(name)
    if info.file_size > MAX_MEMBER:
        raise ValueError(f"{name} is too large to preview")
    return book.read(info)


def epub_preview(path: Path, max_chars: int = MAX_CHARS) -> EpubPreview:
    with zipfile.ZipFile(path) as book:
        container = SafeET.fromstring(_read(book, "META-INF/container.xml"))
        opf_path = next(
            (el.get("full-path") for el in container.iter() if _local(el.tag) == "rootfile"), None
        )
        if not opf_path:
            raise ValueError("no package document in this EPUB")
        opf = SafeET.fromstring(_read(book, opf_path))
        base = posixpath.dirname(opf_path)
        title = next(
            (el.text.strip() for el in opf.iter() if _local(el.tag) == "title" and el.text), None
        )
        manifest = {
            el.get("id"): el.get("href")
            for el in opf.iter()
            if _local(el.tag) == "item" and el.get("id") and el.get("href")
        }
        spine = [el.get("idref") for el in opf.iter() if _local(el.tag) == "itemref"]
        text = ""
        for idref in spine:
            href = manifest.get(idref)
            if not href:
                continue
            name = posixpath.normpath(posixpath.join(base, href.split("#")[0]))
            if name not in book.namelist():
                continue
            parser = _Text()
            parser.feed(_read(book, name).decode("utf-8", errors="replace"))
            chunk = "\n".join(line.strip() for line in "".join(parser.parts).splitlines())
            text += "\n\n" + "\n".join(line for line in chunk.split("\n") if line)
            if len(text) > max_chars:
                break
    text = text.strip()
    return EpubPreview(title=title, text=text[:max_chars], truncated=len(text) > max_chars)
