"""The library index: one row per file in the downloads folder.

Files are added when a job finishes (main file plus extra files) and by a scan of
the folder (for files copied in by hand). Duplicates — same sha256 or same source
id — are linked to the first copy (`duplicate_of`) and never deleted for you.
"""

import asyncio
import contextlib
import hashlib
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sqlmodel import col, func, or_, select

from anyget.core.db import Database
from anyget.core.filenames import UnsafePathError, ensure_inside
from anyget.core.jobs import Job
from anyget.core.users import OWNER_ID
from anyget.library.fulltext import FullText
from anyget.library.kinds import kind_of
from anyget.library.models import LICENCES, LibraryItem, LibraryItemOut, LibraryPage, Licence
from anyget.library.thumbs import KINDS as THUMB_KINDS
from anyget.library.thumbs import PILLOW_SUFFIXES

SKIP_PREFIXES = (".anyget-", ".")
SKIP_SUFFIXES = (".part", ".tmp", ".ytdl")
HASH_CHUNK = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(HASH_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _source_id(job: Job) -> str | None:
    options = job.options or {}
    archive_id = options.get("archive_id")
    if isinstance(archive_id, str) and archive_id:
        return archive_id
    return f"url:{job.url}"


# A section for files saved before sections existed (or added by a folder scan).
SECTION_BY_KIND = {
    "video": "video",
    "audio": "music",
    "pdf": "books",
    "epub": "books",
    "image": "photos",
}


def section_of(item: LibraryItem) -> str | None:
    return item.section or SECTION_BY_KIND.get(item.kind)


def source_of(item: LibraryItem) -> str | None:
    if not item.source_url:
        return None
    host = urlsplit(item.source_url).hostname or ""
    return host.removeprefix("www.") or None


def licence_of(item: LibraryItem) -> Licence:
    return next((lic for lic in LICENCES if lic == item.licence), "unknown")


def _job_meta(job: Job) -> tuple[str | None, str | None]:
    """The section and licence a search result sent with the download, if valid."""
    from anyget.universal.sections import BY_ID

    options = job.options or {}
    section = options.get("section")
    licence = options.get("licence")
    return (
        section if isinstance(section, str) and section in BY_ID else None,
        licence if isinstance(licence, str) and licence in LICENCES else None,
    )


def thumbnail_url(item: LibraryItem) -> str | None:
    if item.kind == "image" and item.rel_path.lower().endswith(".svg"):
        return f"/api/library/{item.id}/file"  # the browser draws SVG itself
    if item.kind not in THUMB_KINDS:
        return None
    if item.kind == "image" and not item.rel_path.lower().endswith(PILLOW_SUFFIXES):
        return None
    return f"/api/library/{item.id}/thumb"


class LibraryIndex:
    def __init__(self, db: Database, downloads_dir: Path) -> None:
        self.db = db
        self.root = downloads_dir
        self.text = FullText(db.engine)

    # ----- paths -----------------------------------------------------------

    def path_of(self, item: LibraryItem) -> Path:
        return ensure_inside(self.root, self.root / item.rel_path)

    def _rel(self, path: Path) -> str | None:
        try:
            resolved = ensure_inside(self.root, path)
        except UnsafePathError:
            return None
        return resolved.relative_to(self.root.resolve()).as_posix()

    # ----- adding ----------------------------------------------------------

    def _add(
        self,
        path: Path,
        *,
        title: str | None = None,
        source_url: str | None = None,
        source_id: str | None = None,
        job_id: str | None = None,
        user_id: str = OWNER_ID,
        tags: list[str] | None = None,
        section: str | None = None,
        licence: str | None = None,
    ) -> LibraryItem | None:
        rel = self._rel(path)
        if rel is None or not path.is_file():
            return None
        digest = sha256_file(path)
        with self.db.session() as session:
            existing = session.exec(select(LibraryItem).where(LibraryItem.rel_path == rel)).first()
            item = existing or LibraryItem(rel_path=rel, kind=kind_of(rel), title=path.stem)
            item.size = path.stat().st_size
            item.sha256 = digest
            item.title = title or item.title
            item.source_url = source_url or item.source_url
            item.source_id = source_id or item.source_id
            item.job_id = job_id or item.job_id
            item.duplicate_of = None
            item.user_id = item.user_id or user_id
            item.expired_at = None
            item.section = section or item.section
            item.licence = licence or item.licence
            if tags:
                item.tags = sorted({*(item.tags or []), *tags})
            candidates = session.exec(
                select(LibraryItem)
                .where(LibraryItem.rel_path != rel)
                .where(LibraryItem.user_id == item.user_id)
                .where(col(LibraryItem.duplicate_of).is_(None))
                .where(
                    or_(LibraryItem.sha256 == digest, LibraryItem.source_id == item.source_id)
                    if item.source_id
                    else LibraryItem.sha256 == digest
                )
                .order_by(col(LibraryItem.added_at))
            ).all()
            for original in candidates:
                # The same bytes, or the same source saved again by another job.
                if original.sha256 == digest or original.job_id != item.job_id:
                    item.duplicate_of = original.id
                    break
            session.add(item)
            session.commit()
            session.refresh(item)
        self.text.put(item.id, path)
        return item

    def add_job_sync(self, job: Job) -> list[LibraryItem]:
        if not job.rel_path:
            return []
        added = []
        source_id = _source_id(job)
        section, licence = _job_meta(job)
        raw = (job.options or {}).get("tags")
        tags = (
            [str(t).strip()[:40] for t in raw if str(t).strip()][:10]
            if isinstance(raw, list)
            else []
        )
        for index, rel in enumerate([job.rel_path, *(job.files or [])]):
            item = self._add(
                self.root / rel,
                title=job.title if index == 0 else None,
                source_url=job.url if not job.url.startswith("anyget:") else None,
                source_id=source_id if index == 0 else None,
                job_id=job.id,
                user_id=job.user_id or OWNER_ID,
                tags=tags,
                section=section,
                licence=licence,
            )
            if item is not None:
                added.append(item)
        return added

    async def add_job(self, job: Job) -> list[LibraryItem]:
        return await asyncio.to_thread(self.add_job_sync, job)

    def _walk(self) -> Iterable[Path]:
        for folder, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if not d.startswith(SKIP_PREFIXES)]
            for name in files:
                if name.startswith(SKIP_PREFIXES) or name.endswith(SKIP_SUFFIXES):
                    continue
                yield Path(folder) / name

    def scan_sync(self) -> dict[str, int]:
        """Add files that are not indexed yet; forget rows whose file is gone."""
        with self.db.session() as session:
            known = {row.rel_path: row for row in session.exec(select(LibraryItem)).all()}
        added = 0
        seen: set[str] = set()
        has_text = self.text.known()
        for path in self._walk():
            rel = self._rel(path)
            if rel is None:
                continue
            seen.add(rel)
            row = known.get(rel)
            changed = row is None or row.size != path.stat().st_size
            if changed and self._add(path) is not None and row is None:
                added += 1
            elif not changed and row is not None and row.id not in has_text:
                self.text.put(row.id, path)  # indexed before full-text search existed
        removed = 0
        with self.db.session() as session:
            for rel, row in known.items():
                if rel not in seen:
                    stale = session.get(LibraryItem, row.id)
                    if stale is not None:
                        session.delete(stale)
                        self.text.drop(row.id)
                        removed += 1
            session.commit()
        return {"added": added, "removed": removed, "total": len(seen)}

    async def scan(self) -> dict[str, int]:
        return await asyncio.to_thread(self.scan_sync)

    # ----- reading ---------------------------------------------------------

    def out(self, item: LibraryItem, snippet: str | None = None) -> LibraryItemOut:
        try:
            missing = not self.path_of(item).is_file()
        except UnsafePathError:
            missing = True
        data = item.model_dump(exclude={"section", "licence", "expired_at"})
        expired = item.expired_at is not None
        return LibraryItemOut(
            **data,
            missing=missing or expired,
            expired=expired,
            thumbnail=None if expired else thumbnail_url(item),
            section=section_of(item),
            licence=licence_of(item),
            source=source_of(item),
            snippet=snippet or None,
        )

    def find(self, rel_path: str) -> LibraryItem | None:
        with self.db.session() as session:
            return session.exec(select(LibraryItem).where(LibraryItem.rel_path == rel_path)).first()

    def get(self, item_id: str) -> LibraryItem | None:
        with self.db.session() as session:
            return session.get(LibraryItem, item_id)

    def search(
        self,
        q: str | None = None,
        kind: str | None = None,
        tag: str | None = None,
        duplicates: bool | None = None,
        offset: int = 0,
        limit: int = 60,
        user_id: str | None = None,
        section: str | None = None,
        source: str | None = None,
        licence: str | None = None,
    ) -> LibraryPage:
        """Title/path matches plus full-text matches; filters by kind, tag (collection),
        section, source host and licence."""
        snippets = self.text.search(q) if q and q.strip() else {}
        with self.db.session() as session:
            query = select(LibraryItem)
            if user_id is not None:
                query = query.where(LibraryItem.user_id == user_id)
            mine = list(session.exec(query).all())
            if q and q.strip():
                like = f"%{q.strip()}%"
                matches = [
                    col(LibraryItem.title).ilike(like),
                    col(LibraryItem.rel_path).ilike(like),
                ]
                if snippets:
                    matches.append(col(LibraryItem.id).in_(list(snippets)))
                query = query.where(or_(*matches))
            if kind:
                query = query.where(LibraryItem.kind == kind)
            if duplicates is True:
                query = query.where(col(LibraryItem.duplicate_of).is_not(None))
            rows = list(session.exec(query.order_by(col(LibraryItem.added_at).desc())).all())
        # JSON column and derived fields: filter in Python (thousands of rows, not millions).
        if tag:
            rows = [r for r in rows if tag in (r.tags or [])]
        if section:
            rows = [r for r in rows if section_of(r) == section]
        if source:
            rows = [r for r in rows if source_of(r) == source]
        if licence:
            rows = [r for r in rows if licence_of(r) == licence]
        return LibraryPage(
            total=len(rows),
            items=[self.out(r, snippets.get(r.id)) for r in rows[offset : offset + limit]],
            tags=sorted({t for r in mine for t in r.tags or []}),
            sections=sorted({s for r in mine if (s := section_of(r))}),
            sources=sorted({s for r in mine if (s := source_of(r))}),
            licences=sorted({licence_of(r) for r in mine}),
        )

    def count(self) -> int:
        with self.db.session() as session:
            return int(session.exec(select(func.count()).select_from(LibraryItem)).one())

    # ----- changing --------------------------------------------------------

    def update(self, item_id: str, **changes: Any) -> LibraryItem | None:
        with self.db.session() as session:
            item = session.get(LibraryItem, item_id)
            if item is None:
                return None
            if "tags" in changes and changes["tags"] is not None:
                clean = [str(t).strip()[:40] for t in changes["tags"] if str(t).strip()]
                item.tags = sorted(set(clean))[:30]
            if changes.get("title"):
                item.title = str(changes["title"]).strip()[:300]
            session.add(item)
            session.commit()
            session.refresh(item)
            return item

    def delete(self, item_id: str, delete_file: bool = False) -> bool:
        with self.db.session() as session:
            item = session.get(LibraryItem, item_id)
            if item is None:
                return False
            if delete_file:
                with contextlib.suppress(UnsafePathError):
                    self.path_of(item).unlink(missing_ok=True)
            for copy in session.exec(
                select(LibraryItem).where(LibraryItem.duplicate_of == item.id)
            ).all():
                copy.duplicate_of = None
                session.add(copy)
            session.delete(item)
            session.commit()
        self.text.drop(item_id)
        return True
