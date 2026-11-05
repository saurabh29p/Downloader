"""Audio/video format conversion with ffmpeg, local files only."""

from pathlib import Path

from anyget.convert.tools import run

PRESETS: dict[str, list[str]] = {
    "mp3": ["-vn", "-c:a", "libmp3lame", "-q:a", "2"],
    "m4a": ["-vn", "-c:a", "aac", "-b:a", "192k"],
    "opus": ["-vn", "-c:a", "libopus", "-b:a", "128k"],
    "flac": ["-vn", "-c:a", "flac"],
    "wav": ["-vn", "-c:a", "pcm_s16le"],
    "mp4": ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "192k"],
    "mkv": ["-c", "copy"],
    "webm": ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "32", "-c:a", "libopus"],
}
MEDIA_EXTS = {
    ".mp4",
    ".mkv",
    ".webm",
    ".mov",
    ".avi",
    ".m4v",
    ".mp3",
    ".m4a",
    ".opus",
    ".ogg",
    ".oga",
    ".flac",
    ".wav",
    ".aac",
}


def is_media(path: Path) -> bool:
    return path.suffix.lower() in MEDIA_EXTS


async def convert(source: Path, target: Path, to: str) -> Path:
    partial = target.with_name(f"{target.stem}.part{target.suffix}")
    await run(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            # Only the local file protocol: a crafted file can't make ffmpeg fetch URLs.
            "-protocol_whitelist",
            "file",
            "-i",
            f"file:{source}",
            *PRESETS[to],
            f"file:{partial}",
        ],
        what="ffmpeg",
    )
    partial.replace(target)
    return target
