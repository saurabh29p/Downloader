"""Code hosts, cloud shares, AI resources, galleries and web pages (offline, respx)."""

import hashlib
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from anyget.core.net import Net
from anyget.core.settings import Settings
from anyget.handlers import gallery as gallery_mod
from anyget.handlers.ai_resources import AiResourcesHandler
from anyget.handlers.base import HandlerError, JobContext
from anyget.handlers.cloud_share import (
    CloudShareHandler,
    direct_url,
    drive_direct,
    onedrive_direct,
    provider,
)
from anyget.handlers.gallery import GalleryHandler, parse_dump
from anyget.handlers.git_code import GitCodeHandler, parse_target, raw_file_url, repo_zip_url
from anyget.handlers.http_generic import HttpGenericHandler
from anyget.handlers.webpage import extract_links


@pytest.fixture
async def net(settings: Settings) -> AsyncIterator[Net]:
    n = Net(settings)
    yield n
    await n.aclose()


def file_response(data: bytes, **headers: str) -> httpx.Response:
    return httpx.Response(200, headers={"Content-Length": str(len(data)), **headers}, content=data)


def mock_file(url: str, data: bytes, **headers: str) -> None:
    respx.head(url).mock(
        return_value=httpx.Response(200, headers={"Content-Length": str(len(data)), **headers})
    )
    respx.get(url).mock(return_value=file_response(data, **headers))


def job(settings: Settings, url: str, job_id: str = "j") -> JobContext:
    return JobContext(id=job_id, url=url, output_dir=settings.downloads_dir)


# ----- code hosts ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "kind", "extra"),
    [
        ("https://github.com/octocat/Hello-World", "repo", {}),
        ("https://github.com/octocat/Hello-World.git", "repo", {"repo": "Hello-World"}),
        ("https://github.com/o/r/blob/main/src/a.py", "file", {"ref": "main", "path": "src/a.py"}),
        ("https://github.com/o/r/tree/v1.0/docs", "folder", {"ref": "v1.0", "path": "docs"}),
        ("https://github.com/o/r/releases/tag/v2.1", "release", {"tag": "v2.1"}),
        ("https://github.com/o/r/releases/latest", "release", {"tag": "latest"}),
        (
            "https://github.com/o/r/releases/download/v2/app.zip",
            "release_asset",
            {"tag": "v2", "path": "app.zip"},
        ),
        ("https://raw.githubusercontent.com/o/r/main/README.md", "file", {"path": "README.md"}),
        (
            "https://gist.github.com/octocat/6cad326836d38bd3a7ae",
            "gist",
            {"gist_id": "6cad326836d38bd3a7ae"},
        ),
        ("https://gitlab.com/group/sub/proj", "repo", {"owner": "group/sub", "repo": "proj"}),
        ("https://gitlab.com/g/p/-/blob/main/x/y.txt", "file", {"ref": "main", "path": "x/y.txt"}),
        ("https://gitlab.com/g/p/-/tree/main/docs", "folder", {"path": "docs"}),
        ("https://codeberg.org/forgejo/forgejo", "repo", {}),
        (
            "https://codeberg.org/o/r/src/branch/main/README.md",
            "file",
            {"ref": "main", "path": "README.md"},
        ),
        (
            "https://bitbucket.org/o/r/src/master/setup.py",
            "file",
            {"ref": "master", "path": "setup.py"},
        ),
        ("https://bitbucket.org/o/r", "repo", {}),
    ],
)
def test_parse_code_links(url: str, kind: str, extra: dict[str, str]) -> None:
    target = parse_target(url)
    assert target.kind == kind
    for key, value in extra.items():
        assert getattr(target, key) == value


def test_code_urls() -> None:
    assert raw_file_url(parse_target("https://github.com/o/r/blob/main/a b.py")) == (
        "https://raw.githubusercontent.com/o/r/main/a%20b.py"
    )
    assert raw_file_url(parse_target("https://gitlab.com/g/p/-/blob/main/x.txt")) == (
        "https://gitlab.com/g/p/-/raw/main/x.txt"
    )
    assert (
        repo_zip_url(parse_target("https://github.com/o/r"))
        == "https://github.com/o/r/archive/HEAD.zip"
    )
    assert (
        repo_zip_url(parse_target("https://bitbucket.org/o/r"))
        == "https://bitbucket.org/o/r/get/HEAD.zip"
    )
    folder = parse_target("https://gitlab.com/g/p/-/tree/main/docs")
    assert (
        repo_zip_url(folder, "main") == "https://gitlab.com/g/p/-/archive/main/p-main.zip?path=docs"
    )


