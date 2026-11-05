"""The `anyget` command line tool. Runs the engine in-process; no server needed."""

import asyncio
import contextlib
import re
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table

from anyget import __version__
from anyget.core.filenames import sanitize_filename
from anyget.core.jobs import ACTIVE_STATES, FINISHED_STATES, JobState
from anyget.core.net import BlockedURLError
from anyget.core.router import normalize
from anyget.core.services import Services
from anyget.core.settings import get_settings
from anyget.handlers.base import HandlerError

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


def _read_urls(urls: list[str], input_file: Path | None) -> list[str]:
    collected = list(urls)
    if input_file is not None:
        for line in input_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                collected.append(line)
    return collected


async def _plan(
    services: Services, url: str, options: dict[str, Any]
) -> list[tuple[str, dict[str, Any]]]:
    """One job per link; playlists and channels expand into one job per video."""
    _, handler = await services.router.resolve(url)
    if handler.name != "ytdlp":
        return [(url, options)]
    probe = await handler.probe(url)
    extra = probe.extra
    if extra.get("kind") not in ("playlist", "channel"):
        return [(url, options)]
    folder = sanitize_filename(probe.title, fallback=str(extra.get("id") or "playlist"))
    console.print(f"[cyan]≡[/cyan] {probe.title}: {len(extra['entries'])} items")
    items = []
    for entry in extra["entries"]:
        if entry.get("saved") or entry.get("live"):
            continue
        items.append(
            (
                entry["url"],
                {
                    **options,
                    "folder": folder,
                    "index": entry["index"],
                    "archive": extra["archive"],
                    "archive_id": entry["archive_id"],
                },
            )
        )
    return items


