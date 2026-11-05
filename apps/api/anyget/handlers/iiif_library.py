"""IIIF libraries: any Presentation v2/v3 manifest, plus item pages of known libraries.

Gallica, Library of Congress, NDL Japan, Europeana and the Qatar Digital Library
item links are turned into their manifest URLs; any URL ending in a manifest
works directly. Every page is saved at full size into one folder, and can be
merged into a PDF. Items marked "In Copyright" (rightsstatements.org) are refused.
"""

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit

from anyget.convert.pdf import images_to_pdf
from anyget.core.filenames import safe_join, sanitize_filename, unique_path
from anyget.core.net import Net
from anyget.core.settings import Settings
from anyget.handlers.base import (
    Choice,
    DownloadResult,
    HandlerError,
    JobRef,
    Probe,
    ProgressCallback,
)
from anyget.handlers.http_generic import HttpGenericHandler
from anyget.handlers.multi import RemoteFile, download_many
from anyget.libraries.registry import library_for_host

MAX_PAGES = 2000
_GALLICA = re.compile(r"/ark:/12148/([a-z0-9]+)", re.I)
_LOC = re.compile(r"^/(?:item|resource)/([^/]+)")
_NDL = re.compile(r"^/(?:info:ndljp/)?pid/(\d+)")
_EUROPEANA = re.compile(r"/item/(\d+)/([^/?#]+)")
_QDL = re.compile(r"^/[a-z]{2}/archive/([^/]+)/([^/?#]+)")
_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/tiff": "tif", "image/jp2": "jp2"}


@dataclass(frozen=True)
class Page:
    label: str
    url: str
    thumbnail: str | None
    ext: str


@dataclass(frozen=True)
class Manifest:
    title: str
    pages: list[Page]
    rights: str | None
    attribution: str | None


def manifest_url_for(url: str, settings: Settings | None = None) -> str | None:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().removeprefix("www.")
    path = parts.path
    if path.endswith(("/manifest.json", "/manifest")) or path.endswith("manifest.json"):
        return url
    if host == "gallica.bnf.fr" and (m := _GALLICA.search(path)) and "/iiif/" not in path:
        return f"https://gallica.bnf.fr/iiif/ark:/12148/{m.group(1)}/manifest.json"
    if host == "loc.gov" and (m := _LOC.match(path)):
        return f"https://www.loc.gov/item/{m.group(1)}/manifest.json"
    if host == "dl.ndl.go.jp" and (m := _NDL.match(path)):
        return f"https://dl.ndl.go.jp/api/iiif/{m.group(1)}/manifest.json"
    if host == "europeana.eu" and (m := _EUROPEANA.search(path)):
        key = settings.europeana_key if settings else ""
        suffix = f"?wskey={quote(key)}" if key else ""
        return f"https://iiif.europeana.eu/presentation/{m.group(1)}/{m.group(2)}/manifest{suffix}"
    if host == "qdl.qa" and (m := _QDL.match(path)):
        return f"https://www.qdl.qa/en/iiif/{m.group(1)}/{m.group(2)}/manifest"
    return None


