"""Updating yt-dlp into the data folder (core/engine.py): checked, guarded, never partial."""

import hashlib
import io
import subprocess
import sys
import zipfile
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import respx

from anyget.core import engine
from anyget.core.net import Net
from anyget.core.settings import Settings
from anyget.handlers.base import HandlerError

NEW = "2099.1.1"
EJS = "9.9.9"
FILES = "https://files.pythonhosted.org/packages/x"


def wheel(package: str, module: str, version: str, extra: dict[str, str] | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(f"{module}/__init__.py", "")
        archive.writestr(f"{module}/version.py", f"__version__ = {version!r}\n")
        archive.writestr(
            f"{module}-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: {package}\nVersion: {version}\n",
        )
        for name, text in (extra or {}).items():
            archive.writestr(name, text)
    return buffer.getvalue()


YTDLP = wheel("yt-dlp", "yt_dlp", NEW)
YTDLP_EJS = wheel("yt-dlp-ejs", "yt_dlp_ejs", EJS)


def release(package: str, version: str, data: bytes, sha: str | None = None) -> dict[str, object]:
    filename = f"{package.replace('-', '_')}-{version}-py3-none-any.whl"
    return {
        "info": {"version": version, "requires_dist": [f'yt-dlp-ejs=={EJS}; extra == "default"']},
        "urls": [
            {"packagetype": "sdist", "filename": f"{package}-{version}.tar.gz", "url": "x"},
            {
                "packagetype": "bdist_wheel",
                "filename": filename,
                "url": f"{FILES}/{filename}",
                "digests": {"sha256": sha or hashlib.sha256(data).hexdigest()},
            },
        ],
    }


def mock_pypi(router: respx.MockRouter, ytdlp_sha: str | None = None) -> None:
    router.get("https://pypi.org/pypi/yt-dlp/json").mock(
        return_value=httpx.Response(200, json={"info": {"version": NEW}})
    )
    router.get(f"https://pypi.org/pypi/yt-dlp/{NEW}/json").mock(
        return_value=httpx.Response(200, json=release("yt-dlp", NEW, YTDLP, ytdlp_sha))
    )
    router.get(f"https://pypi.org/pypi/yt-dlp-ejs/{EJS}/json").mock(
        return_value=httpx.Response(200, json=release("yt-dlp-ejs", EJS, YTDLP_EJS))
    )
    router.get(f"{FILES}/yt_dlp-{NEW}-py3-none-any.whl").mock(
        return_value=httpx.Response(200, content=YTDLP)
    )
    router.get(f"{FILES}/yt_dlp_ejs-{EJS}-py3-none-any.whl").mock(
        return_value=httpx.Response(200, content=YTDLP_EJS)
    )


@pytest.fixture
async def net(settings: Settings) -> AsyncIterator[Net]:
    client = Net(settings)
    yield client
    await client.aclose()


@pytest.fixture
def checked(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Stand-in for the fresh-process check (the fake wheels have no networking)."""
    seen: list[Path] = []

    def fake_check(folder: Path) -> str:
        seen.append(folder)
        assert (folder / "yt_dlp" / "version.py").exists() and (folder / "yt_dlp_ejs").is_dir()
        return NEW

    monkeypatch.setattr(engine, "self_check", fake_check)
    return seen


def test_versions_compare_as_dates() -> None:
    assert engine.version_key("2026.10.26") < engine.version_key("2026.11.3")
    assert engine.version_key("2026.11.03") < engine.version_key("2026.11.03.1")


@respx.mock
async def test_update_installs_into_the_data_folder(
    net: Net, settings: Settings, checked: list[Path]
) -> None:
    mock_pypi(respx.mock)
    status = await engine.update(net, settings.data_dir)
    root = settings.data_dir / "engine"
    assert (root / "current").read_text() == NEW
    assert (root / NEW / "yt_dlp" / "version.py").read_text() == f"__version__ = {NEW!r}\n"
    assert (root / NEW / "yt_dlp_ejs" / "__init__.py").exists()
    assert status.updated == NEW and status.restart_needed and not status.update_available
    assert len(checked) == 1 and not list(root.glob(".*"))  # no staging or wheel left
    again = await engine.update(net, settings.data_dir)  # already there: nothing to do
    assert again.updated == NEW and len(checked) == 1


@respx.mock
async def test_a_wrong_checksum_installs_nothing(
    net: Net, settings: Settings, checked: list[Path]
) -> None:
    mock_pypi(respx.mock, ytdlp_sha="0" * 64)
    with pytest.raises(HandlerError) as info:
        await engine.update(net, settings.data_dir)
    assert info.value.code == "checksum"
    root = settings.data_dir / "engine"
    assert not (root / "current").exists() and not (root / NEW).exists()
    assert not checked


@respx.mock
async def test_a_failed_guard_check_installs_nothing(
    net: Net, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_pypi(respx.mock)

    def refuse(folder: Path) -> str:
        raise HandlerError("engine_check_failed", "net_guard could not hook it")

    monkeypatch.setattr(engine, "self_check", refuse)
    with pytest.raises(HandlerError) as info:
        await engine.update(net, settings.data_dir)
    assert info.value.code == "engine_check_failed"
    root = settings.data_dir / "engine"
    assert not (root / "current").exists() and not list(root.iterdir())


@pytest.mark.parametrize("name", ["../evil.py", "/abs/evil.py", "yt_dlp\\..\\evil.py"])
def test_unsafe_wheel_entries_are_refused(tmp_path: Path, name: str) -> None:
    bad = tmp_path / "bad.whl"
    bad.write_bytes(wheel("yt-dlp", "yt_dlp", NEW, {name: "x"}))
    with pytest.raises(HandlerError):
        engine.unpack_wheel(bad, tmp_path / "out")
    assert not (tmp_path / "evil.py").exists()


def test_symlink_entries_are_refused(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        link = zipfile.ZipInfo("yt_dlp/link")
        link.external_attr = 0o120777 << 16  # a symlink
        archive.writestr(link, "/etc/passwd")
    bad = tmp_path / "link.whl"
    bad.write_bytes(buffer.getvalue())
    with pytest.raises(HandlerError):
        engine.unpack_wheel(bad, tmp_path / "out")


def _activate_in_fresh_process(data_dir: Path) -> str:
    code = (
        "import sys; from pathlib import Path; from anyget.core import engine; "
        f"used = engine.activate(Path({str(data_dir)!r})); "
        "import yt_dlp.version; print(used, yt_dlp.version.__version__, engine.bundled_version())"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, timeout=60
    )
    return result.stdout.strip()


def _install_fake(data_dir: Path, version: str) -> None:
    folder = data_dir / "engine" / version
    folder.mkdir(parents=True)
    with zipfile.ZipFile(io.BytesIO(wheel("yt-dlp", "yt_dlp", version))) as archive:
        archive.extractall(folder)
    (data_dir / "engine" / "current").write_text(version)


def test_a_newer_update_is_used_after_a_restart(tmp_path: Path) -> None:
    _install_fake(tmp_path, NEW)
    used, imported, bundled = _activate_in_fresh_process(tmp_path).split()
    assert used == NEW and imported == NEW
    assert bundled not in ("None", NEW)  # the image's own version is still known


def test_an_older_update_never_replaces_a_newer_image(tmp_path: Path) -> None:
    _install_fake(tmp_path, "2000.1.1")
    used, imported, _ = _activate_in_fresh_process(tmp_path).split()
    assert used == "None" and imported != "2000.1.1"


def test_the_real_self_check_loads_yt_dlp_with_the_guard(tmp_path: Path) -> None:
    # An empty folder: the check imports the bundled yt-dlp and must hook every module.
    from importlib.metadata import version

    assert engine.self_check(tmp_path) == version("yt-dlp")


def test_the_guard_refuses_a_yt_dlp_it_cannot_hook() -> None:
    # A networking module without create_connection: installing must fail, not go on.
    code = (
        "from anyget.core import net_guard; "
        "net_guard.YTDLP_MODULES = (*net_guard.YTDLP_MODULES, 'json'); net_guard.install()"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode != 0
    assert "refusing to run yt-dlp unguarded" in result.stderr


@respx.mock
def test_update_endpoint(
    settings: Settings, checked: list[Path], respx_mock: respx.MockRouter
) -> None:
    from fastapi.testclient import TestClient

    from anyget.main import create_app

    respx_mock.route(host="testserver").pass_through()
    mock_pypi(respx_mock)
    with TestClient(create_app(settings)) as client:
        before = client.get("/api/settings/ytdlp").json()
        assert before["latest"] == NEW and before["update_available"] is True
        after = client.post("/api/settings/ytdlp/update").json()
        assert after["updated"] == NEW and after["restart_needed"] is True
        assert after["update_available"] is False
