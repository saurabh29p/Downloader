"""v2 ownership: every user sees only their own jobs, library and watches."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from anyget.core.db import Database
from anyget.core.jobs import JobStore
from anyget.core.ownership import adopt_rows
from anyget.core.settings import Settings, get_settings
from anyget.library.index import LibraryIndex
from anyget.main import create_app
from anyget.watch.models import Watch


@pytest.fixture
def client(env_settings: Path) -> Iterator[TestClient]:
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_someone_elses_rows_are_invisible(client: TestClient, env_settings: Path) -> None:
    services = client.app.state.services  # type: ignore[attr-defined]
    mine = services.store.create("https://example.org/a.pdf")
    theirs = services.store.create("https://example.org/b.pdf", user_id="someone-else")
    ids = [job["id"] for job in client.get("/api/jobs").json()]
    assert mine.id in ids and theirs.id not in ids
    assert client.get(f"/api/jobs/{theirs.id}").status_code == 404
    assert client.post(f"/api/jobs/{theirs.id}/retry").status_code == 404
    assert client.delete(f"/api/jobs/{theirs.id}").status_code == 404
    assert services.store.get(theirs.id) is not None

    root = env_settings / "downloads"
    root.mkdir(parents=True, exist_ok=True)
    (root / "theirs.txt").write_text("not yours")
    item = services.library._add(root / "theirs.txt", user_id="someone-else")
    assert client.get("/api/library").json()["total"] == 0
    assert client.get(f"/api/library/{item.id}").status_code == 404
    assert client.get(f"/api/library/{item.id}/file").status_code == 404

    with services.db.session() as session:
        watch = Watch(url="https://example.org/c", kind="media", title="c", user_id="else")
        session.add(watch)
        session.commit()
        session.refresh(watch)
    assert client.get("/api/watches").json() == []
    assert client.delete(f"/api/watches/{watch.id}").status_code == 404


def _legacy_db(tmp_path: Path, public: bool = False) -> tuple[Settings, Database]:
    settings = Settings(
        downloads_dir=tmp_path / "downloads", data_dir=tmp_path / "data", public=public
    )
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(settings)
    db.create_all()
    store = JobStore(db)
    job = store.create("https://example.org/old.pdf")
    root = settings.downloads_dir
    root.mkdir(parents=True, exist_ok=True)
    (root / "old.pdf").write_bytes(b"%PDF-1.4")
    LibraryIndex(db, root)._add(root / "old.pdf")
    with db.engine.begin() as conn:  # rows written before v2 had no owner
        conn.execute(text("UPDATE job SET user_id = NULL"))
        conn.execute(text("UPDATE library_item SET user_id = NULL"))
    assert job.id
    return settings, db


def test_hosted_start_clears_old_jobs_but_keeps_files(tmp_path: Path) -> None:
    settings, db = _legacy_db(tmp_path, public=True)
    counts = adopt_rows(db, settings)
    assert counts["jobs_cleared"] == 1 and counts["library"] == 1
    assert JobStore(db).list_jobs() == []
    assert (settings.downloads_dir / "old.pdf").is_file()
    page = LibraryIndex(db, settings.downloads_dir).search(user_id="owner")
    assert page.total == 1
    assert adopt_rows(db, settings) == {"library": 0, "watches": 0, "jobs_cleared": 0}


def test_local_start_keeps_old_jobs(tmp_path: Path) -> None:
    settings, db = _legacy_db(tmp_path)
    counts = adopt_rows(db, settings)
    assert counts["jobs"] == 1
    assert [j.user_id for j in JobStore(db).list_jobs(user_id="owner")] == ["owner"]


async def test_live_events_are_per_user() -> None:
    import asyncio

    from anyget.core.events import EventBus, sse_stream

    bus = EventBus()
    stream = sse_stream(bus, user_id="owner", heartbeat=5)
    assert await anext(stream) == ": connected\n\n"
    reader = asyncio.ensure_future(anext(stream))
    while bus.subscriber_count == 0:
        await asyncio.sleep(0.01)
    bus.publish({"type": "job.updated", "job": {"id": "x"}, "user": "someone-else"})
    bus.publish({"type": "job.updated", "job": {"id": "y"}, "user": "owner"})
    text = await asyncio.wait_for(reader, 2)
    assert '"id": "y"' in text and '"x"' not in text
    await stream.aclose()
