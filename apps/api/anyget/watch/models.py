"""Watch table (created with the other tables by Database.create_all)."""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import JSON, Column
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel

WatchKind = Literal["media", "archive_collection"]
MIN_INTERVAL = 60  # minutes


def _now() -> datetime:
    return datetime.now(UTC)


class Watch(SQLModel, table=True):
    __tablename__ = "watch"

    id: str = SQLField(default_factory=lambda: uuid4().hex, primary_key=True)
    url: str
    kind: str
    title: str
    interval_minutes: int = 360
    enabled: bool = True
    # Job options for every queued item (e.g. {"preset": "audio"}).
    options: dict[str, Any] = SQLField(default_factory=dict, sa_column=Column(JSON))
    # Items already queued or saved, so each run queues only new ones.
    seen_ids: list[str] = SQLField(default_factory=list, sa_column=Column(JSON))
    # How many items the first run queues; older ones are marked seen.
    initial: int = 5
    last_run: datetime | None = None
    last_new: int | None = None
    last_error: str | None = None
    created_at: datetime = SQLField(default_factory=_now)


class WatchIn(BaseModel):
    url: str = Field(min_length=4, max_length=2000)
    interval_minutes: int = Field(default=360, ge=MIN_INTERVAL, le=60 * 24 * 30)
    initial: int = Field(default=5, ge=0, le=50)
    options: dict[str, Any] = Field(default_factory=dict)


class WatchPatch(BaseModel):
    interval_minutes: int | None = Field(default=None, ge=MIN_INTERVAL, le=60 * 24 * 30)
    enabled: bool | None = None


class WatchOut(BaseModel):
    id: str
    url: str
    kind: WatchKind
    title: str
    interval_minutes: int
    enabled: bool
    initial: int
    seen: int
    last_run: datetime | None
    last_new: int | None
    last_error: str | None
    next_run: datetime | None
    created_at: datetime


class WatchRunResult(BaseModel):
    watch: WatchOut
    queued: int
    job_ids: list[str]
