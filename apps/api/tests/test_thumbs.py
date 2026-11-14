"""Library thumbnails: images, video frames, PDF first pages and audio covers."""

import shutil
import subprocess
from pathlib import Path

import img2pdf  # type: ignore[import-untyped]
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from anyget.core.settings import get_settings
from anyget.library.thumbs import make_thumbnail, thumbnail_for
from anyget.main import create_app

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
needs_poppler = pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="needs pdftoppm")


def picture(path: Path, size: tuple[int, int] = (800, 600)) -> Path:
    Image.new("RGB", size, (200, 120, 40)).save(path)
    return path


def is_small_webp(path: Path) -> bool:
    with Image.open(path) as image:
        return image.format == "WEBP" and max(image.size) <= 320


def test_image_thumbnail(tmp_path: Path) -> None:
    out = tmp_path / "t.webp"
    assert make_thumbnail(picture(tmp_path / "a.png"), "image", out)
    assert is_small_webp(out)
    (tmp_path / "broken.jpg").write_bytes(b"not an image")
    assert not make_thumbnail(tmp_path / "broken.jpg", "image", tmp_path / "b.webp")


@needs_poppler
def test_pdf_first_page(tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(img2pdf.convert(str(picture(tmp_path / "page.png"))))
    out = tmp_path / "pdf.webp"
    assert make_thumbnail(pdf, "pdf", out) and is_small_webp(out)


@needs_ffmpeg
def test_video_frame_and_audio_without_cover(tmp_path: Path) -> None:
    video = tmp_path / "clip.mp4"
    subprocess.run(  # noqa: S603 - test media made with the local ffmpeg
        [  # noqa: S607
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=1:size=640x360:rate=10",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
    )
    out = tmp_path / "video.webp"
    assert make_thumbnail(video, "video", out) and is_small_webp(out)

    audio = tmp_path / "tone.mp3"
    subprocess.run(  # noqa: S603 - test media made with the local ffmpeg
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=duration=1", str(audio)],  # noqa: S607
        check=True,
    )
    assert not make_thumbnail(audio, "audio", tmp_path / "audio.webp")  # no cover art


async def test_failures_are_remembered(tmp_path: Path) -> None:
    source = tmp_path / "x.png"
    source.write_bytes(b"broken")
    assert await thumbnail_for(tmp_path, "item1", source, "image") is None
    assert (tmp_path / "thumbs" / "item1.none").exists()
    picture(source)
    assert await thumbnail_for(tmp_path, "item1", source, "image") is None  # not retried


def test_thumb_endpoint(env_settings: Path) -> None:
    get_settings.cache_clear()
    root = env_settings / "downloads"
    root.mkdir(parents=True, exist_ok=True)
    picture(root / "photo.jpg")
    (root / "notes.txt").write_text("hello")
    with TestClient(create_app()) as client:
        client.post("/api/library/scan")
        items = {i["rel_path"]: i for i in client.get("/api/library").json()["items"]}
        photo, notes = items["photo.jpg"], items["notes.txt"]
        assert photo["thumbnail"] == f"/api/library/{photo['id']}/thumb"
        assert notes["thumbnail"] is None
        response = client.get(photo["thumbnail"])
        assert response.status_code == 200 and response.headers["content-type"] == "image/webp"
        # "No picture" is an empty 204 (not an error the browser logs); unknown ids stay 404.
        assert client.get(f"/api/library/{notes['id']}/thumb").status_code == 204
        assert client.get("/api/library/no-such-item/thumb").status_code == 404
    get_settings.cache_clear()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_audio_without_cover_stops_offering_a_thumbnail(env_settings: Path) -> None:
    import wave

    get_settings.cache_clear()
    root = env_settings / "downloads"
    root.mkdir(parents=True, exist_ok=True)
    with wave.open(str(root / "tone.wav"), "wb") as w:  # a WAV has no cover art
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\0\0" * 800)
    with TestClient(create_app()) as client:
        client.post("/api/library/scan")
        (item,) = client.get("/api/library").json()["items"]
        assert item["thumbnail"] == f"/api/library/{item['id']}/thumb"  # not known yet
        assert client.get(item["thumbnail"]).status_code == 204
        (item,) = client.get("/api/library").json()["items"]
        assert item["thumbnail"] is None  # known now: the cards don't ask again
    get_settings.cache_clear()
