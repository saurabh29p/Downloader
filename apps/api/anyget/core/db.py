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
        from anyget.connections import store as connection_models  # noqa: F401
        from anyget.core import jobs, settings_store  # noqa: F401  (register tables)
        from anyget.library import models  # noqa: F401
        from anyget.llm import store as llm_models  # noqa: F401
        from anyget.watch import models as watch_models  # noqa: F401

        SQLModel.metadata.create_all(self.engine)
        self._add_missing_columns()

    def _add_missing_columns(self) -> None:
        """Tiny additive migration: new nullable columns on existing tables."""
        with self.engine.begin() as conn:
            for table in SQLModel.metadata.sorted_tables:
                existing = {
                    row[1] for row in conn.exec_driver_sql(f'PRAGMA table_info("{table.name}")')
                }
                for column in table.columns:
                    if column.name in existing:
                        continue
                    if not column.nullable:  # pragma: no cover - only nullable additions
                        raise RuntimeError(f"cannot add NOT NULL column {table.name}.{column.name}")
                    col_type = column.type.compile(dialect=self.engine.dialect)
                    conn.exec_driver_sql(
                        f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'
                    )
                    if column.index:
                        conn.exec_driver_sql(
                            f'CREATE INDEX IF NOT EXISTS "ix_{table.name}_{column.name}" '
                            f'ON "{table.name}" ("{column.name}")'
                        )

    @contextmanager
    def session(self) -> Iterator[Session]:
        with Session(self.engine, expire_on_commit=False) as session:
            yield session

    def dispose(self) -> None:
        self.engine.dispose()
