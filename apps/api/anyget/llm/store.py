"""The LLM's cache (answers by request, 24 h) and its daily usage, in AnyGet's SQLite."""

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlmodel import Field, SQLModel, select

from anyget.core.db import Database

CACHE_HOURS = 24


def _now() -> datetime:
    return datetime.now(UTC)


class LlmCache(SQLModel, table=True):
    __tablename__ = "llm_cache"

    key: str = Field(primary_key=True)  # sha256 of kind + request
    kind: str = Field(index=True)
    value: str  # JSON
    expires_at: datetime


class LlmUsage(SQLModel, table=True):
    __tablename__ = "llm_usage"

    day: str = Field(primary_key=True)  # YYYY-MM-DD (UTC)
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0


def cache_key(kind: str, request: Any) -> str:
    raw = json.dumps([kind, request], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


class LlmStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def cached(self, kind: str, request: Any) -> Any | None:
        with self.db.session() as session:
            row = session.get(LlmCache, cache_key(kind, request))
        if row is None:
            return None
        expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
        if expires < _now():
            return None
        return json.loads(row.value)

    def remember(self, kind: str, request: Any, value: Any, hours: int = CACHE_HOURS) -> None:
        with self.db.session() as session:
            key = cache_key(kind, request)
            row = session.get(LlmCache, key) or LlmCache(
                key=key, kind=kind, value="", expires_at=_now()
            )
            row.value = json.dumps(value, ensure_ascii=False)
            row.expires_at = _now() + timedelta(hours=hours)
            session.add(row)
            session.commit()

    def today(self) -> LlmUsage:
        day = date.today().isoformat()
        with self.db.session() as session:
            return session.get(LlmUsage, day) or LlmUsage(day=day)

    def record(self, prompt_tokens: int, completion_tokens: int, cost_usd: float) -> None:
        day = date.today().isoformat()
        with self.db.session() as session:
            row = session.get(LlmUsage, day) or LlmUsage(day=day)
            row.calls += 1
            row.prompt_tokens += prompt_tokens
            row.completion_tokens += completion_tokens
            row.cost_usd += cost_usd
            session.add(row)
            session.commit()

    def history(self, days: int = 7) -> list[LlmUsage]:
        with self.db.session() as session:
            rows = session.exec(select(LlmUsage).order_by(LlmUsage.day.desc()).limit(days))  # type: ignore[attr-defined]
            return list(rows)
