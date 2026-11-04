"""The `anyget` command line tool."""

from typing import Annotated

import httpx
import typer
from rich.console import Console

from anyget import __version__
from anyget.core.settings import get_settings

app = typer.Typer(help="AnyGet: paste any public link, get the file.", no_args_is_help=True)
console = Console()


@app.command()
def version() -> None:
    """Show the AnyGet version."""
    console.print(f"anyget {__version__}")


@app.command()
def health(
    url: Annotated[str | None, typer.Option(help="API base URL (default: from settings)")] = None,
) -> None:
    """Check that the AnyGet API is running."""
    settings = get_settings()
    base = url or f"http://{settings.host}:{settings.port}"
    try:
        response = httpx.get(f"{base}/api/health", timeout=5)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        console.print(f"[red]API not reachable at {base}:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]API ok[/green] at {base}")


if __name__ == "__main__":
    app()