@respx.mock
async def test_github_repo_zip_and_single_file(net: Net, settings: Settings) -> None:
    handler = GitCodeHandler(net, settings)
    mock_file("https://github.com/octocat/Hello-World/archive/HEAD.zip", b"PK zip")
    result = await handler.download(
        job(settings, "https://github.com/octocat/Hello-World"), {}, lambda _p: None
    )
    assert [p.name for p in result.paths] == ["Hello-World-HEAD.zip"]
    mock_file(
        "https://raw.githubusercontent.com/octocat/Hello-World/master/README", b"Hello World!\n"
    )
    url = "https://github.com/octocat/Hello-World/blob/master/README"
    result = await handler.download(job(settings, url, "j2"), {}, lambda _p: None)
    assert result.paths[0].read_bytes() == b"Hello World!\n"


@respx.mock
async def test_github_folder_via_tree_api(net: Net, settings: Settings) -> None:
    settings.github_token = "ghp_test"  # noqa: S105
    handler = GitCodeHandler(net, settings)
    route = respx.get("https://api.github.com/repos/o/r/git/trees/main?recursive=1").mock(
        return_value=httpx.Response(
            200,
            json={
                "tree": [
                    {"path": "docs", "type": "tree"},
                    {"path": "docs/a.md", "type": "blob", "size": 3},
                    {"path": "docs/img/b.png", "type": "blob", "size": 4},
                    {"path": "src/c.py", "type": "blob", "size": 5},
                ]
            },
        )
    )
    mock_file("https://raw.githubusercontent.com/o/r/main/docs/a.md", b"# a")
    mock_file("https://raw.githubusercontent.com/o/r/main/docs/img/b.png", b"\x89PNG")
    probe = await handler.probe("https://github.com/o/r/tree/main/docs")
    assert [c.id for c in probe.choices] == ["a.md", "img/b.png"]
    assert route.calls[0].request.headers["authorization"] == "Bearer ghp_test"
    result = await handler.download(
        job(settings, "https://github.com/o/r/tree/main/docs"), {}, lambda _p: None
    )
    assert sorted(
        p.relative_to(settings.downloads_dir.resolve()).as_posix() for p in result.paths
    ) == [
        "o_r_ docs/a.md",
        "o_r_ docs/img/b.png",
    ]


@respx.mock
async def test_github_release_assets_and_rate_limit(net: Net, settings: Settings) -> None:
    handler = GitCodeHandler(net, settings)
    respx.get("https://api.github.com/repos/o/r/releases/tags/v2").mock(
        return_value=httpx.Response(
            200,
            json={
                "tag_name": "v2",
                "name": "Version 2",
                "assets": [
                    {
                        "name": "app-linux.tar.gz",
                        "size": 6,
                        "browser_download_url": "https://github.com/o/r/releases/download/v2/app-linux.tar.gz",
                    },
                    {
                        "name": "app-win.zip",
                        "size": 5,
                        "browser_download_url": "https://github.com/o/r/releases/download/v2/app-win.zip",
                    },
                ],
            },
        )
    )
    mock_file("https://github.com/o/r/releases/download/v2/app-win.zip", b"PKwin")
    url = "https://github.com/o/r/releases/tag/v2"
    probe = await handler.probe(url)
    assert [c.id for c in probe.choices] == ["app-linux.tar.gz", "app-win.zip", "r-v2-source.zip"]
    result = await handler.download(job(settings, url), {"files": ["app-win.zip"]}, lambda _p: None)
    assert [p.name for p in result.paths] == ["app-win.zip"]

    respx.get("https://api.github.com/repos/o/r/releases/latest").mock(
        return_value=httpx.Response(403)
    )
    with pytest.raises(HandlerError) as limited:
        await handler.probe("https://github.com/o/r/releases/latest")
    assert limited.value.code == "rate_limited"