async def _get(urls: list[str], options: dict[str, Any]) -> int:
    services = Services.build(get_settings())
    await services.start(recover=False)  # leave other processes' jobs alone
    events = services.bus.subscribe()
    failures = 0
    job_ids: list[str] = []
    try:
        for raw in urls:
            try:
                url = raw.strip()
                if not url.startswith("anyget:"):  # internal task links need no network
                    url = normalize(raw)
                    await services.net.check(url)
            except BlockedURLError as exc:
                console.print(f"[red]✗[/red] {raw}: {exc}")
                failures += 1
                continue
            try:
                planned = await _plan(services, url, options)
            except (HandlerError, BlockedURLError) as exc:
                console.print(f"[red]✗[/red] {raw}: {exc}")
                failures += 1
                continue
            for item_url, item_options in planned:
                existing = services.store.find_resumable(item_url)
                if existing is not None:
                    console.print(f"[cyan]↻[/cyan] resuming {item_url}")
                    if existing.state == JobState.queued:
                        services.queue.schedule(existing.id)
                    else:
                        services.queue.resume(existing.id)
                    job_ids.append(existing.id)
                else:
                    job_ids.append(services.queue.submit(item_url, item_options).id)

        if not job_ids:
            return 1
        with Progress(
            TextColumn("[bold]{task.description}", justify="left"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            bars: dict[str, TaskID] = {
                job_id: progress.add_task("starting…", total=None) for job_id in job_ids
            }
            remaining = set(job_ids)
            try:
                async for event in events:
                    job = event["job"]
                    job_id = job.get("id")
                    if job_id not in bars:
                        continue
                    name = (job.get("title") or job.get("url") or "")[:40]
                    progress.update(
                        bars[job_id],
                        description=name,
                        completed=job.get("downloaded") or 0,
                        total=job.get("total"),
                    )
                    state = job.get("state")
                    if state in FINISHED_STATES or state == JobState.paused:
                        remaining.discard(job_id)
                        if state == JobState.done:
                            progress.console.print(f"[green]✓[/green] {job.get('rel_path')}")
                        elif state != JobState.paused:
                            failures += 1
                            progress.console.print(f"[red]✗[/red] {name}: {job.get('error')}")
                    if not remaining:
                        break
            except asyncio.CancelledError:
                # Ctrl+C: pause running jobs so the next run resumes from the partial file.
                for job_id in remaining:
                    job_obj = services.store.get(job_id)
                    if job_obj is not None and job_obj.state in ACTIVE_STATES:
                        with contextlib.suppress(Exception):
                            await services.queue.pause(job_id)
                console.print("[yellow]Paused. Run the same command again to resume.[/yellow]")
                raise
    finally:
        await events.aclose()
        await services.stop()
    return 1 if failures else 0


@app.command()
def get(
    urls: Annotated[list[str] | None, typer.Argument(help="Links to download")] = None,
    input_file: Annotated[
        Path | None, typer.Option("--input", "-i", help="Text file with one link per line")
    ] = None,
    quality: Annotated[
        str | None,
        typer.Option("--quality", "-q", help="Video: best, 2160, 1440, 1080, 720, 480 or 360"),
    ] = None,
    audio: Annotated[
        str | None, typer.Option("--audio", "-x", help="Audio only: mp3, m4a or opus")
    ] = None,
) -> None:
    """Download one or more links into the downloads folder."""
    all_urls = _read_urls(urls or [], input_file)
    if not all_urls:
        console.print("[red]Give at least one link (or -i list.txt).[/red]")
        raise typer.Exit(code=2)
    try:
        options: dict[str, Any] = {}
        if audio:
            options.update(preset="audio", audio_format=audio)
        elif quality:
            options["preset"] = quality
        code = asyncio.run(_get(all_urls, options))
    except KeyboardInterrupt:
        raise typer.Exit(code=130) from None
    raise typer.Exit(code=code)


async def _probe(url: str) -> None:
    services = Services.build(get_settings())
    try:
        normalized, handler = await services.router.resolve(url)
        result = await handler.probe(normalized)
    finally:
        await services.stop()
    table = Table(show_header=False, box=None)
    table.add_row("Handler", result.handler)
    table.add_row("Title", result.title)
    table.add_row("Size", f"{result.size:,} bytes" if result.size is not None else "unknown")
    for key, value in result.extra.items():
        if value not in (None, {}, ""):
            table.add_row(key.replace("_", " ").capitalize(), str(value))
    console.print(table)


@app.command()
def probe(url: Annotated[str, typer.Argument(help="Link to inspect")]) -> None:
    """Show what is behind a link without downloading it."""
    try:
        asyncio.run(_probe(url))
    except (BlockedURLError, HandlerError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except httpx.HTTPError as exc:
        console.print(f"[red]network error: {exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def jobs(
    limit: Annotated[int, typer.Option(help="How many to show")] = 20,
) -> None:
    """List recent download jobs."""
    services = Services.build(get_settings())
    rows = services.store.list_jobs(limit=limit)
    services.db.dispose()
    if not rows:
        console.print("No jobs yet. Try: anyget get <link>")
        return
    table = Table("State", "Title", "Progress", "Id")
    for job in rows:
        done = f"{job.downloaded:,}" + (f" / {job.total:,}" if job.total else "")
        table.add_row(job.state, (job.title or job.url)[:50], done, job.id[:8])
    console.print(table)


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Title, author, ISBN or an old ebook URL")],
    kind: Annotated[
        str, typer.Option("--type", help="books or libraries", case_sensitive=False)
    ] = "books",
    lang: Annotated[str | None, typer.Option(help="Language code, e.g. fr")] = None,
    limit: Annotated[int, typer.Option(help="Results per source")] = 5,
) -> None:
    """Find the best legal copy of a book across many free sources."""
    from anyget.books.search import search_books

    if kind not in ("books", "libraries"):
        raise typer.BadParameter("--type must be books or libraries")

    async def run() -> Any:
        services = Services.build(get_settings())
        try:
            return await search_books(
                services.net,
                services.settings,
                query,
                kind="libraries" if kind == "libraries" else "books",
                lang=lang,
                limit=limit,
            )
        finally:
            await services.stop()

    result = asyncio.run(run())
    if result.best:
        best = result.best
        console.print(f"[green]Best copy:[/green] {best.title} ({best.source})")
        console.print(f"  {best.formats[0].kind}: {best.formats[0].url}")
    table = Table("Source", "Title", "Access", "Formats")
    for hit in result.results[:25]:
        table.add_row(
            hit.source,
            hit.title[:50],
            hit.access.value.replace("_", " "),
            ", ".join(f.kind for f in hit.formats) or hit.details_url[:40],
        )
    console.print(table)
    notes = [f"{s.label}: {s.status}" for s in result.sources if s.status != "ok"]
    if notes:
        console.print("[dim]" + "; ".join(notes) + "[/dim]")


@app.command()
def convert(
    job: Annotated[str, typer.Argument(help="Job id (or its first characters)")],
    to: Annotated[str, typer.Option(help="pdf, ocr, mp3, m4a, opus, flac, wav, mp4, mkv, webm")],
    lang: Annotated[str | None, typer.Option(help="OCR languages, e.g. eng+hin")] = None,
) -> None:
    """Convert a finished download (page images to PDF, OCR, audio/video formats)."""
    from anyget.handlers.convert import TARGETS, convert_url

    if to not in TARGETS:
        raise typer.BadParameter(f"--to must be one of: {', '.join(TARGETS)}")
    services = Services.build(get_settings())
    matches = [j for j in services.store.list_jobs(limit=1000) if j.id.startswith(job)]
    services.db.dispose()
    if len(matches) != 1:
        console.print(
            f"[red]{'no job' if not matches else 'more than one job'} matches {job}[/red]"
        )
        raise typer.Exit(code=1)
    code = asyncio.run(_get([convert_url(matches[0].id, to, lang)], {}))
    raise typer.Exit(code=code)


@app.command()
def library(
    query: Annotated[str | None, typer.Argument(help="Search titles and paths")] = None,
    scan: Annotated[bool, typer.Option("--scan", help="Index files added by hand first")] = False,
    kind: Annotated[str | None, typer.Option(help="video, audio, image, pdf, epub, …")] = None,
    limit: Annotated[int, typer.Option(help="How many to show")] = 30,
) -> None:
    """List downloaded files in the library."""

    async def run() -> Any:
        services = Services.build(get_settings())
        try:
            if scan:
                found = await services.library.scan()
                console.print(f"Scanned: {found['added']} added, {found['removed']} removed")
            return services.library.search(query, kind, None, None, 0, limit)
        finally:
            await services.stop()

    page = asyncio.run(run())
    if not page.items:
        console.print("The library is empty. Try: anyget library --scan")
        return
    table = Table("Kind", "Title", "Size", "Path", "Id")
    for item in page.items:
        mark = " (copy)" if item.duplicate_of else ""
        table.add_row(
            item.kind, item.title[:40] + mark, f"{item.size:,}", item.rel_path[:50], item.id[:8]
        )
    console.print(table)


watch_app = typer.Typer(help="Check channels, playlists and archive.org collections for new items.")
app.add_typer(watch_app, name="watch")


@watch_app.command("add")
def watch_add(
    url: Annotated[str, typer.Argument(help="Channel, playlist or archive.org collection")],
    every: Annotated[int, typer.Option(help="Minutes between checks (min 60)")] = 360,
    initial: Annotated[int, typer.Option(help="Items to fetch on the first run")] = 5,
) -> None:
    """Add a watch (the API server runs it on schedule; `anyget watch run` runs it now)."""
    from anyget.watch.models import WatchIn

    async def run() -> Any:
        services = Services.build(get_settings())
        try:
            return await services.watches.create(
                WatchIn(url=url, interval_minutes=every, initial=initial)
            )
        finally:
            await services.stop()

    try:
        watch = asyncio.run(run())
    except (HandlerError, BlockedURLError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"Watching {watch.title} every {watch.interval_minutes} min (id {watch.id[:8]})")


@watch_app.command("list")
def watch_list() -> None:
    """List watches."""
    from anyget.watch.runner import out

    services = Services.build(get_settings())
    rows = [out(w) for w in services.watches.all()]
    services.db.dispose()
    if not rows:
        console.print("No watches yet. Try: anyget watch add <channel or collection link>")
        return
    table = Table("Title", "Every", "Last run", "New", "Seen", "Id")
    for w in rows:
        last = w.last_run.strftime("%Y-%m-%d %H:%M") if w.last_run else "never"
        new = "-" if w.last_new is None else str(w.last_new)
        table.add_row(w.title[:40], f"{w.interval_minutes} min", last, new, str(w.seen), w.id[:8])
    console.print(table)


@watch_app.command("run")
def watch_run(
    watch_id: Annotated[str, typer.Argument(help="Watch id (or its first characters)")],
) -> None:
    """Check one watch now and download what is new."""
    services = Services.build(get_settings())
    matches = [w for w in services.watches.all() if w.id.startswith(watch_id)]
    services.db.dispose()
    if len(matches) != 1:
        console.print(
            f"[red]{'no watch' if not matches else 'more than one watch'} matches {watch_id}[/red]"
        )
        raise typer.Exit(code=1)

    async def run() -> Any:
        inner = Services.build(get_settings())
        try:
            return await inner.watches.run(matches[0].id)
        finally:
            await inner.stop()

    result = asyncio.run(run())
    console.print(f"{result.queued} new item(s) queued")
    if result.queued:
        queued = [
            j
            for j in Services.build(get_settings()).store.list_jobs(limit=200)
            if j.id in set(result.job_ids)
        ]
        raise typer.Exit(code=asyncio.run(_get([j.url for j in queued], {})))


LINK = re.compile(r"(?:https?://|magnet:\?)\S+", re.IGNORECASE)


def links_in(text: str) -> list[str]:
    """Links in copied text, without trailing punctuation, in order, once each."""
    found = [m.group(0).rstrip(").,;'\"]>") for m in LINK.finditer(text or "")]
    return list(dict.fromkeys(found))


@app.command("watch-clipboard")
def watch_clipboard(
    auto: Annotated[bool, typer.Option("--auto", help="Download without asking")] = False,
    interval: Annotated[float, typer.Option(help="Seconds between clipboard checks")] = 1.0,
) -> None:
    """Desktop helper: links you copy are offered as downloads (Ctrl+C to stop)."""
    try:
        import pyperclip  # type: ignore[import-untyped,unused-ignore]  # optional extra
    except ImportError as exc:
        console.print(
            "This needs pyperclip: uv pip install 'anyget[desktop]' (or pip install pyperclip)"
        )
        raise typer.Exit(code=1) from exc
    import time as _time

    console.print("Watching the clipboard. Copy a link to download it. Ctrl+C to stop.")
    last = ""
    try:
        while True:
            text = str(pyperclip.paste() or "")
            if text != last:
                last = text
                for link in links_in(text):
                    if auto or typer.confirm(f"Download {link}?", default=True):
                        asyncio.run(_get([link], {}))
            _time.sleep(interval)
    except KeyboardInterrupt:
        console.print("Stopped.")


if __name__ == "__main__":
    app()
