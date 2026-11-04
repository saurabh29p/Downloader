from pathlib import Path

import pytest

from anyget.core.filenames import (
    MAX_FILENAME_BYTES,
    UnsafePathError,
    ensure_inside,
    safe_join,
    sanitize_filename,
    unique_path,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("report.pdf", "report.pdf"),
        ('a<b>c:d"e|f?g*h.txt', "a_b_c_d_e_f_g_h.txt"),
        ("../../etc/passwd", "_._etc_passwd"),
        ("CON.txt", "_CON.txt"),
        ("lpt1", "_lpt1"),
        ("name. . .", "name"),
        ("   spaced   out  .mp3", "spaced out.mp3"),
        ("東京タワー.jpg", "東京タワー.jpg"),
        ("كتاب قديم.pdf", "كتاب قديم.pdf"),
        ("पुस्तक.epub", "पुस्तक.epub"),
    ],
)
def test_sanitize(raw: str, expected: str) -> None:
    assert sanitize_filename(raw) == expected


def test_nfc_normalized() -> None:
    decomposed = "cafe\u0301.txt"
    assert sanitize_filename(decomposed) == "caf\u00e9.txt"


def test_empty_uses_fallback() -> None:
    assert sanitize_filename("", fallback="abc123") == "abc123"
    assert sanitize_filename("...", fallback="abc123") == "abc123"
    assert sanitize_filename("///", fallback="id42") == "id42"


@pytest.mark.parametrize("char", ["a", "न", "日"])
def test_byte_limit_keeps_extension_and_whole_characters(char: str) -> None:
    name = sanitize_filename(char * 500 + ".pdf")
    assert len(name.encode("utf-8")) <= MAX_FILENAME_BYTES
    assert name.endswith(".pdf")
    name.encode("utf-8").decode("utf-8")  # no broken characters


def test_safe_join_inside(tmp_path: Path) -> None:
    path = safe_join(tmp_path, "music/album", "song.mp3")
    assert path == (tmp_path / "music" / "album" / "song.mp3").resolve()


@pytest.mark.parametrize(
    "evil",
    [
        "../outside.txt",
        "a/../../outside",
        "/etc/passwd",
        "\\\\server\\share",
        "C:\\Windows\\x",
        "..",
    ],
)
def test_safe_join_rejects_traversal(tmp_path: Path, evil: str) -> None:
    with pytest.raises(UnsafePathError):
        safe_join(tmp_path, evil)


def test_safe_join_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "link").symlink_to(outside)
    with pytest.raises(UnsafePathError):
        safe_join(root, "link", "file.txt")


def test_ensure_inside(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("x")
    assert ensure_inside(tmp_path, tmp_path / "a.txt") == (tmp_path / "a.txt").resolve()
    with pytest.raises(UnsafePathError):
        ensure_inside(tmp_path, tmp_path / ".." / "x")
    with pytest.raises(UnsafePathError):
        ensure_inside(tmp_path, tmp_path)


def test_unique_path(tmp_path: Path) -> None:
    first = tmp_path / "file.txt"
    assert unique_path(first) == first
    first.write_text("x")
    assert unique_path(first).name == "file (1).txt"
    (tmp_path / "file (1).txt").write_text("x")
    assert unique_path(first).name == "file (2).txt"
