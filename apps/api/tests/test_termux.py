"""The Termux share script: finds the link and posts it to AnyGet (curl is faked)."""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "termux" / "termux-url-opener"


def run(tmp_path: Path, shared: str, status: str = "201", token: str = "") -> tuple[int, str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    log = tmp_path / "curl.log"
    curl = bin_dir / "curl"
    curl.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > {log}\nprintf {status}\n', encoding="utf-8")
    curl.chmod(curl.stat().st_mode | stat.S_IEXEC)
    config = tmp_path / "cfg" / "anyget"
    config.mkdir(parents=True, exist_ok=True)
    (config / "termux.env").write_text(
        f"ANYGET_URL=https://dl.example.org/\nANYGET_TOKEN={token}\n", encoding="utf-8"
    )
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "XDG_CONFIG_HOME": str(tmp_path / "cfg"),
    }
    done = subprocess.run(  # noqa: S603
        ["bash", str(SCRIPT), shared],  # noqa: S607
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return done.returncode, done.stdout + done.stderr, log.read_text() if log.exists() else ""


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_shares_the_first_link_with_token(tmp_path: Path) -> None:
    code, out, curl = run(
        tmp_path,
        "Watch this: https://v.test/a?b=1 and https://x.test",
        token="t0k",  # noqa: S106
    )
    assert code == 0 and "Sent to AnyGet: https://v.test/a?b=1" in out
    assert "https://dl.example.org/api/jobs" in curl
    assert "Authorization: Bearer t0k" in curl
    assert '{"urls":["https://v.test/a?b=1"],"options":{}}' in curl


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_reports_problems(tmp_path: Path) -> None:
    assert run(tmp_path, "no link here")[0] == 1
    code, out, _ = run(tmp_path, "https://v.test/a", status="401")
    assert code == 1 and "refused the token" in out
