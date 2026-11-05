"""What universal search plans and returns (shared by the keyword and, later, LLM router)."""

from typing import Literal

from pydantic import BaseModel, Field

Kind = Literal["url", "search", "question"]
Intent = Literal["download", "find", "watch", "read", "listen", "explore"]
Media = Literal[
    "movie",
    "book",
    "music",
    "video",
    "declassified",
    "map",
    "newspaper",
    "photo",
    "manuscript",
    "other",
]
Licence = Literal["public_domain", "cc", "rights_reserved", "streaming_only", "unknown"]
SourceName = Literal["archive", "books", "videos", "libraries"]


class QuerySpec(BaseModel):
    source: SourceName
    q: str = Field(min_length=1, max_length=300)
    filters: dict[str, str] = Field(default_factory=dict)


class RouterPlan(BaseModel):
    """The router's JSON (v2 prompt schema): what was asked and which searches to run."""

    kind: Kind
    intent: Intent = "find"
    media: list[Media] = Field(default_factory=list)  # empty: any
    language: str = "en"
    queries: list[QuerySpec] = Field(default_factory=list)
    answer_needed: bool = False
    # Links found in the text (kind "url"): the web probes them as before.
    urls: list[str] = Field(default_factory=list)
    # "keyword" today; "llm" once the optional AI router (Phase 5) answers.
    router: Literal["keyword", "llm"] = "keyword"


class ResultCard(BaseModel):
    id: str  # "<source>:<id>"
    source: SourceName
    source_label: str
    title: str
    url: str  # the item's page at its source ("Open source")
    download: str | None = None  # a link AnyGet can download, when one is legal
    media: Media
    licence: Licence = "unknown"
    year: str | None = None
    creator: str | None = None
    formats: list[str] = Field(default_factory=list)
    thumbnail: str | None = None
    # Higher is more relevant to the query (comparable across sources).
    score: float = 0.0


class SourceDone(BaseModel):
    source: SourceName
    status: Literal["ok", "timeout", "error"]
    message: str | None = None
    results: list[ResultCard] = Field(default_factory=list)


class UniversalDone(BaseModel):
    total: int
    counts: dict[str, int]  # media → number of cards
