"""Per-source download archives: one file per playlist/channel, so saved items are skipped."""

import re
from pathlib import Path

from anyget.core.filenames import sanitize_filename


def archive_key(extractor: str, source_id: str | None) -> str:
    """e.g. ("YoutubeTab", "UCxyz") → "youtubetab-UCxyz"; single videos: "<extractor>-videos"."""
    raw = f"{extractor.lower()}-{source_id or 'videos'}"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw)[:120]


def archive_path(data_dir: Path, key: str) -> Path:
    folder = data_dir / "archives"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / sanitize_filename(f"{key}.txt")


def archive_id(extractor: str, video_id: str) -> str:
    """The line yt-dlp writes for a saved item: '<extractor lowercase> <id>'."""
    return f"{extractor.lower()} {video_id}"


def contains(path: Path, entry: str) -> bool:
    if not path.exists():
        return False
    with path.open(encoding="utf-8") as fh:
        return any(line.strip() == entry for line in fh)
