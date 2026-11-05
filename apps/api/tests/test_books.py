"""Book sources (one fixture per API), the ranker, the fan-out search and books links."""

import asyncio
import json
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from anyget.books import search as search_mod
from anyget.books.base import Access, Adapter, BookFormat, BookHit, SearchContext, find_links
from anyget.books.hathitrust import identifier
from anyget.books.ranker import rank, relevance
from anyget.books.search import search_books
from anyget.books.sources import ADAPTERS, BY_NAME
from anyget.books.standard_ebooks import epub_url
from anyget.core.net import Net
from anyget.core.settings import Settings
from anyget.handlers.archive_org import ArchiveOrgHandler
from anyget.handlers.base import HandlerError, JobContext
from anyget.handlers.books import BooksHandler, book_kind

FIX = Path(__file__).parent / "fixtures" / "books"


def fixture(name: str) -> Any:
    text = (FIX / name).read_text(encoding="utf-8")
    return json.loads(text) if name.endswith(".json") else text


@pytest.fixture
async def net(settings: Settings) -> AsyncIterator[Net]:
    n = Net(settings)
    yield n
    await n.aclose()


def ctx(net: Net, settings: Settings, lang: str | None = None) -> SearchContext:
    return SearchContext(net=net, settings=settings, lang=lang)


def hit(source: str, kind: str | None, *, access: Access = Access.full_view, **kw: Any) -> BookHit:
    formats = (
        [BookFormat.model_validate({"kind": kind, "url": f"https://{source}.test/x"})]
        if kind
        else []
    )
    return BookHit(
        source=source,
        id=kw.pop("id", source),
        title=kw.pop("title", "Pride and Prejudice"),
        authors=kw.pop("authors", ["Jane Austen"]),
        access=access,
        formats=formats,
        details_url=f"https://{source}.test/",
        **kw,
    )


# ----- ranker ----------------------------------------------------------------------


def test_ranker_prefers_full_view_then_match_then_format() -> None:
    hits = [
        hit("borrow", "pdf_scan", access=Access.borrow_only),
        hit("scan", "pdf_scan"),
        hit("online", None, access=Access.view_online),
        hit("other_book", "epub", title="Emma"),
        hit("epub", "epub"),
        hit("chapter", "epub", partial=True),
        hit("text_pdf", "pdf_text"),
    ]
    order = [h.source for h in rank(hits, "pride and prejudice austen")]
    assert order[:4] == ["epub", "chapter", "text_pdf", "scan"]
    assert order.index("other_book") > order.index("scan")  # wrong title loses to a scan
    assert order[-2:] == ["online", "borrow"]


def test_ranker_uses_source_trust_as_tie_break() -> None:
    hits = [hit("gutendex", "epub"), hit("standard_ebooks", "epub")]
    trust = {a.name: a.trust for a in ADAPTERS}
    assert rank(hits, "pride", trust)[0].source == "standard_ebooks"


def test_relevance_folds_accents_and_case() -> None:
    assert relevance(hit("x", "epub", title="Les Misérables", authors=[]), "les miserables") == 1.0
    assert relevance(hit("x", "epub", title="源氏物語", authors=[]), "源氏物語") == 1.0


def test_not_downloadable_books_get_library_and_buy_links() -> None:
    linked = find_links(hit("ol", None, access=Access.in_copyright, isbn=["9780000000002"]))
    assert linked.library_links[0].url == "https://openlibrary.org/isbn/9780000000002"
    assert any("worldcat" in link.url for link in linked.library_links)
    assert linked.buy_links and "9780000000002" in linked.buy_links[0].url
    assert find_links(hit("ok", "epub")).library_links == []


def test_no_shadow_libraries_are_sources() -> None:
    banned = re.compile(r"libgen|z-?lib|annas|sci-?hub|pdfdrive|b-ok", re.I)
    for adapter in ADAPTERS:
        assert not banned.search(adapter.name + adapter.label + (adapter.search_url or ""))


# ----- adapters --------------------------------------------------------------------


@respx.mock
async def test_gutendex(net: Net, settings: Settings) -> None:
    respx.get(url__startswith="https://gutendex.com/books").mock(
        return_value=httpx.Response(200, json=fixture("gutendex.json"))
    )
    found = await BY_NAME["gutendex"].search(ctx(net, settings), "pride", 10)  # type: ignore[misc]
    assert [f.kind for f in found[0].formats] == ["epub", "txt", "html"]
    assert found[0].details_url == "https://www.gutenberg.org/ebooks/1342"
    assert found[1].access == Access.in_copyright and found[1].formats == []