@respx.mock
async def test_gist_files(net: Net, settings: Settings) -> None:
    handler = GitCodeHandler(net, settings)
    respx.get("https://api.github.com/gists/abc123").mock(
        return_value=httpx.Response(
            200,
            json={
                "description": "my snippets",
                "files": {
                    "a.py": {
                        "raw_url": "https://gist.githubusercontent.com/u/abc123/raw/a.py",
                        "size": 4,
                    },
                    "b.sh": {
                        "raw_url": "https://gist.githubusercontent.com/u/abc123/raw/b.sh",
                        "size": 4,
                    },
                },
            },
        )
    )
    mock_file("https://gist.githubusercontent.com/u/abc123/raw/a.py", b"pass")
    mock_file("https://gist.githubusercontent.com/u/abc123/raw/b.sh", b"echo")
    result = await handler.download(
        job(settings, "https://gist.github.com/u/abc123"), {}, lambda _p: None
    )
    assert [p.name for p in result.paths] == ["a.py", "b.sh"]
    assert result.paths[0].parent.name == "my snippets"


# ----- cloud shares --------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOp/view?usp=sharing",
            "https://drive.usercontent.google.com/download?id=1AbCdEfGhIjKlMnOp&export=download&confirm=t",
        ),
        (
            "https://drive.google.com/open?id=1AbCdEfGhIjKlMnOp",
            "https://drive.usercontent.google.com/download?id=1AbCdEfGhIjKlMnOp&export=download&confirm=t",
        ),
        (
            "https://docs.google.com/document/d/1AbCdEfGhIjKlMnOp/edit",
            "https://docs.google.com/document/d/1AbCdEfGhIjKlMnOp/export?format=pdf",
        ),
        (
            "https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOp/edit#gid=0",
            "https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOp/export?format=xlsx",
        ),
        (
            "https://www.dropbox.com/scl/fi/xyz/report.pdf?rlkey=abc&dl=0",
            "https://www.dropbox.com/scl/fi/xyz/report.pdf?rlkey=abc&dl=1",
        ),
        ("https://www.dropbox.com/s/abc/photo.jpg", "https://www.dropbox.com/s/abc/photo.jpg?dl=1"),
    ],
)
def test_cloud_direct_urls(url: str, expected: str) -> None:
    assert direct_url(url) == expected


def test_onedrive_and_providers() -> None:
    assert onedrive_direct("https://1drv.ms/u/s!Abc").startswith(
        "https://api.onedrive.com/v1.0/shares/u!"
    )
    assert provider("https://mega.nz/file/abc#key") == "mega"
    assert provider("https://contoso.sharepoint.com/:x:/g/abc") == "onedrive"
    with pytest.raises(HandlerError):
        drive_direct("https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOp")


@respx.mock
async def test_drive_download_and_private_file(net: Net, settings: Settings) -> None:
    handler = CloudShareHandler(net)
    url = "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOp/view"
    direct = drive_direct(url)
    mock_file(
        direct, b"%PDF-1.4 drive", **{"Content-Disposition": 'attachment; filename="notes.pdf"'}
    )
    probe = await handler.probe(url)
    assert probe.title == "notes.pdf" and probe.extra["provider"] == "gdrive"
    result = await handler.download(
        job(settings, url), {"probe": probe.model_dump(mode="json")}, lambda _p: None
    )
    assert result.paths[0].name == "notes.pdf"

    private = "https://drive.google.com/file/d/1PrivatePrivateX/view"
    respx.head(drive_direct(private)).mock(
        return_value=httpx.Response(200, headers={"Content-Type": "text/html"})
    )
    respx.get(drive_direct(private)).mock(
        return_value=httpx.Response(
            200, headers={"Content-Type": "text/html"}, text="<title>Sign in</title>"
        )
    )
    with pytest.raises(HandlerError) as info:  # a sign-in page is never saved as the file
        await handler.probe(private)
    assert info.value.code == "login_required"


