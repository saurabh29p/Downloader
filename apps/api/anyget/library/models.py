"""Library tables (created with the job tables by Database.create_all)."""

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

Kind = Literal["video", "audio", "image", "pdf", "epub", "text", "archive", "other"]
Licence = Literal["public_domain", "cc", "rights_reserved", "streaming_only", "unknown"]
LICENCES: tuple[Licence, ...] = (
    "public_domain",
    "cc",
    "rights_reserved",
    "streaming_only",
    "unknown",
)


def _now() -> datetime:
    return datetime.now(UTC)


class LibraryItem(SQLModel, table=True):
    __tablename__ = "library_item"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    rel_path: str = Field(index=True, unique=True)
    kind: str = Field(index=True)
    size: int = 0
    sha256: str | None = Field(default=None, index=True)
    title: str
    source_url: str | None = None
    source_id: str | None = Field(default=None, index=True)
    job_id: str | None = Field(default=None, index=True)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    duplicate_of: str | None = None
    added_at: datetime = Field(default_factory=_now)
    user_id: str | None = Field(default=None, index=True)
    # Where it came from in AnyGet (a section id) and its licence, when known.
    section: str | None = Field(default=None, index=True)
    licence: str | None = None
    # Set when retention cleanup removed the file (the entry stays for Download again).
    expired_at: datetime | None = None


class LibraryItemOut(BaseModel):
    id: str
    rel_path: str
    kind: Kind
    size: int
    sha256: str | None
    title: str
    source_url: str | None
    source_id: str | None
    job_id: str | None
    tags: list[str]
    duplicate_of: str | None
    added_at: datetime
    missing: bool = False
    # The file was removed by retention cleanup (it was older than the retention days).
    expired: bool = False
    # A small picture for the Library grid (made on first request), or None.
    thumbnail: str | None = None
    section: str | None = None
    licence: Licence = "unknown"
    # The source site's host (archive.org, youtube.com…), from source_url.
    source: str | None = None
    # Text around a full-text match (OCR, PDF text, EPUB, text files).
    snippet: str | None = None


class LibraryPage(BaseModel):
    total: int
    items: list[LibraryItemOut]
    tags: list[str]
    # What the filters can offer (over all of the user's items).
    sections: list[str] = []
    sources: list[str] = []
    licences: list[Licence] = []