@respx.mock
async def test_internet_archive_marks_lending_items(net: Net, settings: Settings) -> None:
    respx.get(url__startswith="https://archive.org/advancedsearch.php").mock(
        return_value=httpx.Response(200, json=fixture("internet_archive.json"))
    )
    found = await BY_NAME["internet_archive"].search(ctx(net, settings), "pride", 10)  # type: ignore[misc]
    assert found[0].access == Access.full_view
    assert {f.kind for f in found[0].formats} == {"pdf_text", "txt"}
    assert found[1].access == Access.borrow_only and found[1].formats == []


@respx.mock
async def test_open_library_access_states(net: Net, settings: Settings) -> None:
    respx.get(url__startswith="https://openlibrary.org/search.json").mock(
        return_value=httpx.Response(200, json=fixture("open_library.json"))
    )
    found = await BY_NAME["open_library"].search(ctx(net, settings), "pride", 10)  # type: ignore[misc]
    assert [h.access for h in found] == [Access.full_view, Access.in_copyright, Access.borrow_only]
    assert found[0].formats[0].url == "https://archive.org/details/prideprejudice00aust"
    assert found[0].isbn == ["9780141439518"]


@respx.mock
async def test_standard_ebooks_search_page(net: Net, settings: Settings) -> None:
    respx.get(url__startswith="https://standardebooks.org/ebooks").mock(
        return_value=httpx.Response(200, text=fixture("standard_ebooks.html"))
    )
    found = await BY_NAME["standard_ebooks"].search(ctx(net, settings), "pride", 10)  # type: ignore[misc]
    assert found[0].title == "Pride and Prejudice" and found[0].authors == ["Jane Austen"]
    assert found[0].formats[0].url == (
        "https://standardebooks.org/ebooks/jane-austen/pride-and-prejudice/downloads/"
        "jane-austen_pride-and-prejudice.epub"
    )
    assert epub_url("/ebooks/leo-tolstoy/war-and-peace/louise-maude_aylmer-maude").endswith(
        "/downloads/leo-tolstoy_war-and-peace_louise-maude_aylmer-maude.epub"
    )
    assert await BY_NAME["standard_ebooks"].search(ctx(net, settings, "fr"), "x", 5) == []  # type: ignore[misc]


@respx.mock
async def test_wikisource_uses_the_language(net: Net, settings: Settings) -> None:
    route = respx.get(url__startswith="https://fr.wikisource.org/w/api.php").mock(
        return_value=httpx.Response(200, json=fixture("wikisource.json"))
    )
    found = await BY_NAME["wikisource"].search(ctx(net, settings, "fr"), "x", 10)  # type: ignore[misc]
    assert route.called
    assert found[0].formats[0].url.startswith("https://ws-export.wmcloud.org/?format=epub&lang=fr")
    assert found[1].partial is True


@respx.mock
async def test_google_books_only_offers_allowed_downloads(net: Net, settings: Settings) -> None:
    respx.get(url__startswith="https://www.googleapis.com/books/v1/volumes").mock(
        return_value=httpx.Response(200, json=fixture("google_books.json"))
    )
    found = await BY_NAME["google_books"].search(ctx(net, settings), "pride", 10)  # type: ignore[misc]
    assert found[0].formats[0].kind == "pdf_scan" and found[0].access == Access.full_view
    assert found[1].access == Access.view_online and not found[1].formats


@respx.mock
async def test_hathitrust_by_isbn(net: Net, settings: Settings) -> None:
    assert identifier("978-0-14-143951-8") == ("isbn", "9780141439518")
    assert identifier("oclc:12345") == ("oclc", "12345")
    assert identifier("pride and prejudice") is None
    respx.get("https://catalog.hathitrust.org/api/volumes/brief/isbn/9780141439518.json").mock(
        return_value=httpx.Response(200, json=fixture("hathitrust.json"))
    )
    found = await BY_NAME["hathitrust"].search(ctx(net, settings), "9780141439518", 10)  # type: ignore[misc]
    assert [h.access for h in found] == [Access.view_online, Access.in_copyright]
    assert await BY_NAME["hathitrust"].search(ctx(net, settings), "pride", 10) == []  # type: ignore[misc]


@respx.mock
async def test_loc_items_point_at_iiif(net: Net, settings: Settings) -> None:
    respx.get(url__startswith="https://www.loc.gov/books/").mock(
        return_value=httpx.Response(200, json=fixture("loc.json"))
    )
    found = await BY_NAME["loc"].search(ctx(net, settings), "alice", 10)  # type: ignore[misc]
    assert len(found) == 1
    assert found[0].formats[0].url == "https://www.loc.gov/item/2021667404/"


