"""`.env.example` documents every setting, and copying it changes nothing (safe defaults)."""

from pathlib import Path

import pytest

from anyget.core.settings import Settings

EXAMPLE = Path(__file__).resolve().parents[3] / ".env.example"
pytestmark = pytest.mark.skipif(not EXAMPLE.exists(), reason="only in a repository checkout")


def test_every_setting_is_documented() -> None:
    text = EXAMPLE.read_text(encoding="utf-8")
    missing = [name for name in Settings.model_fields if f"ANYGET_{name.upper()}=" not in text]
    assert missing == []


def test_copying_the_example_keeps_the_defaults() -> None:
    from_example = Settings(_env_file=EXAMPLE)
    defaults = Settings(_env_file=None)
    assert from_example.model_dump() == defaults.model_dump()
    assert from_example.retention_days == 0 and from_example.torrent_enabled is False
