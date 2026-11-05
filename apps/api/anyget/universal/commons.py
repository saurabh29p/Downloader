"""Wikimedia Commons photo search, with each file's licence.

One MediaWiki API call (`generator=search` in the File namespace, `imageinfo` with
`extmetadata`) gives titles, thumbnails and licences. Downloads go through the
Wikimedia handler (the original file, SHA-1 checked).
"""

from typing import Any
from urllib.parse import urlencode

from anyget.core.net import Net
from anyget.core.text import words
from anyget.handlers.base import HandlerError
from anyget.universal.models import Licence, ResultCard

API = "https://commons.wikimedia.org/w/api.php"


def licence_of(meta: dict[str, Any]) -> Licence:
    name = str((meta.get("LicenseShortName") or {}).get("value") or "").lower()
    if "public domain" in name or name.startswith(("pd", "cc0")):
        return "public_domain"
    if name.startswith("cc"):
        return "cc"
    return "unknown"


def _plain(value: Any) -> str | None:
    text = str((value or {}).get("value") or "")
    # extmetadata values are HTML; keep it short and tag-free.
    out, inside = [], False
    for char in text:
        if char == "<":
            inside = True
        elif char == ">":
            inside = False
        elif not inside:
            out.append(char)
    clean = " ".join("".join(out).split())
    return clean[:120] or None


async def search_photos(net: Net, query: str, limit: int = 12) -> list[ResultCard]:
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "search",
        "gsrnamespace": "6",
        "gsrsearch": f"{query} filetype:bitmap",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": "320",
    }
    response = await net.request("GET", f"{API}?{urlencode(params)}")
    if response.status_code >= 400:
        raise HandlerError("upstream", f"Wikimedia Commons answered {response.status_code}")
    pages = (response.json().get("query") or {}).get("pages") or []
    asked = words(query)
    cards = []
    for page in sorted(pages, key=lambda p: p.get("index", 0)):
        info = (page.get("imageinfo") or [{}])[0]
        title = str(page.get("title") or "")
        if not title or not info.get("descriptionurl"):
            continue
        meta = info.get("extmetadata") or {}
        name = title.removeprefix("File:").rsplit(".", 1)[0]
        share = len(asked & words(name)) / len(asked) if asked else 0.0
        date = _plain(meta.get("DateTimeOriginal")) or ""
        cards.append(
            ResultCard(
                id=f"commons:{page.get('pageid')}",
                source="commons",
                source_label="Wikimedia Commons",
                title=name,
                url=str(info["descriptionurl"]),
                download=str(info["descriptionurl"]),
                media="photo",
                licence=licence_of(meta),
                year=date[:4] if date[:4].isdigit() else None,
                creator=_plain(meta.get("Artist")),
                thumbnail=info.get("thumburl"),
                score=2.0 * share,
            )
        )
    return cards
