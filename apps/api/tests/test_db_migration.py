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


def test_adds_new_indexes_to_an_old_database(settings: Settings) -> None:
    db = Database(settings)
    db.create_all()
    path = settings.data_dir / "anyget.db"
    with sqlite3.connect(path) as conn:  # a database from before the composite indexes
        conn.execute("DROP INDEX ix_job_user_created")
        conn.execute("DROP INDEX ix_library_item_user_added")
    db.create_all()
    with sqlite3.connect(path) as conn:
        indexes = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        names = {row[0] for row in indexes}
        query = "SELECT * FROM job WHERE user_id = 'owner' ORDER BY created_at DESC"
        plan = " ".join(str(row[3]) for row in conn.execute(f"EXPLAIN QUERY PLAN {query}"))
    assert {"ix_job_user_created", "ix_library_item_user_added"} <= names
    assert "ix_job_user_created" in plan  # the Downloads list uses it (no sort step)
