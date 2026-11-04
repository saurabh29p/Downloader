from pathlib import Path

import httpx
import respx
from typer.testing import CliRunner

from anyget import __version__
from anyget.cli.main import app

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
