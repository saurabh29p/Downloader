"""Live archive.org / Wayback tests (real network, public-domain material only).

- A Project Gutenberg item on archive.org (collection "gutenberg"): download its
  smallest PDF and verify the md5 archive.org publishes.
- A 2005 Wayback snapshot of http://example.com/ (IANA's example page), raw bytes.
"""

import pytest

from anyget.core.net import Net
from anyget.core.settings import Settings
from anyget.handlers.archive_org import ArchiveOrgHandler, build_query, search
from anyget.handlers.base import JobContext
from anyget.handlers.wayback import WaybackHandler, list_snapshots

pytestmark = [pytest.mark.live]


async def test_gutenberg_pdf_with_md5(settings: Settings) -> None:
    net = Net(settings)
    handler = ArchiveOrgHandler(net)
    page = await search(
        net, build_query("format:PDF", collection="gutenberg", mediatype="texts"), rows=20
    )
    assert page.items, "no Gutenberg items found"
    for hit in page.items:
        item = await handler.item(hit.identifier)
        pdfs = [
            f
            for f in item.files
            if f.name.lower().endswith(".pdf") and f.md5 and f.size and not f.private
        ]
        if item.restricted or not pdfs:
            continue
        smallest = min(pdfs, key=lambda f: f.size or 0)
        job = JobContext(
            id="live-ia",
            url=f"https://archive.org/details/{item.identifier}",
            output_dir=settings.downloads_dir,
        )
        result = await handler.download(job, {"files": [smallest.name]}, lambda _p: None)
        assert result.checksum_ok is True
        assert result.paths[0].read_bytes()[:5] == b"%PDF-"
        break
    else:
        pytest.fail("no Gutenberg item with a PDF in the first 20 results")
    await net.aclose()


async def test_2005_snapshot_raw(settings: Settings) -> None:
    net = Net(settings)
    snapshots = await list_snapshots(net, "example.com", year_from=2005, year_to=2005, limit=5)
    assert snapshots.snapshots, "no 2005 snapshots of example.com"
    first = snapshots.snapshots[0]
    handler = WaybackHandler(net)
    url = f"https://web.archive.org/web/{first.timestamp}/{first.original}"
    probe = await handler.probe(url)
    job = JobContext(id="live-wb", url=url, output_dir=settings.downloads_dir)
    result = await handler.download(job, {"probe": probe.model_dump(mode="json")}, lambda _p: None)
    body = result.paths[0].read_bytes().lower()
    assert b"<html" in body and b"wayback" not in body[:2000]  # raw capture, no toolbar
    await net.aclose()
