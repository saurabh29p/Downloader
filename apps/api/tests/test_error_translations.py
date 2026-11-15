"""Every error code the API can return has a plain-words message in every language.

The web app shows `Errors.<code>` from apps/web/messages/<lang>.json and falls back to
"Something went wrong" for unknown codes, which tells the user nothing. Codes are found
in the source (HandlerError, {"code": …}, error_code=…, ConnectionValueError) and in
yt-dlp's reason table.
"""

import json
import re
from pathlib import Path

import pytest

from anyget.handlers.ytdlp_support import errors as ytdlp_errors

SOURCE = Path(__file__).resolve().parents[1] / "anyget"
MESSAGES = Path(__file__).resolve().parents[2] / "web" / "messages"
PATTERNS = (
    r'HandlerError\(\s*"([a-z_]+)"',
    r'"code":\s*"([a-z_]+)"',
    r'\berror_code="([a-z_]+)"',
    r'\bcode="([a-z_]+)"',
    r'\bcode = "([a-z_]+)" if',
    r'ConnectionValueError\(\s*f?"[^"]*",\s*"([a-z_]+)"',
)
pytestmark = pytest.mark.skipif(not MESSAGES.exists(), reason="only in a repository checkout")


def api_codes() -> set[str]:
    codes: set[str] = set()
    for path in SOURCE.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in PATTERNS:
            codes.update(re.findall(pattern, text))
    codes.update(code for code, _ in ytdlp_errors._RULES)
    return codes


def test_codes_were_found() -> None:
    codes = api_codes()
    assert {"internal", "disk_full", "not_cookies_txt", "login_required"} <= codes


@pytest.mark.parametrize("lang", ["en", "hi", "ar"])
def test_every_error_code_is_translated(lang: str) -> None:
    errors = json.loads((MESSAGES / f"{lang}.json").read_text(encoding="utf-8"))["Errors"]
    assert sorted(api_codes() - set(errors)) == []