async def test_mega_needs_megatools(net: Net, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: None)
    with pytest.raises(HandlerError) as info:
        await CloudShareHandler(net).probe("https://mega.nz/file/abc#key")
    assert info.value.code == "unsupported"


# ----- AI resources ----------------------------------------------------------------


@respx.mock
async def test_hugging_face_files_with_sha256(net: Net, settings: Settings) -> None:
    weights = b"safetensors-bytes"
    respx.get("https://huggingface.co/api/models/acme/tiny/tree/main?recursive=true").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"type": "directory", "path": "onnx"},
                {"type": "file", "path": "config.json", "size": 2},
                {
                    "type": "file",
                    "path": "model.safetensors",
                    "size": 99,
                    "lfs": {"oid": hashlib.sha256(weights).hexdigest(), "size": len(weights)},
                },
            ],
        )
    )
    mock_file("https://huggingface.co/acme/tiny/resolve/main/config.json", b"{}")
    mock_file("https://huggingface.co/acme/tiny/resolve/main/model.safetensors", weights)
    handler = AiResourcesHandler(net, settings)
    assert handler.can_handle("https://huggingface.co/acme/tiny")
    probe = await handler.probe("https://huggingface.co/acme/tiny")
    assert [c.id for c in probe.choices] == ["config.json", "model.safetensors"]
    assert all(c.default for c in probe.choices)  # small repo: everything
    result = await handler.download(
        job(settings, "https://huggingface.co/acme/tiny"), {}, lambda _p: None
    )
    assert result.checksum_ok is True and [p.name for p in result.paths] == [
        "config.json",
        "model.safetensors",
    ]


@respx.mock
async def test_gated_hugging_face_repo(net: Net, settings: Settings) -> None:
    respx.get("https://huggingface.co/api/datasets/org/gated/tree/main?recursive=true").mock(
        return_value=httpx.Response(401)
    )
    with pytest.raises(HandlerError) as info:
        await AiResourcesHandler(net, settings).probe("https://huggingface.co/datasets/org/gated")
    assert info.value.code == "login_required"


@respx.mock
async def test_civitai_and_kaggle(net: Net, settings: Settings) -> None:
    respx.get("https://civitai.com/api/v1/models/123").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "Cool LoRA",
                "modelVersions": [
                    {
                        "name": "v1",
                        "files": [
                            {
                                "name": "cool.safetensors",
                                "sizeKB": 1.5,
                                "downloadUrl": "https://civitai.com/api/download/models/9",
                                "hashes": {"SHA256": "ABC"},
                            }
                        ],
                    }
                ],
            },
        )
    )
    handler = AiResourcesHandler(net, settings)
    probe = await handler.probe("https://civitai.com/models/123/cool-lora")
    assert probe.title == "Cool LoRA" and probe.choices[0].id == "v1/cool.safetensors"
    with pytest.raises(HandlerError) as kaggle:
        await handler.probe("https://www.kaggle.com/datasets/owner/data")
    assert kaggle.value.code == "login_required"


# ----- galleries -------------------------------------------------------------------


GALLERY_DUMP = json.dumps(
    [
        [2, {"category": "flickr", "album": {"title": "x"}, "title": "Colour photos 1940s"}],
        [
            3,
            "https://live.staticflickr.com/1/a_o.jpg",
            {"filename": "a", "extension": "jpg", "width": 800, "height": 600},
        ],
        [3, "https://live.staticflickr.com/2/b_o.jpg", {"filename": "b", "extension": "jpg"}],
    ]
)


def test_parse_dump() -> None:
    title, items = parse_dump(GALLERY_DUMP)
    assert title == "Colour photos 1940s"
    assert [i["name"] for i in items] == ["a.jpg", "b.jpg"]
    with pytest.raises(HandlerError):
        parse_dump(json.dumps([[-1, {"message": "HTTP 404"}]]))


