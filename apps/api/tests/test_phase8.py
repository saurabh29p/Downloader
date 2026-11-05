"""Library index and previews, folder templates, saved settings, watches, CLI helpers."""

import asyncio
import zipfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from anyget.cli.main import links_in
from anyget.core import templates
from anyget.core.jobs import JobState
from anyget.core.services import Services
from anyget.core.settings import Settings
from anyget.handlers.base import HandlerError, Probe
from anyget.library.epub import epub_preview
from anyget.library.kinds import kind_of
from anyget.main import create_app
from anyget.watch.models import WatchIn

DATA = b"x" * 5000


def make_epub(path: Path, chapters: list[str], title: str = "A Book") -> Path:
    with zipfile.ZipFile(path, "w") as book:
        book.writestr("mimetype", "application/epub+zip")
        book.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?>'
            '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles></container>',
        )
        items = "".join(
            f'<item id="c{i}" href="c{i}.xhtml" media-type="application/xhtml+xml"/>'
            for i in range(len(chapters))
        )
        spine = "".join(f'<itemref idref="c{i}"/>' for i in range(len(chapters)))
        book.writestr(
            "OEBPS/content.opf",
            '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f"<metadata><dc:title>{title}</dc:title></metadata>"
            f"<manifest>{items}</manifest><spine>{spine}</spine></package>",
        )
        for i, text in enumerate(chapters):
            book.writestr(
                f"OEBPS/c{i}.xhtml",
                f"<html><head><style>p{{color:red}}</style></head><body><h1>Ch {i}</h1>"
                f"<p>{text}</p><script>alert(1)</script></body></html>",
            )
    return path


@pytest.fixture
async def services(settings: Settings) -> AsyncIterator[Services]:
    svc = Services.build(settings)
    yield svc
    await svc.stop()


# ----- kinds, templates, epub ---------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("a.MP4", "video"),
        ("b.opus", "audio"),
        ("c.jpeg", "image"),
        ("d.pdf", "pdf"),
        ("e.epub", "epub"),
        ("f.srt", "text"),
        ("g.zip", "archive"),
        ("h.bin", "other"),
    ],
)
def test_kinds(name: str, kind: str) -> None:
    assert kind_of(name) == kind


def test_folder_templates() -> None:
    when = datetime(2026, 11, 5, tzinfo=UTC)
    parts = templates.render(
        "{type}/{source}/{year}-{month}",
        kind="videos",
        url="https://www.youtube.com/watch?v=x",
        title="t",
        when=when,
    )
    assert parts == ["videos", "youtube.com", "2026-11"]
    assert templates.render("", kind="files", url="https://x.org", title="t") == []
    # Traversal and odd characters are neutralized; parts stay single folder names.
    evil = templates.render("../{title}/..", kind="files", url="https://x.org", title="a/../b:c")
    assert ".." not in evil and all("/" not in p for p in evil)
    with pytest.raises(templates.TemplateError):
        templates.validate("{nope}")
    with pytest.raises(templates.TemplateError):
        templates.validate("a/b/c/d/e")
    assert templates.kind_for("ytdlp", {"preset": "audio"}) == "audio"


def test_epub_preview(tmp_path: Path) -> None:
    book = make_epub(tmp_path / "b.epub", ["It was the best of times.", "Second chapter."])
    preview = epub_preview(book)
    assert preview.title == "A Book"
    assert "best of times" in preview.text and "Second chapter" in preview.text
    assert "alert" not in preview.text and "color" not in preview.text
    assert preview.truncated is False


# ----- library index ---------------------------------------------------------------


