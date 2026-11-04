"""SQLite database (SQLModel) living in the data folder."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, event
from sqlmodel import Session, SQLModel, create_engine

from anyget.core.settings import Settings


def _enable_wal(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


class Database:
    def __init__(self, settings: Settings) -> None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(
            settings.database_url, connect_args={"check_same_thread": False}
        )
        event.listen(self.engine, "connect", _enable_wal)

    def create_all(self) -> None:
        from anyget.core import jobs  # noqa: F401  (register tables)

        SQLModel.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with Session(self.engine, expire_on_commit=False) as session:
            yield session

    def dispose(self) -> None:
        self.engine.dispose()
