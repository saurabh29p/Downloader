"""Backups: consistent database copy, private file, safe restore."""

import io
import sqlite3
import stat
import tarfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from anyget.backup import BackupError, create, restore
from anyget.cli.main import app


def make_data(data: Path) -> None:
    data.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(data / "anyget.db") as db:
        db.execute("create table t (v text)")
        db.execute("insert into t values ('hello')")
    (data / "cookies.txt").write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    (data / "archives").mkdir()
    (data / "archives" / "youtube-videos.txt").write_text("youtube abc\n", encoding="utf-8")


def test_backup_and_restore_round_trip(tmp_path: Path) -> None:
    data = tmp_path / "data"
    make_data(data)
    archive = create(data, tmp_path / "backups")
    assert stat.S_IMODE(archive.stat().st_mode) == 0o600
    with tarfile.open(archive) as tar:
        names = set(tar.getnames())
    assert {
        "anyget.db",
        "cookies.txt",
        "archives/youtube-videos.txt",
        "anyget-backup.json",
    } <= names

    with sqlite3.connect(data / "anyget.db") as db:
        db.execute("delete from t")
    (data / "archives" / "youtube-videos.txt").unlink()
    restored = restore(archive, data)
    assert restored == ["anyget.db", "cookies.txt", "archives"]
    with sqlite3.connect(data / "anyget.db") as db:
        assert db.execute("select v from t").fetchall() == [("hello",)]
    assert (data / "archives" / "youtube-videos.txt").read_text() == "youtube abc\n"
    assert stat.S_IMODE((data / "cookies.txt").stat().st_mode) == 0o600


def test_restore_refuses_unsafe_or_foreign_archives(tmp_path: Path) -> None:
    evil = tmp_path / "evil.tar.gz"
    with tarfile.open(evil, "w:gz") as tar:
        info = tarfile.TarInfo("../outside.txt")
        info.size = 2
        tar.addfile(info, io.BytesIO(b"hi"))
    with pytest.raises(BackupError):
        restore(evil, tmp_path / "data")
    assert not (tmp_path / "outside.txt").exists()
    other = tmp_path / "other.tar.gz"
    with tarfile.open(other, "w:gz") as tar:
        info = tarfile.TarInfo("notes.txt")
        info.size = 2
        tar.addfile(info, io.BytesIO(b"hi"))
    with pytest.raises(BackupError, match="not an AnyGet backup"):
        restore(other, tmp_path / "data")
    with pytest.raises(BackupError):
        create(tmp_path / "empty", tmp_path / "b")


def test_cli(env_settings: Path) -> None:
    make_data(env_settings / "data")
    runner = CliRunner()
    made = runner.invoke(app, ["backup", "create", "--out", str(env_settings / "b")])
    assert made.exit_code == 0, made.output
    archive = next((env_settings / "b").glob("anyget-*.tar.gz"))
    back = runner.invoke(app, ["backup", "restore", str(archive), "--yes"])
    assert back.exit_code == 0 and "anyget.db" in back.output
