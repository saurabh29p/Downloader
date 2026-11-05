"""Shared types for book and library sources.

Every source is one adapter module with a module-level `ADAPTER`. Adapters only
read public APIs through `Net`; anything that is not openly downloadable is
returned with an access state that says so, never worked around.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal
from urllib.parse import quote_plus

from pydantic import BaseModel, Field

from anyget.core.net import Net
from anyget.core.settings import Settings

FormatKind = Literal["epub", "pdf_text", "pdf_scan", "images", "txt", "html"]
Region = Literal["global", "europe", "asia", "oceania", "middle_east_africa", "americas"]


class Access(StrEnum):
    full_view = "full_view"  # downloadable here
    view_online = "view_online"  # free to read on the site, no file to download
    borrow_only = "borrow_only"  # lending library: not downloadable
    in_copyright = "in_copyright"  # not legally downloadable


class BookFormat(BaseModel):
    kind: FormatKind
    url: str
    size: int | None = None
    label: str | None = None


class Link(BaseModel):
    label: str
    url: str


class BookHit(BaseModel):
    source: str
    source_label: str | None = None  # filled in by the search from the adapter
    id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: str | None = None
    language: str | None = None
    access: Access
    formats: list[BookFormat] = Field(default_factory=list)
    details_url: str
    thumbnail: str | None = None
    isbn: list[str] = Field(default_factory=list)
    # A chapter, a volume of a set or a single page, rather than the whole work.
    partial: bool = False
    library_links: list[Link] = Field(default_factory=list)
    buy_links: list[Link] = Field(default_factory=list)

    @property
    def downloadable(self) -> bool:
        return self.access == Access.full_view and bool(self.formats)


@dataclass(frozen=True)
class SearchContext:
    net: Net
    settings: Settings
    lang: str | None = None


SearchFn = Callable[[SearchContext, str, int], Awaitable[list[BookHit]]]


@dataclass(frozen=True)
class Adapter:
    name: str
    label: str
    region: Region
    search: SearchFn | None
    key_setting: str | None = None  # Settings field that must be set, e.g. "dpla_key"
    # For sources without an open search API: where to search by hand.
    search_url: str | None = None
    kinds: tuple[Literal["books", "libraries"], ...] = ("books",)
    trust: int = 5  # lower is better when two copies are otherwise equal

    def key(self, settings: Settings) -> str:
        return str(getattr(settings, self.key_setting, "")) if self.key_setting else ""

    def manual_url(self, query: str) -> str | None:
        return self.search_url.format(q=quote_plus(query)) if self.search_url else None


def find_links(hit: BookHit) -> BookHit:
    """Where to borrow or buy a book that is not legally downloadable."""
    if hit.downloadable or hit.access == Access.view_online:
        return hit
    terms = " ".join([hit.title, *hit.authors[:1]])
    library = [
        Link(label="WorldCat", url=f"https://search.worldcat.org/search?q={quote_plus(terms)}")
    ]
    if hit.isbn:
        library.insert(
            0, Link(label="Open Library", url=f"https://openlibrary.org/isbn/{hit.isbn[0]}")
        )
    keywords = quote_plus(hit.isbn[0] if hit.isbn else terms)
    buy = [Link(label="Bookshop", url=f"https://bookshop.org/search?keywords={keywords}")]
    return hit.model_copy(update={"library_links": library, "buy_links": buy})


def first(value: object) -> str | None:
    """First item of a list-or-string API field, as text."""
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        value = value.get("@value") or value.get("value") or next(iter(value.values()), None)
    return str(value).strip() if value not in (None, "") else None


def as_list(value: object) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    return [str(v).strip() for v in items if str(v).strip()]
