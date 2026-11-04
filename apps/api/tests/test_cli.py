import httpx
import respx
from typer.testing import CliRunner

from anyget import __version__
from anyget.cli.main import app

runner = CliRunner()


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