@respx.mock
async def test_gallica_sru(net: Net, settings: Settings) -> None:
    respx.get(url__startswith="https://gallica.bnf.fr/SRU").mock(
        return_value=httpx.Response(200, text=fixture("gallica.xml"))
    )
    found = await BY_NAME["gallica"].search(ctx(net, settings), "misérables", 10)  # type: ignore[misc]
    assert found[0].id == "bpt6k5545437j" and found[0].access == Access.full_view
    assert found[0].formats[0].url == "https://gallica.bnf.fr/ark:/12148/bpt6k5545437j"
    assert found[1].access == Access.view_online and not found[1].formats


@respx.mock
async def test_ndl_opensearch(net: Net, settings: Settings) -> None:
    respx.get(url__startswith="https://ndlsearch.ndl.go.jp/api/opensearch").mock(
        return_value=httpx.Response(200, text=fixture("ndl.xml"))
    )
    found = await BY_NAME["ndl"].search(ctx(net, settings), "源氏物語", 10)  # type: ignore[misc]
    assert found[0].formats[0].url == "https://dl.ndl.go.jp/pid/2567680"
    assert found[0].authors == ["紫式部"]
    assert found[1].access == Access.view_online


@pytest.mark.parametrize(
    ("name", "fixture_name", "prefix", "key_attr"),
    [
        ("europeana", "europeana.json", "https://api.europeana.eu/", "europeana_key"),
        ("dpla", "dpla.json", "https://api.dp.la/", "dpla_key"),
        ("bhl", "bhl.json", "https://www.biodiversitylibrary.org/api3", "bhl_key"),
        ("trove", "trove.json", "https://api.trove.nla.gov.au/", "trove_key"),
        ("digitalnz", "digitalnz.json", "https://api.digitalnz.org/", "digitalnz_key"),
        ("ddb", "ddb.json", "https://api.deutsche-digitale-bibliothek.de/", "ddb_key"),
    ],
)
@respx.mock
async def test_keyed_sources(
    net: Net, settings: Settings, name: str, fixture_name: str, prefix: str, key_attr: str
) -> None:
    setattr(settings, key_attr, "secret-key")
    route = respx.get(url__startswith=prefix).mock(
        return_value=httpx.Response(200, json=fixture(fixture_name))
    )
    adapter = BY_NAME[name]
    assert adapter.key_setting == key_attr
    found = await adapter.search(ctx(net, settings), "x", 5)  # type: ignore[misc]
    assert found and found[0].title
    request = route.calls[0].request
    assert "secret-key" in str(request.url) or request.headers.get("x-api-key") == "secret-key"
    if name == "europeana":
        assert found[0].formats[0].url.startswith("https://iiif.europeana.eu/presentation/9200365/")
    if name == "bhl":
        assert found[0].formats[0].url == "https://www.biodiversitylibrary.org/itempdf/27850"


@respx.mock
async def test_wayback_finds_dead_ebook_links(net: Net, settings: Settings) -> None:
    respx.get(url__startswith="https://web.archive.org/cdx/search/cdx").mock(
        return_value=httpx.Response(
            200,
            json=[
                ["timestamp", "original", "mimetype", "statuscode", "length"],
                [
                    "20050101000000",
                    "http://old.example.org/book.pdf",
                    "application/pdf",
                    "200",
                    "1234",
                ],
            ],
        )
    )
    adapter = BY_NAME["wayback"]
    found = await adapter.search(ctx(net, settings), "http://old.example.org/book.pdf", 5)  # type: ignore[misc]
    assert found[0].formats[0].url == (
        "https://web.archive.org/web/20050101000000id_/http://old.example.org/book.pdf"
    )
    assert await adapter.search(ctx(net, settings), "pride and prejudice", 5) == []  # type: ignore[misc]


# ----- fan-out ---------------------------------------------------------------------


