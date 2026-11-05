import sqlite3

from anyget.core.db import Database
from anyget.core.jobs import JobStore
from anyget.core.settings import Settings


def test_adds_new_columns_to_an_old_database(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True)
    path = settings.data_dir / "anyget.db"
    with sqlite3.connect(path) as conn:  # the Phase 2 jobs table, without note/files
        conn.execute(
            "CREATE TABLE job (id VARCHAR PRIMARY KEY, url VARCHAR NOT NULL, handler VARCHAR,"
            " state VARCHAR NOT NULL, title VARCHAR, filename VARCHAR, rel_path VARCHAR,"
            " downloaded INTEGER NOT NULL, total INTEGER, speed FLOAT, error VARCHAR,"
            " error_code VARCHAR, checksum_ok BOOLEAN, options JSON, created_at DATETIME NOT NULL,"
            " updated_at DATETIME NOT NULL, finished_at DATETIME)"
        )
        conn.execute(
            "INSERT INTO job VALUES ('old', 'https://x.test/a', NULL, 'done', NULL, NULL, NULL,"
            " 0, NULL, NULL, NULL, NULL, NULL, '{}', '2026-01-01', '2026-01-01', NULL)"
        )
    db = Database(settings)
    db.create_all()
    with sqlite3.connect(path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(job)")}
    assert {"note", "files"} <= columns
    store = JobStore(db)
    job = store.update("old", note="already_downloaded", files=["a.srt"])
    assert job is not None and job.note == "already_downloaded" and job.files == ["a.srt"]
    db.create_all()  # running again is a no-op
