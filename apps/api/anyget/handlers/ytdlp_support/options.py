"""Build yt-dlp parameters from AnyGet job options.

Safety settings are fixed here and never come from the user:
- geo_bypass is OFF (yt-dlp would otherwise fake an X-Forwarded-For address).
- Unplayable (DRM) formats are never allowed.
- Only yt-dlp's native downloaders fetch data (HLS/DASH included), so every
  connection goes through the SSRF guard; ffmpeg only processes local files.
"""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from anyget.handlers.ytdlp_support.formats import AUDIO_CODECS, CONTAINERS, format_selector

SAFETY_PARAMS: dict[str, Any] = {
    "geo_bypass": False,
    "allow_unplayable_formats": False,
    "external_downloader": {"default": "native"},
    "hls_prefer_native": True,
    "check_formats": False,
}

# A title is cut to 150 bytes so "<title> [<id>].<ext>" stays under the 180-byte limit.
TITLE_TEMPLATE = "%(title).150B [%(id)s].%(ext)s"


class MediaOptions(BaseModel):
    """What the user picked in the format picker (all optional)."""

    preset: Literal["best", "2160", "1440", "1080", "720", "480", "360", "audio"] = "best"
    format_id: str | None = Field(default=None, max_length=64, pattern=r"^[\w.+-]+$")
    container: Literal["mp4", "mkv", "webm"] | None = None
    audio_format: Literal["mp3", "m4a", "opus"] = "mp3"
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    chapters: bool = True
    subtitles: list[str] = Field(default_factory=list, max_length=50)
    auto_subtitles: bool = False
    subtitles_mode: Literal["srt", "embed"] = "srt"
    write_info_json: bool = False
    # Where playlist items go and how they are numbered (set by the playlist picker).
    folder: str | None = Field(default=None, max_length=200)
    index: int | None = Field(default=None, ge=1, le=100_000)
    # Archive file key (per playlist/channel) and date window (YYYYMMDD).
    archive: str | None = Field(default=None, max_length=160, pattern=r"^[\w.-]+$")
    date_after: str | None = Field(default=None, pattern=r"^\d{8}$")
    date_before: str | None = Field(default=None, pattern=r"^\d{8}$")
    use_cookies: bool = True

    @field_validator("subtitles")
    @classmethod
    def _langs(cls, value: list[str]) -> list[str]:
        import re

        return [lang for lang in value if re.fullmatch(r"[A-Za-z0-9_-]{1,20}", lang)]

    @property
    def audio_only(self) -> bool:
        return self.preset == "audio"


def _escape(text: str) -> str:
    """Literal text inside an output template: % must be doubled."""
    return text.replace("%", "%%")


def output_template(opts: MediaOptions) -> str:
    prefix = f"{opts.index:03d} - " if opts.index else ""
    return _escape(prefix) + TITLE_TEMPLATE


def build_params(
    opts: MediaOptions,
    *,
    home: Path,
    temp: Path,
    cache_dir: Path,
    archive_file: Path | None,
    cookie_file: Path | None,
    deno: str | None,
    proxy: str | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        **SAFETY_PARAMS,
        "quiet": True,
        "noprogress": True,
        "noplaylist": True,
        "windowsfilenames": True,
        "continuedl": True,
        "overwrites": False,
        "retries": 5,
        "fragment_retries": 10,
        "socket_timeout": 30,
        "paths": {"home": str(home), "temp": str(temp)},
        "outtmpl": {"default": output_template(opts)},
        "cachedir": str(cache_dir),
        "format": format_selector(opts.preset, opts.format_id),
    }
    if deno:
        params["js_runtimes"] = {"deno": {"path": deno}}
    if proxy:
        params["proxy"] = proxy
    if archive_file is not None:
        params["download_archive"] = str(archive_file)
    if cookie_file is not None:
        params["cookiefile"] = str(cookie_file)

    postprocessors: list[dict[str, Any]] = []
    if opts.audio_only:
        assert opts.audio_format in AUDIO_CODECS  # noqa: S101 (validated by pydantic)
        postprocessors.append(
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": opts.audio_format,
                "preferredquality": "0",
            }
        )
    else:
        container = opts.container
        if container:
            assert container in CONTAINERS  # noqa: S101 (validated by pydantic)
            params["merge_output_format"] = container
            postprocessors.append({"key": "FFmpegVideoRemuxer", "preferedformat": container})
            if container == "mp4":
                # Prefer H.264/AAC so the file plays everywhere, within the height limit.
                params["format_sort"] = ["res", "ext:mp4:m4a"]

    if opts.subtitles:
        params["writesubtitles"] = True
        params["writeautomaticsub"] = opts.auto_subtitles
        params["subtitleslangs"] = opts.subtitles
        if opts.subtitles_mode == "srt" or opts.audio_only:
            postprocessors.insert(
                0, {"key": "FFmpegSubtitlesConvertor", "format": "srt", "when": "before_dl"}
            )
        else:
            postprocessors.append({"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False})

    if opts.embed_metadata or opts.chapters:
        postprocessors.append(
            {
                "key": "FFmpegMetadata",
                "add_metadata": opts.embed_metadata,
                "add_chapters": opts.chapters,
            }
        )
    can_embed_thumbnail = opts.audio_only or opts.container != "webm"
    if opts.embed_thumbnail and can_embed_thumbnail:
        params["writethumbnail"] = True
        postprocessors.insert(
            0, {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"}
        )
        postprocessors.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
    if opts.write_info_json:
        params["writeinfojson"] = True

    params["postprocessors"] = postprocessors
    return params


def probe_params(
    *, max_entries: int, cache_dir: Path, deno: str | None, proxy: str | None
) -> dict[str, Any]:
    """Parameters for extract_info(download=False): flat playlists, no files written."""
    params: dict[str, Any] = {
        **SAFETY_PARAMS,
        "quiet": True,
        "noprogress": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "playlistend": max_entries,
        "cachedir": str(cache_dir),
        "socket_timeout": 30,
    }
    if deno:
        params["js_runtimes"] = {"deno": {"path": deno}}
    if proxy:
        params["proxy"] = proxy
    return params
