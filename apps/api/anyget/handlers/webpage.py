"""Web pages: save the page itself, or pick documents and media linked from it.

This is the HTML branch of the generic fallback (routing step 10): when a link
returns HTML, HttpGenericHandler hands it here instead of refusing it.
"""

from html.parser import HTMLParser
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urljoin, urlsplit

from anyget.core.filenames import safe_join, sanitize_filename, unique_path
from anyget.core.net import Net
from anyget.handlers.base import (
    Choice,
    DownloadResult,
    HandlerError,
    JobRef,
    Probe,
    ProgressCallback,
)
from anyget.handlers.multi import RemoteFile, download_many

if TYPE_CHECKING:
    from anyget.handlers.http_generic import HttpGenericHandler

MAX_PAGE_BYTES = 5 * 1024 * 1024
MAX_LINKS = 500
PAGE_ID = "page"
LINK_KINDS = {
    "document": {
        "pdf",
        "epub",
        "djvu",
        "doc",
        "docx",
        "odt",
        "rtf",
        "txt",
        "csv",
        "xls",
        "xlsx",
        "ods",
        "ppt",
        "pptx",
        "odp",
        "md",
        "json",
        "xml",
    },
    "image": {"jpg", "jpeg", "png", "gif", "webp", "svg", "avif", "tif", "tiff", "bmp"},
    "audio": {"mp3", "m4a", "ogg", "oga", "opus", "flac", "wav", "aac"},
    "video": {"mp4", "webm", "mkv", "mov", "avi", "m4v", "ogv"},
    "archive": {"zip", "7z", "rar", "tar", "gz", "tgz", "bz2", "xz", "iso"},
}
_EXT_KIND = {ext: kind for kind, exts in LINK_KINDS.items() for ext in exts}


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.title = ""
        self._in_title = False
        self.base: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "base" and values.get("href"):
            self.base = values["href"]
        for attr in ("href", "src", "data", "poster"):
            value = values.get(attr)
            if value and tag in (
                "a",
                "img",
                "source",
                "video",
                "audio",
                "embed",
                "object",
                "link",
                "track",
            ):
                self.links.append(value)
        srcset = values.get("srcset")
        if srcset and tag in ("img", "source"):
            self.links.extend(
                part.strip().split(" ")[0] for part in srcset.split(",") if part.strip()
            )

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


def extract_links(html: str, page_url: str) -> tuple[str, list[dict[str, str]]]:
    """→ (page title, [{url, name, kind}]) for links to files we know how to save."""
    parser = _LinkParser()
    parser.feed(html)
    base = urljoin(page_url, parser.base) if parser.base else page_url
    seen: set[str] = set()
    links: list[dict[str, str]] = []
    for raw in parser.links:
        absolute = urljoin(base, raw.strip())
        parts = urlsplit(absolute)
        if parts.scheme not in ("http", "https"):
            continue
        absolute = parts._replace(fragment="").geturl()
        name = PurePosixPath(unquote(parts.path)).name
        ext = name.rpartition(".")[2].lower() if "." in name else ""
        kind = _EXT_KIND.get(ext)
        if not kind or absolute in seen:
            continue
        seen.add(absolute)
        links.append({"url": absolute, "name": name, "kind": kind})
        if len(links) >= MAX_LINKS:
            break
    return " ".join(parser.title.split()), links


async def fetch_page(net: Net, url: str) -> tuple[str, str]:
    """Page HTML (capped at 5 MB) and its final URL."""
    async with net.stream("GET", url) as response:
        if response.status_code >= 400:
            raise HandlerError("upstream", f"the page answered {response.status_code}")
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > MAX_PAGE_BYTES:
                break
            chunks.append(chunk)
        charset = response.charset_encoding or "utf-8"
        return b"".join(chunks).decode(charset, errors="replace"), str(response.url)


async def probe_page(net: Net, url: str) -> Probe:
    html, final = await fetch_page(net, url)
    title, links = extract_links(html, final)
    host = urlsplit(final).hostname or "page"
    title = title or host
    return Probe(
        url=url,
        handler="http",
        title=title,
        choices=[
            Choice(
                id=PAGE_ID,
                label=f"{sanitize_filename(title, fallback=host)}.html",
                kind="page",
                default=True,
            ),
            *(Choice(id=link["url"], label=link["name"], kind=link["kind"]) for link in links),
        ],
        extra={
            "kind": "webpage",
            "filename": f"{sanitize_filename(title, fallback=host)}.html",
            "content_type": "text/html",
            "final_url": final,
            "links": links,
            "resumable": False,
            "checksums": {},
        },
    )


async def download_page(
    http: "HttpGenericHandler",
    job: JobRef,
    options: dict[str, Any],
    probe: Probe,
    progress_cb: ProgressCallback,
) -> DownloadResult:
    wanted = options.get("files")
    ids = [str(w) for w in wanted] if isinstance(wanted, list) and wanted else [PAGE_ID]
    links = {link["url"]: link for link in probe.extra.get("links", [])}
    unknown = [i for i in ids if i != PAGE_ID and i not in links]
    if unknown:
        raise HandlerError("not_found", "some chosen links are not on this page")
    paths = []
    title = probe.title
    if PAGE_ID in ids:
        html, _ = await fetch_page(http.net, job.url)
        target = unique_path(safe_join(job.output_dir, str(probe.extra["filename"])))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        paths.append(target)
    chosen = [links[i] for i in ids if i != PAGE_ID]
    if chosen:
        folder = safe_join(job.output_dir, sanitize_filename(title))
        folder.mkdir(parents=True, exist_ok=True)
        files = [
            RemoteFile(url=link["url"], name=link["name"], headers={"Referer": job.url})
            for link in chosen
        ]
        result = await download_many(http, job, files, folder, progress_cb)
        paths.extend(result.paths)
    return DownloadResult(paths=paths)