async def test_finished_jobs_are_indexed_with_dedupe(services: Services) -> None:
    root = services.settings.downloads_dir
    (root / "sub").mkdir(parents=True)
    (root / "a.mp4").write_bytes(DATA)
    (root / "a.en.srt").write_bytes(b"1\n00:00 --> 00:01\nhi")
    (root / "sub" / "copy.mp4").write_bytes(DATA)  # same bytes, different job
    job = services.store.create("https://videos.test/a")
    services.store.update(
        job.id, state=JobState.done, rel_path="a.mp4", files=["a.en.srt"], title="Video A"
    )
    items = await services.library.add_job(services.store.get(job.id))  # type: ignore[arg-type]
    assert [i.kind for i in items] == ["video", "text"]
    assert items[0].title == "Video A" and items[0].source_url == "https://videos.test/a"
    assert items[1].duplicate_of is None  # subtitles of the same job are not copies
    other = services.store.create("https://mirror.test/a")
    services.store.update(other.id, state=JobState.done, rel_path="sub/copy.mp4")
    copy = (await services.library.add_job(services.store.get(other.id)))[0]  # type: ignore[arg-type]
    assert copy.duplicate_of == items[0].id
    page = services.library.search(duplicates=True)
    assert [i.rel_path for i in page.items] == ["sub/copy.mp4"]


async def test_scan_skips_partials_and_forgets_removed_files(services: Services) -> None:
    root = services.settings.downloads_dir
    root.mkdir(parents=True, exist_ok=True)
    (root / "book.pdf").write_bytes(b"%PDF-1.4")
    (root / ".anyget-job1.part").write_bytes(b"half")
    (root / ".anyget-job2").mkdir()
    (root / ".anyget-job2" / "x.mp4").write_bytes(b"half")
    (root / "song.mp3.part").write_bytes(b"half")
    first = await services.library.scan()
    assert first == {"added": 1, "removed": 0, "total": 1}
    (root / "book.pdf").unlink()
    second = await services.library.scan()
    assert second["removed"] == 1 and services.library.count() == 0


async def test_tags_search_and_delete(services: Services) -> None:
    root = services.settings.downloads_dir
    root.mkdir(parents=True, exist_ok=True)
    (root / "Moon Landing.mp4").write_bytes(DATA)
    (root / "notes.txt").write_bytes(b"hello")
    await services.library.scan()
    video = services.library.search(q="moon").items[0]
    services.library.update(video.id, tags=["space", " nasa ", "space", ""])
    page = services.library.search(tag="space")
    assert [i.id for i in page.items] == [video.id] and page.tags == ["nasa", "space"]
    assert services.library.search(kind="text").total == 1
    assert services.library.delete(video.id, delete_file=True)
    assert not (root / "Moon Landing.mp4").exists()


# ----- API -------------------------------------------------------------------------


@pytest.fixture
def client(env_settings: Path) -> Any:
    with TestClient(create_app()) as test_client:
        yield test_client


def test_library_api_previews_and_ranges(client: TestClient, env_settings: Path) -> None:
    root = env_settings / "downloads"
    root.mkdir(parents=True, exist_ok=True)
    (root / "clip.mp4").write_bytes(bytes(range(256)) * 40)
    make_epub(root / "story.epub", ["Once upon a time."])
    (root / "page.html").write_text("<script>alert(1)</script>")
    assert client.post("/api/library/scan").json()["added"] == 3
    items = {i["kind"]: i for i in client.get("/api/library").json()["items"]}
    video = items["video"]
    ranged = client.get(f"/api/library/{video['id']}/file", headers={"Range": "bytes=100-199"})
    assert ranged.status_code == 206 and len(ranged.content) == 100
    assert ranged.headers["content-disposition"].startswith("inline")
    html = client.get(f"/api/library/{items['text']['id']}/file")
    assert html.headers["content-security-policy"] == "sandbox"
    preview = client.get(f"/api/library/{items['epub']['id']}/preview").json()
    assert "Once upon a time" in preview["text"]
    assert client.get(f"/api/library/{video['id']}/preview").status_code == 422
    patched = client.patch(f"/api/library/{video['id']}", json={"tags": ["fun"]}).json()
    assert patched["tags"] == ["fun"]
    assert client.post(f"/api/library/{video['id']}/redownload").status_code == 422  # no source
    assert client.delete(f"/api/library/{video['id']}").status_code == 204
    assert client.get(f"/api/library/{video['id']}").status_code == 404


