"""Turn yt-dlp's raw format list into a small, UI-friendly list and quality presets."""

from typing import Any, Literal

from pydantic import BaseModel

Preset = Literal["best", "2160", "1440", "1080", "720", "480", "360", "audio"]
HEIGHT_PRESETS: tuple[int, ...] = (2160, 1440, 1080, 720, 480, 360)
CONTAINERS = ("mp4", "mkv", "webm")
AUDIO_CODECS = ("mp3", "m4a", "opus")

_CODEC_NAMES = {
    "avc1": "H.264",
    "avc3": "H.264",
    "hev1": "H.265",
    "hvc1": "H.265",
    "vp9": "VP9",
    "vp09": "VP9",
    "av01": "AV1",
    "mp4a": "AAC",
    "opus": "Opus",
    "vorbis": "Vorbis",
    "mp3": "MP3",
    "flac": "FLAC",
    "ac-3": "AC-3",
    "ec-3": "E-AC-3",
}


class MediaFormat(BaseModel):
    id: str
    ext: str
    kind: Literal["video", "audio", "video+audio"]
    height: int | None = None
    width: int | None = None
    fps: float | None = None
    vcodec: str | None = None
    acodec: str | None = None
    abr: float | None = None
    tbr: float | None = None
    size: int | None = None
    size_is_estimate: bool = False
    label: str


def codec_name(raw: str | None) -> str | None:
    if not raw or raw == "none":
        return None
    head = raw.split(".")[0].lower()
    return _CODEC_NAMES.get(head, head.upper())


def _size(fmt: dict[str, Any]) -> tuple[int | None, bool]:
    if fmt.get("filesize"):
        return int(fmt["filesize"]), False
    if fmt.get("filesize_approx"):
        return int(fmt["filesize_approx"]), True
    return None, False


def normalize_formats(info: dict[str, Any]) -> list[MediaFormat]:
    """Downloadable formats, best first; storyboards, DRM and manifests-only are dropped."""
    result: list[MediaFormat] = []
    for fmt in info.get("formats") or []:
        if fmt.get("has_drm") or fmt.get("format_note") == "storyboard":
            continue
        vcodec, acodec = fmt.get("vcodec"), fmt.get("acodec")
        has_video = vcodec not in (None, "none") or (fmt.get("height") and vcodec is None)
        has_audio = acodec not in (None, "none")
        if not has_video and not has_audio:
            continue
        kind: Literal["video", "audio", "video+audio"] = (
            "video+audio" if has_video and has_audio else "video" if has_video else "audio"
        )
        size, estimate = _size(fmt)
        height = fmt.get("height") if has_video else None
        fps = fmt.get("fps")
        if has_video and height:
            label = f"{height}p{int(fps) if fps and fps > 30 else ''}"
        elif has_audio:
            abr = fmt.get("abr")
            label = f"{round(abr)} kbps" if abr else "audio"
        else:
            label = str(fmt.get("format_note") or fmt.get("format_id"))
        result.append(
            MediaFormat(
                id=str(fmt["format_id"]),
                ext=str(fmt.get("ext") or ""),
                kind=kind,
                height=height,
                width=fmt.get("width") if has_video else None,
                fps=fps if has_video else None,
                vcodec=codec_name(vcodec) if has_video else None,
                acodec=codec_name(acodec),
                abr=fmt.get("abr"),
                tbr=fmt.get("tbr"),
                size=size,
                size_is_estimate=estimate,
                label=label,
            )
        )
    result.sort(key=lambda f: (f.height or 0, f.abr or 0, f.tbr or 0), reverse=True)
    return result


def available_presets(formats: list[MediaFormat]) -> list[str]:
    """Presets that make sense for this video (no 2160 for a 720p upload)."""
    heights = [f.height for f in formats if f.height]
    has_audio = any(f.kind in ("audio", "video+audio") for f in formats)
    presets: list[str] = ["best"] if formats else []
    if heights:
        top = max(heights)
        presets += [
            str(h) for h in HEIGHT_PRESETS if h <= top and any(x >= h * 0.9 for x in heights)
        ]
        smallest = min(heights)
        if not any(str(h) in presets for h in HEIGHT_PRESETS) and smallest:
            presets.append(str(min(HEIGHT_PRESETS, key=lambda h: abs(h - smallest))))
    if has_audio:
        presets.append("audio")
    return presets


def _best(
    formats: list[MediaFormat], kind: str, max_height: int | None = None
) -> MediaFormat | None:
    for fmt in formats:  # sorted best first
        if fmt.kind != kind and not (kind == "video" and fmt.kind == "video+audio"):
            continue
        if max_height and fmt.height and fmt.height > max_height:
            continue
        return fmt
    return None


def estimate_size(formats: list[MediaFormat], preset: str) -> int | None:
    """Rough size of what a preset will download (best video at that height + best audio)."""
    audio = _best(formats, "audio")
    if preset == "audio":
        return audio.size if audio else None
    max_height = None if preset == "best" else int(preset)
    video = _best(formats, "video", max_height)
    if video is None:
        return None
    if video.kind == "video+audio" or audio is None:
        return video.size
    if video.size is None or audio.size is None:
        return None
    return video.size + audio.size


def format_selector(preset: str, format_id: str | None = None) -> str:
    """yt-dlp -f selector for a preset, e.g. 1080 → bv*[height<=1080]+ba/b[height<=1080]."""
    if format_id:
        # A chosen video-only format still gets the best audio merged in.
        return f"{format_id}+ba/{format_id}"
    if preset == "audio":
        return "ba/b"
    if preset == "best":
        return "bv*+ba/b"
    height = int(preset)
    return f"bv*[height<={height}]+ba/b[height<={height}]"
