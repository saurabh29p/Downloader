from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from anyget import __version__
from anyget.cli.main import app
from anyget.core.settings import Settings

runner = CliRunner()
DATA = b"x" * 5000


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


@respx.mock
def test_health_ok() -> None:
    respx.get("http://api.test/api/health").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    result = runner.invoke(app, ["health", "--url", "http://api.test"])
    assert result.exit_code == 0
    assert "API ok" in result.stdout


@respx.mock
def test_health_down() -> None:
    respx.get("http://api.test/api/health").mock(side_effect=httpx.ConnectError("refused"))
    result = runner.invoke(app, ["health", "--url", "http://api.test"])
    assert result.exit_code == 1


def mock_file(url: str) -> None:
    respx.head(url).mock(
        return_value=httpx.Response(200, headers={"Content-Length": str(len(DATA))})
    )
    respx.get(url).mock(return_value=httpx.Response(200, content=DATA))


@respx.mock
def test_get_from_args_and_file(env_settings: Path) -> None:
    mock_file("https://files.test/a.bin")
    mock_file("https://files.test/b.bin")
    links = env_settings / "links.txt"
    links.write_text("# my links\nhttps://files.test/b.bin\n\n", encoding="utf-8")
    result = runner.invoke(app, ["get", "https://files.test/a.bin", "-i", str(links)])
    assert result.exit_code == 0, result.stdout
    downloads = env_settings / "downloads"
    assert (downloads / "a.bin").read_bytes() == DATA
    assert (downloads / "b.bin").read_bytes() == DATA

    listed = runner.invoke(app, ["jobs"])
    assert "a.bin" in listed.stdout and "done" in listed.stdout


def test_get_blocked(env_settings: Path) -> None:
    result = runner.invoke(app, ["get", "http://192.168.1.1/router.cfg"])
    assert result.exit_code == 1
    assert "private" in result.stdout


def test_get_needs_links(env_settings: Path) -> None:
    assert runner.invoke(app, ["get"]).exit_code == 2


@respx.mock
def test_probe_command(env_settings: Path) -> None:
    mock_file("https://files.test/a.bin")
    result = runner.invoke(app, ["probe", "https://files.test/a.bin"])
    assert result.exit_code == 0
    assert "5,000 bytes" in result.stdout


async def test_playlist_expands_into_numbered_items(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from anyget.cli.main import _plan
    from anyget.core.services import Services
    from anyget.handlers.base import Probe
    from anyget.handlers.ytdlp import YtDlpHandler

    entries = [
        {"index": 1, "url": "https://www.youtube.com/watch?v=a1", "archive_id": "youtube a1"},
        {
            "index": 2,
            "url": "https://www.youtube.com/watch?v=a2",
            "archive_id": "youtube a2",
            "saved": True,
        },
        {"index": 3, "url": "https://www.youtube.com/watch?v=a3", "archive_id": "youtube a3"},
    ]

    async def fake_probe(self: YtDlpHandler, url: str, options: object = None) -> Probe:
        extra = {"kind": "playlist", "entries": entries, "archive": "youtubetab-PL", "id": "PL"}
        return Probe(url=url, handler="ytdlp", title="Open / Movies", extra=extra)

    monkeypatch.setattr(YtDlpHandler, "probe", fake_probe)
    services = Services.build(settings)
    plan = await _plan(services, "https://www.youtube.com/playlist?list=PL", {"preset": "720"})
    await services.stop()
    assert [url for url, _ in plan] == [entries[0]["url"], entries[2]["url"]]  # saved one skipped
    first = plan[0][1]
    assert first == {
        "preset": "720",
        "folder": "Open _ Movies",
        "index": 1,
        "archive": "youtubetab-PL",
        "archive_id": "youtube a1",
    }


@respx.mock
def test_search_books(env_settings: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANYGET_BOOK_SOURCES", "gutendex")
    respx.get(url__startswith="https://gutendex.com/books").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 1342,
                        "title": "Pride and Prejudice",
                        "authors": [{"name": "Austen, Jane"}],
                        "formats": {"application/epub+zip": "https://www.gutenberg.org/x.epub"},
                    }
                ]
            },
        )
    )
    result = runner.invoke(app, ["search", "pride and prejudice"])
    assert result.exit_code == 0, result.output
    assert "Best copy:" in result.output and "epub" in result.output


def test_convert_needs_a_matching_job(env_settings: Path) -> None:
    result = runner.invoke(app, ["convert", "nope", "--to", "pdf"])
    assert result.exit_code == 1 and "no job matches" in result.output
    bad = runner.invoke(app, ["convert", "nope", "--to", "exe"])
    assert bad.exit_code != 0