@respx.mock
async def test_search_books_merges_ranks_and_reports_sources(
    net: Net, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def slow(_ctx: SearchContext, _q: str, _limit: int) -> list[BookHit]:
        await asyncio.sleep(5)
        return []

    async def broken(_ctx: SearchContext, _q: str, _limit: int) -> list[BookHit]:
        raise HandlerError("upstream", "down")

    adapters = (
        BY_NAME["gutendex"],
        BY_NAME["standard_ebooks"],
        BY_NAME["open_library"],
        Adapter("slowpoke", "Slow", "global", slow),
        Adapter("broken", "Broken", "global", broken),
        BY_NAME["dpla"],  # no key set
        BY_NAME["ndli"],  # no search API
    )
    monkeypatch.setattr(search_mod, "ADAPTERS", adapters)
    respx.get(url__startswith="https://gutendex.com/books").mock(
        return_value=httpx.Response(200, json=fixture("gutendex.json"))
    )
    respx.get(url__startswith="https://standardebooks.org/ebooks").mock(
        return_value=httpx.Response(200, text=fixture("standard_ebooks.html"))
    )
    respx.get(url__startswith="https://openlibrary.org/search.json").mock(
        return_value=httpx.Response(200, json=fixture("open_library.json"))
    )
    result = await search_books(net, settings, "Pride and Prejudice", time_limit=0.2)
    assert result.best is not None and result.best.source == "standard_ebooks"
    assert result.results[1].source == "gutendex"
    states = {s.name: s.status for s in result.sources}
    assert states == {
        "gutendex": "ok",
        "standard_ebooks": "ok",
        "open_library": "ok",
        "slowpoke": "timeout",
        "broken": "error",
        "dpla": "needs_key",
        "ndli": "link_only",
    }
    ndli = next(s for s in result.sources if s.name == "ndli")
    assert ndli.search_url and "Pride+and+Prejudice" in ndli.search_url
    borrow = next(h for h in result.results if h.access == Access.borrow_only)
    assert borrow.library_links  # where to borrow it instead


async def test_book_sources_setting_limits_sources(settings: Settings) -> None:
    settings.book_sources = ["gutendex"]
    assert [a.name for a in search_mod.pick_adapters(settings, "books")] == ["gutendex"]
    libraries = {a.name for a in search_mod.pick_adapters(Settings(_env_file=None), "libraries")}
    assert {"loc", "gallica", "ndl", "trove", "digitalnz"} <= libraries


# ----- books handler ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "kind"),
    [
        ("https://www.gutenberg.org/ebooks/1342", "gutenberg"),
        ("https://www.gutenberg.org/ebooks/1342.epub3.images", None),
        ("https://standardebooks.org/ebooks/jane-austen/pride-and-prejudice", "standard_ebooks"),
        (
            "https://standardebooks.org/ebooks/jane-austen/pride-and-prejudice/downloads/x.epub",
            None,
        ),
        ("https://openlibrary.org/works/OL66554W/Pride_and_Prejudice", "open_library"),
        ("https://en.wikisource.org/wiki/Pride_and_Prejudice", "wikisource"),
        ("https://example.org/ebooks/1", None),
    ],
)
def test_book_links(url: str, kind: str | None) -> None:
    assert book_kind(url) == kind


@respx.mock
async def test_gutenberg_link_downloads_the_epub(net: Net, settings: Settings) -> None:
    book = fixture("gutendex.json")["results"][0]
    respx.get("https://gutendex.com/books/1342").mock(return_value=httpx.Response(200, json=book))
    epub = b"PK\x03\x04 epub"
    url = "https://www.gutenberg.org/ebooks/1342.epub3.images"
    respx.head(url).mock(
        return_value=httpx.Response(200, headers={"Content-Length": str(len(epub))})
    )
    respx.get(url).mock(return_value=httpx.Response(200, content=epub))
    handler = BooksHandler(net, settings, ArchiveOrgHandler(net))
    page = "https://www.gutenberg.org/ebooks/1342"
    probe = await handler.probe(page)
    assert [c.id for c in probe.choices] == ["epub", "txt", "html"] and probe.choices[0].default
    job = JobContext(id="b1", url=page, output_dir=settings.downloads_dir)
    result = await handler.download(job, {}, lambda _p: None)
    assert result.paths[0].name == "Pride and Prejudice - Austen, Jane.epub"
    assert result.paths[0].read_bytes() == epub


@respx.mock
async def test_open_library_borrow_only_is_refused(net: Net, settings: Settings) -> None:
    respx.get(url__startswith="https://openlibrary.org/search.json").mock(
        return_value=httpx.Response(
            200, json={"docs": [{"key": "/works/OL2W", "ebook_access": "borrowable", "ia": ["x"]}]}
        )
    )
    handler = BooksHandler(net, settings, ArchiveOrgHandler(net))
    with pytest.raises(HandlerError) as info:
        await handler.probe("https://openlibrary.org/works/OL2W")
    assert info.value.code == "borrow_only"