def _label(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return next((t for t in (_label(v) for v in value) if t), "")
    if isinstance(value, dict):
        if "@value" in value:
            return str(value["@value"]).strip()
        for key in ("en", "none", *value.keys()):
            if key in value:
                return _label(value[key])
    return ""


def _service(resource: dict[str, Any]) -> tuple[str | None, bool]:
    """(service base URL, speaks Image API 3) for an image resource."""
    services = resource.get("service") or []
    for svc in services if isinstance(services, list) else [services]:
        if not isinstance(svc, dict):
            continue
        base = svc.get("id") or svc.get("@id")
        if base:
            kind = str(svc.get("type") or svc.get("@type") or "")
            profile = str(svc.get("profile") or "")
            v3 = "ImageService3" in kind or "image/3" in profile
            return str(base).rstrip("/"), v3
    return None, False


def _page(label: str, resource: dict[str, Any]) -> Page | None:
    base, v3 = _service(resource)
    direct = resource.get("id") or resource.get("@id")
    ext = _EXT.get(str(resource.get("format") or ""), "jpg")
    if base:
        size = "max" if v3 else "full"
        return Page(
            label, f"{base}/full/{size}/0/default.jpg", f"{base}/full/240,/0/default.jpg", "jpg"
        )
    if direct:
        return Page(label, str(direct), None, ext)
    return None


def parse_manifest(data: dict[str, Any]) -> Manifest:
    pages: list[Page] = []
    if "sequences" in data:  # Presentation 2
        canvases = (data.get("sequences") or [{}])[0].get("canvases") or []
        for index, canvas in enumerate(canvases, 1):
            images = canvas.get("images") or []
            resource = images[0].get("resource") if images else None
            if isinstance(resource, dict) and (
                page := _page(_label(canvas.get("label")) or str(index), resource)
            ):
                pages.append(page)
        rights = _label(data.get("license")) or None
        attribution = _label(data.get("attribution")) or None
    else:  # Presentation 3
        for index, canvas in enumerate(data.get("items") or [], 1):
            try:
                body = canvas["items"][0]["items"][0]["body"]
            except (KeyError, IndexError, TypeError):
                continue
            if isinstance(body, list):
                body = body[0] if body else {}
            if isinstance(body, dict) and (
                page := _page(_label(canvas.get("label")) or str(index), body)
            ):
                pages.append(page)
        rights = _label(data.get("rights")) or None
        statement = data.get("requiredStatement") or {}
        attribution = _label(statement.get("value")) if isinstance(statement, dict) else None
    return Manifest(
        title=_label(data.get("label")) or "IIIF item",
        pages=pages[:MAX_PAGES],
        rights=rights,
        attribution=attribution or None,
    )


class IiifLibraryHandler:
    name = "iiif_library"

    def __init__(self, net: Net, settings: Settings | None = None) -> None:
        self.net = net
        self.http = HttpGenericHandler(net)
        self.settings = settings

    def can_handle(self, url: str) -> bool:
        return manifest_url_for(url, self.settings) is not None

    async def _manifest(self, url: str) -> tuple[str, Manifest]:
        manifest_url = manifest_url_for(url, self.settings)
        if manifest_url is None:
            raise HandlerError("unsupported", "not a IIIF manifest or a known library item")
        response = await self.net.request(
            "GET", manifest_url, headers={"Accept": "application/ld+json, application/json"}
        )
        if response.status_code == 404:
            raise HandlerError("not_found", "the library has no item like this")
        if response.status_code in (401, 403):
            raise HandlerError(
                "restricted", "this item is not published openly (read it on the library's site)"
            )
        if response.status_code >= 400:
            raise HandlerError("upstream", f"the library answered {response.status_code}")
        try:
            manifest = parse_manifest(response.json())
        except ValueError as exc:
            raise HandlerError("unsupported", "the library did not send a IIIF manifest") from exc
        if manifest.rights and "rightsstatements.org/vocab/inc" in manifest.rights.lower():
            raise HandlerError("in_copyright", "this item is in copyright: view it on the site")
        if not manifest.pages:
            raise HandlerError("not_found", "this item has no page images")
        return manifest_url, manifest

    async def probe(self, url: str, options: dict[str, Any] | None = None) -> Probe:
        manifest_url, manifest = await self._manifest(url)
        library = library_for_host(urlsplit(url).hostname or "")
        return Probe(
            url=url,
            handler=self.name,
            title=manifest.title,
            thumbnail=manifest.pages[0].thumbnail,
            choices=[
                Choice(id=str(i), label=page.label, kind="image", ext=page.ext, default=True)
                for i, page in enumerate(manifest.pages, 1)
            ],
            extra={
                "kind": "iiif",
                "manifest": manifest_url,
                "count": len(manifest.pages),
                "library": library.name if library else None,
                "rights": manifest.rights,
                "attribution": manifest.attribution,
                "items": [
                    {"index": i, "url": page.thumbnail or page.url}
                    for i, page in enumerate(manifest.pages, 1)
                ],
            },
        )

    async def download(
        self, job: JobRef, options: dict[str, Any], progress_cb: ProgressCallback
    ) -> DownloadResult:
        _, manifest = await self._manifest(job.url)
        numbered = list(enumerate(manifest.pages, 1))
        wanted = options.get("files")
        if isinstance(wanted, list) and wanted:
            ids = {str(w) for w in wanted}
            numbered = [(i, p) for i, p in numbered if str(i) in ids]
        if not numbered:
            raise HandlerError("not_found", "none of the chosen pages are in this item")
        title = sanitize_filename(manifest.title, fallback="iiif-item")
        folder = safe_join(job.output_dir, title)
        folder.mkdir(parents=True, exist_ok=True)
        files = [RemoteFile(url=page.url, name=f"{i:04d}.{page.ext}") for i, page in numbered]
        result = await download_many(self.http, job, files, folder, progress_cb)
        if options.get("pdf"):
            pdf = images_to_pdf(
                result.paths, unique_path(safe_join(job.output_dir, f"{title}.pdf"))
            )
            return DownloadResult(paths=[pdf, *result.paths], checksum_ok=result.checksum_ok)
        return result
