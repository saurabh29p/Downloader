"""Live tests for code hosts, cloud links, galleries and AI repos (real network).

Only openly licensed or public sample material:
- octocat/Hello-World on GitHub (GitHub's public sample repo): repo zip and one file.
- A public Google Drive file: set ANYGET_LIVE_DRIVE_URL to a file you shared yourself
  (no stable public-domain Drive file exists, so the test is skipped without it).
- A Flickr Commons album (no known copyright restrictions); override with
  ANYGET_LIVE_FLICKR_ALBUM.
- hf-internal-testing/tiny-random-bert on Hugging Face (Apache-2.0 test model).
"""

import os
import zipfile

import pytest

from anyget.core.net import Net
from anyget.core.settings import Settings
from anyget.handlers.ai_resources import AiResourcesHandler
from anyget.handlers.base import JobContext
from anyget.handlers.cloud_share import CloudShareHandler
from anyget.handlers.gallery import GalleryHandler
from anyget.handlers.git_code import GitCodeHandler

pytestmark = [pytest.mark.live]

REPO = "https://github.com/octocat/Hello-World"
FLICKR = "https://www.flickr.com/photos/library_of_congress/albums/72157603624867509"
HF = "https://huggingface.co/hf-internal-testing/tiny-random-bert"


def _job(settings: Settings, job_id: str, url: str) -> JobContext:
    return JobContext(id=job_id, url=url, output_dir=settings.downloads_dir)


async def test_github_repo_zip(settings: Settings) -> None:
    net = Net(settings)
    handler = GitCodeHandler(net, settings)
    result = await handler.download(_job(settings, "live-repo", REPO), {}, lambda _p: None)
    assert zipfile.is_zipfile(result.paths[0])
    with zipfile.ZipFile(result.paths[0]) as archive:
        assert any(name.endswith("README") for name in archive.namelist())
    await net.aclose()


async def test_github_single_file(settings: Settings) -> None:
    net = Net(settings)
    handler = GitCodeHandler(net, settings)
    url = f"{REPO}/blob/master/README"
    result = await handler.download(_job(settings, "live-file", url), {}, lambda _p: None)
    assert result.paths[0].name == "README"
    assert b"Hello World" in result.paths[0].read_bytes()
    await net.aclose()


async def test_drive_file(settings: Settings) -> None:
    url = os.environ.get("ANYGET_LIVE_DRIVE_URL")
    if not url:
        pytest.skip("set ANYGET_LIVE_DRIVE_URL to a public Drive file you shared")
    net = Net(settings)
    handler = CloudShareHandler(net)
    probe = await handler.probe(url)
    options = {"probe": probe.model_dump(mode="json")}
    result = await handler.download(_job(settings, "live-drive", url), options, lambda _p: None)
    assert result.paths[0].stat().st_size > 0
    assert b"<html" not in result.paths[0].read_bytes()[:500].lower()
    await net.aclose()


async def test_flickr_commons_album(settings: Settings) -> None:
    url = os.environ.get("ANYGET_LIVE_FLICKR_ALBUM") or FLICKR
    net = Net(settings)
    handler = GalleryHandler(net)
    assert handler.can_handle(url)
    probe = await handler.probe(url)
    assert probe.extra["count"] >= 2
    first_two = [c.id for c in probe.choices[:2]]
    options = {"probe": probe.model_dump(mode="json"), "files": first_two}
    result = await handler.download(_job(settings, "live-flickr", url), options, lambda _p: None)
    assert len(result.paths) == 2
    for path in result.paths:
        head = path.read_bytes()[:4]
        assert head.startswith(b"\xff\xd8") or head == b"\x89PNG"
    await net.aclose()


async def test_hugging_face_small_file(settings: Settings) -> None:
    net = Net(settings)
    handler = AiResourcesHandler(net, settings)
    probe = await handler.probe(HF)
    assert "config.json" in {c.id for c in probe.choices}
    result = await handler.download(
        _job(settings, "live-hf", HF), {"files": ["config.json"]}, lambda _p: None
    )
    assert result.paths[0].read_bytes().lstrip().startswith(b"{")
    await net.aclose()
