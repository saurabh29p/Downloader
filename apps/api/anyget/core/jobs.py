"""Download jobs: the SQLite table and small helpers to read and change it."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel, col, select

from anyget.core.db import Database


class JobState(StrEnum):
    queued = "queued"
    probing = "probing"
    downloading = "downloading"
    paused = "paused"
    done = "done"
    failed = "failed"
    canceled = "canceled"


ACTIVE_STATES = {JobState.queued, JobState.probing, JobState.downloading}
FINISHED_STATES = {JobState.done, JobState.failed, JobState.canceled}


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid.uuid4().hex


class Job(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    url: str
    handler: str | None = None
    state: JobState = Field(default=JobState.queued, index=True)
    title: str | None = None
    filename: str | None = None
    # Path of the finished file relative to the downloads folder.
    rel_path: str | None = None
    downloaded: int = 0
    total: int | None = None
    speed: float | None = None
    error: str | None = None
    error_code: str | None = None
    checksum_ok: bool | None = None
    # Short status detail, e.g. "merging", "already_downloaded" (a code the UI translates).
    note: str | None = None
    # Extra files next to the main one (subtitles, info.json), relative to downloads.
    files: list[str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    options: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now, index=True)
    updated_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None


class JobStore:
    """Thin repository over the jobs table."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, url: str, options: dict[str, Any] | None = None) -> Job:
        job = Job(url=url, options=options or {})
        with self.db.session() as session:
            session.add(job)
            session.commit()
            session.refresh(job)
        return job

    def get(self, job_id: str) -> Job | None:
        with self.db.session() as session:
            return session.get(Job, job_id)

    def list_jobs(self, states: set[JobState] | None = None, limit: int = 100) -> list[Job]:
        with self.db.session() as session:
            query = select(Job).order_by(col(Job.created_at).desc()).limit(limit)
            if states:
                query = query.where(col(Job.state).in_(states))
            return list(session.exec(query).all())

    def update(self, job_id: str, **changes: Any) -> Job | None:
        with self.db.session() as session:
            job = session.get(Job, job_id)
            if job is None:
                return None
            for key, value in changes.items():
                setattr(job, key, value)
            job.updated_at = _now()
            if changes.get("state") in FINISHED_STATES:
                job.finished_at = job.updated_at
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    def delete(self, job_id: str) -> bool:
        with self.db.session() as session:
            job = session.get(Job, job_id)
            if job is None:
                return False
            session.delete(job)
            session.commit()
            return True

    def find_resumable(self, url: str) -> Job | None:
        """Latest unfinished job for this URL (used by the CLI to resume)."""
        with self.db.session() as session:
            query = (
                select(Job)
                .where(Job.url == url)
                .where(col(Job.state).in_([JobState.paused, JobState.failed, JobState.queued]))
                .order_by(col(Job.created_at).desc())
            )
            return session.exec(query).first()

    def reset_interrupted(self) -> list[Job]:
        """After a restart, jobs that were running go back to the queue."""
        with self.db.session() as session:
            query = select(Job).where(col(Job.state).in_([JobState.probing, JobState.downloading]))
            jobs = list(session.exec(query).all())
            for job in jobs:
                job.state = JobState.queued
                job.speed = None
                job.updated_at = _now()
                session.add(job)
            session.commit()
            return jobs


class JobOut(BaseModel):
    """A job as the API and events show it."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    url: str
    handler: str | None
    state: JobState
    title: str | None
    filename: str | None
    rel_path: str | None
    downloaded: int
    total: int | None
    speed: float | None
    error: str | None
    error_code: str | None
    checksum_ok: bool | None
    note: str | None = None
    files: list[str] | None = None
    options: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None

    @field_validator("created_at", "updated_at", "finished_at", mode="after")
    @classmethod
    def _as_utc(cls, value: datetime | None) -> datetime | None:
        """SQLite drops the timezone; every stored time is UTC."""
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
