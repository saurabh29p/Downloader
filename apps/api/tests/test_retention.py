"""Retention cleanup: age boundaries, grace period, active jobs, keep tag, symlinks, off."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from anyget.core.jobs import JobState
from anyget.core.queue import InvalidStateError
from anyget.core.services import Services
from anyget.core.settings import Settings
from anyget.library.models import LibraryItem
from anyget.main import create_app

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


@pytest.fixture
async def services(settings: Settings) -> AsyncIterator[Services]:
    svc = Services.build(settings)
    yield svc
    await svc.stop()


def _add(services: Services, name: str, age_days: float, **extra: object) -> LibraryItem:
    root = services.settings.downloads_dir
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * 100)
    item = services.library._add(path)
    assert item is not None
    with services.db.session() as session:
        row = session.get(LibraryItem, item.id)
        assert row is not None
        row.added_at = NOW - timedelta(days=age_days)
        for key, value in extra.items():
            setattr(row, key, value)
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


def _start(services: Services, days_ago: float) -> None:
    services.settings_store.set_state(
        "retention_since", (NOW - timedelta(days=days_ago)).isoformat()
    )


def test_default_is_seven_days_and_first_run_only_starts_the_grace(services: Services) -> None:
    assert services.settings.retention_days == 7
    _add(services, "old.mp4", age_days=30)
    first = services.retention.run(now=NOW)
    assert first.removed == [] and first.starts_at == NOW + timedelta(days=7)
    assert (services.settings.downloads_dir / "old.mp4").exists()  # grace: nothing deleted
    later = services.retention.run(now=NOW + timedelta(days=7, minutes=1))
    assert later.removed == ["old.mp4"]


def test_age_boundary_keep_tag_and_expired_marking(services: Services) -> None:
    _start(services, days_ago=30)
    root = services.settings.downloads_dir
    old = _add(services, "old.pdf", age_days=7.01)
    _add(services, "edge.pdf", age_days=6.99)
    _add(services, "kept.pdf", age_days=40, tags=["keep", "books"])
    preview = services.retention.run(now=NOW, dry_run=True)
    assert preview.removed == ["old.pdf"] and preview.skipped_kept == 1
    assert (root / "old.pdf").exists()  # dry run deletes nothing

    result = services.retention.run(now=NOW)
    assert result.removed == ["old.pdf"] and result.freed_bytes == 100
    assert not (root / "old.pdf").exists()
    assert (root / "edge.pdf").exists() and (root / "kept.pdf").exists()
    out = services.library.out(services.library.get(old.id))  # type: ignore[arg-type]
    assert out.expired and out.missing and out.thumbnail is None  # the entry stays
    assert services.retention.run(now=NOW).removed == []  # not counted twice


def test_active_jobs_are_never_touched(services: Services) -> None:
    _start(services, days_ago=30)
    job = services.store.create("https://files.test/big.iso")
    services.store.update(job.id, state=JobState.downloading, options={"_folder": "isos"})
    _add(services, "isos/part1.iso", age_days=20)
    _add(services, "busy.bin", age_days=20, job_id=job.id)
    done = services.store.create("https://files.test/done.zip")
    services.store.update(done.id, state=JobState.done, rel_path="done.zip")
    _add(services, "done.zip", age_days=20, job_id=done.id)
    result = services.retention.run(now=NOW)
    assert result.removed == ["done.zip"] and result.skipped_active == 2
    assert services.store.get(done.id).note == "expired"  # type: ignore[union-attr]


def test_symlinks_and_files_outside_are_never_deleted(services: Services, tmp_path: Path) -> None:
    _start(services, days_ago=30)
    root = services.settings.downloads_dir
    outside = tmp_path / "precious"
    outside.mkdir()
    (outside / "family.jpg").write_bytes(b"photo")
    (root / "linked").symlink_to(outside, target_is_directory=True)
    (root / "alias.jpg").symlink_to(outside / "family.jpg")
    for name in ("linked/family.jpg", "alias.jpg"):
        with services.db.session() as session:
            session.add(
                LibraryItem(
                    rel_path=name, kind="image", title=name, added_at=NOW - timedelta(days=30)
                )
            )
            session.commit()
    result = services.retention.run(now=NOW)
    assert result.removed == [] and result.skipped_unsafe == 2
    assert (outside / "family.jpg").read_bytes() == b"photo"


def test_unindexed_files_and_the_database_are_never_candidates(services: Services) -> None:
    _start(services, days_ago=30)
    root = services.settings.downloads_dir
    (root / "hand-copied.txt").write_text("not in the library")
    result = services.retention.run(now=NOW)
    assert result.removed == [] and (root / "hand-copied.txt").exists()
    assert (services.settings.data_dir / "anyget.db").exists()


def test_off_mode_and_overlapping_folders(services: Services, tmp_path: Path) -> None:
    _start(services, days_ago=30)
    _add(services, "old.mp3", age_days=90)
    services.settings.retention_days = 0
    off = services.retention.run(now=NOW)
    assert not off.enabled and off.removed == []
    assert services.settings_store.get_state("retention_since") is None  # grace restarts later
    services.settings.retention_days = 7
    services.settings.data_dir = services.settings.downloads_dir / "data"
    blocked = services.retention.run(now=NOW + timedelta(days=60))
    assert blocked.blocked == "folders_overlap" and blocked.removed == []
    assert (services.settings.downloads_dir / "old.mp3").exists()


def test_retention_api(env_settings: Path) -> None:
    with TestClient(create_app()) as client:
        status = client.get("/api/retention").json()
        assert status["days"] == 7 and status["enabled"] is True and status["blocked"] is None
        dry = client.post("/api/retention/run").json()
        assert dry["dry_run"] is True
        saved = client.put("/api/settings", json={"retention_days": 0}).json()
        assert saved["retention_days"] == 0
        assert client.get("/api/retention").json()["enabled"] is False
        assert client.put("/api/settings", json={"retention_days": -1}).status_code == 422


async def test_retry_downloads_an_expired_file_again(services: Services) -> None:
    _start(services, days_ago=30)
    done = services.store.create("https://files.test/old.zip")
    services.store.update(done.id, state=JobState.done, rel_path="old.zip")
    _add(services, "old.zip", age_days=20, job_id=done.id)
    services.retention.run(now=NOW)
    again = services.queue.retry(done.id)
    assert again.state == JobState.queued and again.note is None
    other = services.store.create("https://files.test/fine.zip")
    services.store.update(other.id, state=JobState.done, rel_path="fine.zip")
    with pytest.raises(InvalidStateError):
        services.queue.retry(other.id)  # a normal finished download is not retried


def test_downloads_inside_the_data_volume_is_fine(services: Services, tmp_path: Path) -> None:
    # e.g. Railway with one volume: ANYGET_DATA_DIR=/data, ANYGET_DOWNLOADS_DIR=/data/downloads
    services.settings.data_dir = services.settings.downloads_dir.parent
    assert services.retention.status().blocked is None
    services.settings.data_dir = services.settings.downloads_dir
    assert services.retention.status().blocked == "folders_overlap"