def test_settings_are_saved_and_validated(
    client: TestClient, env_settings: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = client.get("/api/settings").json()
    assert view["folder_template"] == "" and "secrets" not in view  # keys: Connections
    saved = client.put(
        "/api/settings",
        json={
            "folder_template": "{type}/{source}",
            "max_concurrent_downloads": 2,
            "rate_limit_kbps": 500,
            "proxy": "http://127.0.0.1:3128",
        },
    ).json()
    assert saved["folder_template"] == "{type}/{source}" and saved["max_concurrent_downloads"] == 2
    assert saved["restart_needed"] == ["proxy"]
    bad = client.put("/api/settings", json={"folder_template": "{oops}"})
    assert bad.status_code == 422
    assert client.put("/api/settings", json={"proxy": "ftp://x"}).status_code == 422
    # Saved settings survive a restart and win over the environment.
    from anyget.core.settings import get_settings

    get_settings.cache_clear()
    with TestClient(create_app()) as again:
        view = again.get("/api/settings").json()
        assert view["rate_limit_kbps"] == 500


@respx.mock
def test_ytdlp_version_check(client: TestClient, respx_mock: respx.MockRouter) -> None:
    respx_mock.route(host="testserver").pass_through()
    respx_mock.get("https://pypi.org/pypi/yt-dlp/json").mock(
        return_value=httpx.Response(200, json={"info": {"version": "2099.1.1"}})
    )
    body = client.get("/api/settings/ytdlp").json()
    assert body["latest"] == "2099.1.1" and body["update_available"] is True


# ----- folder template in the queue ------------------------------------------------


@respx.mock
async def test_template_puts_new_downloads_in_folders(services: Services) -> None:
    services.settings.folder_template = "{type}/{source}"
    url = "https://files.test/report.pdf"
    respx.head(url).mock(
        return_value=httpx.Response(
            200, headers={"Content-Length": str(len(DATA)), "Content-Type": "application/pdf"}
        )
    )
    respx.get(url).mock(return_value=httpx.Response(200, content=DATA))
    await services.start(watch=False)
    job = services.queue.submit(url)
    await services.queue.wait_idle()
    await services.queue.wait_hooks()
    done = services.store.get(job.id)
    assert done is not None and done.state == JobState.done
    assert done.rel_path == "files/files.test/report.pdf"
    assert services.library.search(q="report").items[0].rel_path == done.rel_path


# ----- watches ---------------------------------------------------------------------


class FakeMedia:
    """A yt-dlp stand-in: a channel whose entries we control."""

    name = "fake_media"

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def can_handle(self, url: str) -> bool:
        return "channel.test" in url

    async def probe(self, url: str, options: dict[str, Any] | None = None) -> Probe:
        if "/watch" in url:
            return Probe(url=url, handler=self.name, title="one video", extra={"kind": "video"})
        return Probe(
            url=url,
            handler=self.name,
            title="Test channel",
            extra={"kind": "channel", "archive": "fake-chan", "entries": self.entries},
        )

    async def download(self, *_: Any) -> Any:  # never reached: jobs are not started here
        raise AssertionError


def entry(n: int, saved: bool = False) -> dict[str, Any]:
    return {
        "index": n,
        "id": f"v{n}",
        "url": f"https://channel.test/watch?v={n}",
        "archive_id": f"fake v{n}",
        "saved": saved,
        "live": False,
    }


async def test_watch_queues_only_new_items(services: Services) -> None:
    fake = FakeMedia()
    services.registry.register(fake, 1)
    fake.entries = [entry(n) for n in (9, 8, 7, 6, 5, 4, 3)]  # newest first
    watch = await services.watches.create(
        WatchIn(url="https://channel.test/@c", interval_minutes=60, initial=2)
    )
    assert watch.kind == "media" and watch.title == "Test channel"
    first = await services.watches.run(watch.id)
    queued = [services.store.get(j).url for j in first.job_ids]  # type: ignore[union-attr]
    assert queued == ["https://channel.test/watch?v=9", "https://channel.test/watch?v=8"]
    assert first.watch.seen == 7  # the older five are history, not news

    again = await services.watches.run(watch.id)
    assert again.queued == 0  # nothing new: nothing queued

    fake.entries = [entry(11), entry(10, saved=True), *fake.entries]
    third = await services.watches.run(watch.id)
    assert third.queued == 1  # v10 is already in the download archive
    assert services.store.get(third.job_ids[0]).url.endswith("v=11")  # type: ignore[union-attr]

    with pytest.raises(HandlerError):
        await services.watches.create(WatchIn(url="https://channel.test/watch?v=1"))


@respx.mock
async def test_archive_collection_watch(services: Services) -> None:
    respx.get("https://archive.org/metadata/oldtimeradio").mock(
        return_value=httpx.Response(
            200,
            json={
                "metadata": {
                    "identifier": "oldtimeradio",
                    "title": "OTR",
                    "mediatype": "collection",
                },
                "files": [],
            },
        )
    )

    def items(*ids: str) -> httpx.Response:
        return httpx.Response(
            200, json={"items": [{"identifier": i, "title": i} for i in ids], "total": len(ids)}
        )

    scrape = respx.get(url__startswith="https://archive.org/services/search/v1/scrape")
    scrape.mock(return_value=items("show3", "show2", "show1"))
    watch = await services.watches.create(
        WatchIn(url="https://archive.org/details/oldtimeradio", initial=1)
    )
    assert watch.kind == "archive_collection"
    first = await services.watches.run(watch.id)
    assert first.queued == 1 and "sorts=publicdate" in str(scrape.calls[0].request.url)
    scrape.mock(return_value=items("show4", "show3", "show2", "show1"))
    second = await services.watches.run(watch.id)
    assert second.queued == 1
    assert services.store.get(second.job_ids[0]).url.endswith("/show4")  # type: ignore[union-attr]


async def test_scheduler_runs_due_watches(services: Services) -> None:
    fake = FakeMedia()
    services.registry.register(fake, 1)
    fake.entries = [entry(1)]
    watch = await services.watches.create(
        WatchIn(url="https://channel.test/@c", interval_minutes=60)
    )
    assert await services.scheduler.tick() == 1  # never run: due now
    assert await services.scheduler.tick() == 0  # just ran
    later = datetime.now(UTC) + timedelta(minutes=61)
    assert [w.id for w in services.watches.due(later)] == [watch.id]
    services.watches.update(watch.id, enabled=False)
    assert services.watches.due(later) == []


def test_watch_api(client: TestClient) -> None:
    assert client.get("/api/watches").json() == []
    bad = client.post("/api/watches", json={"url": "https://example.org", "interval_minutes": 5})
    assert bad.status_code == 422  # interval below an hour
    assert client.post("/api/watches/nope/run").status_code == 404


# ----- CLI helpers -----------------------------------------------------------------


def test_links_in_copied_text() -> None:
    text = "see (https://a.test/x.pdf), and https://b.test/y?z=1. Also https://a.test/x.pdf"
    assert links_in(text) == ["https://a.test/x.pdf", "https://b.test/y?z=1"]
    assert links_in("no links here") == []


async def test_hooks_never_block_shutdown(services: Services) -> None:
    async def slow(_job: Any) -> None:
        await asyncio.sleep(10)

    services.queue.on_done.append(slow)
    task = asyncio.create_task(services.queue._after_done(services.store.create("https://x.test")))
    services.queue._hook_tasks.add(task)
    await services.queue.wait_hooks(time_limit=0.05)
    await asyncio.sleep(0)
    assert task.cancelled() or task.done()
