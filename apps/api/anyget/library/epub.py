"""Plain-text preview of an EPUB: the first chapters, read with the standard library.

Only parsing (no scripts, no network): container.xml → OPF spine → XHTML text.
XML goes through defusedxml; chapter HTML through HTMLParser.
"""

import posixpath
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, ClassVar, Literal

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
        _check_drm(book)
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


# ----- reader: table of contents and chapters as plain blocks ----------------------
# Chapters are sent as typed text blocks, never as HTML: no scripts, styles, forms or
# remote resources from the book can reach the page.

BlockKind = Literal["h1", "h2", "h3", "h4", "p", "li", "quote", "pre"]
MAX_BLOCKS = 4000


class EpubProtected(ValueError):  # noqa: N818 - a state the API reports as "protected"
    """DRM-encrypted EPUB (not font obfuscation): AnyGet can't and won't open it."""


class Chapter(BaseModel):
    index: int
    title: str | None


class EpubBook(BaseModel):
    title: str | None
    chapters: list[Chapter]


class Block(BaseModel):
    kind: BlockKind
    text: str


class EpubChapter(BaseModel):
    index: int
    title: str | None
    blocks: list[Block]
    truncated: bool = False


FONT_OBFUSCATION = ("http://www.idpf.org/2008/embedding", "http://ns.adobe.com/pdf/enc#RC")


def _check_drm(book: zipfile.ZipFile) -> None:
    if "META-INF/encryption.xml" not in book.namelist():
        return
    root = SafeET.fromstring(_read(book, "META-INF/encryption.xml"))
    for el in root.iter():
        if _local(el.tag) == "EncryptionMethod" and el.get("Algorithm") not in FONT_OBFUSCATION:
            raise EpubProtected("this EPUB is protected (DRM)")


def _package(book: zipfile.ZipFile) -> tuple[Any, str]:
    container = SafeET.fromstring(_read(book, "META-INF/container.xml"))
    opf_path = next(
        (el.get("full-path") for el in container.iter() if _local(el.tag) == "rootfile"), None
    )
    if not opf_path:
        raise ValueError("no package document in this EPUB")
    return SafeET.fromstring(_read(book, opf_path)), posixpath.dirname(opf_path)


def _spine(book: zipfile.ZipFile) -> tuple[str | None, list[str], dict[str, str]]:
    """(title, chapter file names in reading order, TOC labels by file name)."""
    opf, base = _package(book)
    names = set(book.namelist())
    title = next(
        (el.text.strip() for el in opf.iter() if _local(el.tag) == "title" and el.text), None
    )
    items = {
        el.get("id"): el
        for el in opf.iter()
        if _local(el.tag) == "item" and el.get("id") and el.get("href")
    }

    def path_of(href: str, rel_base: str = base) -> str:
        return posixpath.normpath(posixpath.join(rel_base, href.split("#")[0]))

    order = []
    for el in opf.iter():
        if _local(el.tag) == "itemref":
            item = items.get(el.get("idref"))
            if item is not None and path_of(item.get("href")) in names:
                order.append(path_of(item.get("href")))
    labels: dict[str, str] = {}
    nav = next((i for i in items.values() if "nav" in (i.get("properties") or "").split()), None)
    ncx = next(
        (i for i in items.values() if i.get("media-type") == "application/x-dtbncx+xml"), None
    )
    try:
        if nav is not None:
            nav_path = path_of(nav.get("href"))
            parser = _Links()
            parser.feed(_read(book, nav_path).decode("utf-8", errors="replace"))
            for href, label in parser.links:
                labels.setdefault(path_of(href, posixpath.dirname(nav_path)), label)
        elif ncx is not None:
            ncx_path = path_of(ncx.get("href"))
            root = SafeET.fromstring(_read(book, ncx_path))
            for point in root.iter():
                if _local(point.tag) != "navPoint":
                    continue
                text = next((t.text for t in point.iter() if _local(t.tag) == "text"), None)
                src = next((c.get("src") for c in point if _local(c.tag) == "content"), None)
                if text and src:
                    labels.setdefault(path_of(src, posixpath.dirname(ncx_path)), text.strip())
    except (KeyError, ValueError, SafeET.ParseError):
        pass  # a broken TOC: chapters are still listed by number
    return title, order, labels


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            label = " ".join("".join(self._text).split())
            if label:
                self.links.append((self._href, label))
            self._href = None

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)


class _Blocks(HTMLParser):
    KINDS: ClassVar[dict[str, BlockKind]] = {
        "h1": "h1",
        "h2": "h2",
        "h3": "h3",
        "h4": "h4",
        "h5": "h4",
        "h6": "h4",
        "p": "p",
        "li": "li",
        "blockquote": "quote",
        "pre": "pre",
        "div": "p",
        "section": "p",
        "td": "p",
        "dt": "p",
        "dd": "p",
        "figcaption": "p",
    }
    SKIP: ClassVar[set[str]] = {"script", "style", "head", "svg", "math", "nav", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self._kinds: list[BlockKind] = []
        self._buf: list[str] = []
        self._skip = 0

    def _flush(self) -> None:
        text = "".join(self._buf)
        kind = self._kinds[-1] if self._kinds else "p"
        text = text.strip("\n") if kind == "pre" else " ".join(text.split())
        if text and len(self.blocks) < MAX_BLOCKS:
            self.blocks.append(Block(kind=kind, text=text))
        self._buf = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self._skip += 1
        elif not self._skip and tag in self.KINDS:
            self._flush()
            self._kinds.append(self.KINDS[tag])
        elif not self._skip and tag == "br":
            self._buf.append("\n" if self._kinds and self._kinds[-1] == "pre" else " ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP:
            self._skip = max(0, self._skip - 1)
        elif not self._skip and tag in self.KINDS:
            self._flush()
            if self._kinds:
                self._kinds.pop()

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._buf.append(data)

    def close(self) -> None:
        super().close()
        self._flush()


def epub_book(path: Path) -> EpubBook:
    with zipfile.ZipFile(path) as book:
        _check_drm(book)
        title, order, labels = _spine(book)
    if not order:
        raise ValueError("this EPUB has no chapters")
    return EpubBook(
        title=title,
        chapters=[Chapter(index=i, title=labels.get(name)) for i, name in enumerate(order)],
    )


def epub_chapter(path: Path, index: int) -> EpubChapter:
    with zipfile.ZipFile(path) as book:
        _check_drm(book)
        _, order, labels = _spine(book)
        if not 0 <= index < len(order):
            raise KeyError(index)
        parser = _Blocks()
        parser.feed(_read(book, order[index]).decode("utf-8", errors="replace"))
        parser.close()
    return EpubChapter(
        index=index,
        title=labels.get(order[index]),
        blocks=parser.blocks,
        truncated=len(parser.blocks) >= MAX_BLOCKS,
    )