@respx.mock
async def test_gallery_probe_and_download(
    net: Net, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeProcess:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return GALLERY_DUMP.encode(), b""

    calls: list[tuple[Any, ...]] = []

    async def fake_exec(*args: Any, **kwargs: Any) -> FakeProcess:
        calls.append(args)
        return FakeProcess()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr(gallery_mod, "gallery_hosts", lambda: frozenset({"flickr.com"}))
    mock_file("https://live.staticflickr.com/1/a_o.jpg", b"JPEGa")
    mock_file("https://live.staticflickr.com/2/b_o.jpg", b"JPEGb")
    handler = GalleryHandler(net)
    url = "https://www.flickr.com/photos/x/albums/1"
    assert handler.can_handle(url) and not handler.can_handle("https://example.org/x")
    probe = await handler.probe(url)
    assert probe.extra["count"] == 2 and "-J" in calls[0]
    result = await handler.download(
        job(settings, url),
        {"probe": probe.model_dump(mode="json"), "files": ["2"]},
        lambda _p: None,
    )
    assert [p.name for p in result.paths] == ["002 b.jpg"]
    assert respx.calls.last.request.headers["referer"] == url


async def test_gallery_hosts_from_real_gallery_dl() -> None:
    gallery_mod.gallery_hosts.cache_clear()
    hosts = gallery_mod.gallery_hosts()
    assert {"flickr.com", "imgur.com", "deviantart.com"} <= hosts


# ----- web pages -----------------------------------------------------------------------


PAGE = """<!doctype html><html><head><title> Annual  reports </title><base href="/files/"></head>
<body><a href="2024.pdf">2024</a> <a href="https://cdn.example.org/2023.pdf#page=2">2023</a>
<a href="about.html">About</a> <img src="chart.png" srcset="chart@2x.png 2x, chart.png 1x">
<video src="/media/intro.mp4"></video><a href="mailto:x@y.z">mail</a><a href="2024.pdf">dup</a>
</body></html>"""


def test_extract_links() -> None:
    title, links = extract_links(PAGE, "https://reports.test/annual/")
    assert title == "Annual reports"
    assert [(link["url"], link["kind"]) for link in links] == [
        ("https://reports.test/files/2024.pdf", "document"),
        ("https://cdn.example.org/2023.pdf", "document"),
        ("https://reports.test/files/chart.png", "image"),
        ("https://reports.test/files/chart@2x.png", "image"),
        ("https://reports.test/media/intro.mp4", "video"),
    ]


@respx.mock
async def test_webpage_save_page_and_links(net: Net, settings: Settings) -> None:
    url = "https://reports.test/annual/"
    respx.head(url).mock(return_value=httpx.Response(200, headers={"Content-Type": "text/html"}))
    respx.get(url).mock(
        return_value=httpx.Response(
            200, headers={"Content-Type": "text/html; charset=utf-8"}, text=PAGE
        )
    )
    mock_file("https://reports.test/files/2024.pdf", b"%PDF 2024")
    http = HttpGenericHandler(net)
    probe = await http.probe(url)
    assert probe.choices[0].id == "page" and probe.choices[0].default
    options = {
        "probe": probe.model_dump(mode="json"),
        "files": ["page", "https://reports.test/files/2024.pdf"],
    }
    result = await http.download(job(settings, url), options, lambda _p: None)
    names = [p.name for p in result.paths]
    assert names == ["Annual reports.html", "2024.pdf"]
    assert "Annual" in result.paths[0].read_text()
    with pytest.raises(HandlerError):
        await http.download(
            job(settings, url, "j2"),
            {"probe": probe.model_dump(mode="json"), "files": ["https://evil.test/x.pdf"]},
            lambda _p: None,
        )


def test_user_cannot_set_private_headers(settings: Settings) -> None:
    from fastapi.testclient import TestClient

    from anyget.main import create_app

    with TestClient(create_app(settings)) as client, respx.mock(assert_all_called=False) as mock:
        mock.head("https://files.test/a.bin").mock(
            return_value=httpx.Response(200, headers={"Content-Length": "1"})
        )
        body = {
            "urls": ["https://files.test/a.bin"],
            "options": {"_headers": {"Authorization": "x"}, "md5": "y"},
        }
        created = client.post("/api/jobs", json=body).json()
    assert created["jobs"][0]["options"] == {"md5": "y"}


def test_paths_used_in_tests_exist() -> None:
    assert Path(gallery_mod.__file__).exists()
