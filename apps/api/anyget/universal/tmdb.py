"""TMDB: what a film is and where to watch it legally in India (`watch/providers`, IN).

Needs the user's free TMDB key (Connections → TMDB, or TMDB_API_KEY). A v3 API key is
sent as `api_key`; a v4 read access token (a JWT, "eyJ…") as a Bearer header. AnyGet
never downloads these films: the card says where to stream, rent or buy them.
Provider data comes from TMDB (powered by JustWatch); its page link is shown as the
source, as TMDB's terms ask.
"""

import asyncio
from typing import Any
from urllib.parse import urlencode

from anyget.core.net import Net
from anyget.core.text import words
from anyget.handlers.base import HandlerError
from anyget.universal.models import MovieInfo, Provider, ResultCard

API = "https://api.themoviedb.org/3"
IMAGES = "https://image.tmdb.org/t/p"
REGION = "IN"
DETAILS = 4  # results that get full details (cast, trailer, providers)
EXTRAS = "credits,videos,watch/providers"


def _auth(key: str) -> tuple[dict[str, str], dict[str, str]]:
    """(headers, query params) for a v4 token or a v3 key."""
    key = key.strip()
    if key.startswith("eyJ"):
        return {"Authorization": f"Bearer {key}"}, {}
    return {}, {"api_key": key}


async def _get(net: Net, key: str, path: str, **params: str) -> dict[str, Any]:
    headers, auth = _auth(key)
    query = urlencode({**params, **auth})
    response = await net.request("GET", f"{API}{path}?{query}", headers=headers)
    if response.status_code in (401, 403):
        raise HandlerError("needs_key", "TMDB refused the key; check it in Connections")
    if response.status_code >= 400:
        raise HandlerError("upstream", f"TMDB answered {response.status_code}")
    data: dict[str, Any] = response.json()
    return data


def _providers(entries: list[dict[str, Any]] | None) -> list[Provider]:
    out = []
    for entry in sorted(entries or [], key=lambda e: e.get("display_priority", 99)):
        logo = entry.get("logo_path")
        out.append(
            Provider(
                name=str(entry.get("provider_name") or "?"),
                logo=f"{IMAGES}/w92{logo}" if logo else None,
            )
        )
    return out


def movie_info(details: dict[str, Any]) -> MovieInfo:
    credits = details.get("credits") or {}
    videos = (details.get("videos") or {}).get("results") or []
    trailer = next(
        (
            v
            for v in videos
            if v.get("site") == "YouTube" and v.get("type") == "Trailer" and v.get("key")
        ),
        None,
    )
    region = ((details.get("watch/providers") or {}).get("results") or {}).get(REGION) or {}
    return MovieInfo(
        tmdb_id=int(details["id"]),
        overview=details.get("overview") or None,
        rating=round(float(details["vote_average"]), 1) if details.get("vote_average") else None,
        cast=[str(c["name"]) for c in (credits.get("cast") or [])[:5] if c.get("name")],
        trailer=f"https://www.youtube.com/watch?v={trailer['key']}" if trailer else None,
        region=REGION,
        stream=_providers(region.get("flatrate")),
        free=_providers((region.get("free") or []) + (region.get("ads") or [])),
        rent=_providers(region.get("rent")),
        buy=_providers(region.get("buy")),
        watch_link=region.get("link"),
    )


def card(found: dict[str, Any], query: str, info: MovieInfo | None) -> ResultCard:
    title = str(found.get("title") or found.get("original_title") or "?")
    asked = words(query)
    share = len(asked & words(title)) / len(asked) if asked else 0.0
    poster = found.get("poster_path")
    return ResultCard(
        id=f"tmdb:{found['id']}",
        source="tmdb",
        source_label="TMDB",
        title=title,
        url=f"https://www.themoviedb.org/movie/{found['id']}",
        download=None,  # copyrighted films: where to watch only
        media="movie",
        licence="rights_reserved",
        year=str(found.get("release_date") or "")[:4] or None,
        thumbnail=f"{IMAGES}/w342{poster}" if poster else None,
        score=2.0 * share + 0.4,
        movie=info,
    )


async def search_movies(net: Net, key: str, query: str, limit: int = 8) -> list[ResultCard]:
    if not key:
        raise HandlerError("needs_key", "add a free TMDB key in Connections")
    found = (await _get(net, key, "/search/movie", query=query, region=REGION)).get("results")
    hits = [h for h in (found or []) if h.get("id")][:limit]

    async def details(hit: dict[str, Any]) -> MovieInfo | None:
        try:
            data = await _get(
                net,
                key,
                f"/movie/{int(hit['id'])}",
                append_to_response="credits,videos,watch/providers",
            )
        except HandlerError:
            return None
        return movie_info(data)

    infos = await asyncio.gather(*(details(h) for h in hits[:DETAILS]))
    padded = [*infos, *([None] * (len(hits) - len(infos)))]
    return [card(hit, query, info) for hit, info in zip(hits, padded, strict=True)]
