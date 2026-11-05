"""Relevance for mixed search results (archive.org hits today, every source later).

archive.org sorts by downloads, so a search for a place ("Taj Mahal") used to list
popular concert recordings by the musician of that name first. Scores here prefer:
the query's words in the title, then in the subjects; the kind of media the words
ask for ("song", "film", "किताब"…); and push down recordings whose only match is an
artist's name when nobody asked for music. Popularity only breaks ties.
"""

import math
import re
from collections.abc import Iterable

from anyget.core.text import words
from anyget.handlers.archive_org import SearchHit

# Words that say which media is wanted (English, Hindi, Hinglish, Arabic).
_INTENT_TEXT: dict[str, frozenset[str]] = {
    "audio": frozenset(
        {
            "song",
            "songs",
            "music",
            "album",
            "concert",
            "live",
            "band",
            "mp3",
            "track",
            "audio",
            "gaana",
            "gana",
            "geet",
            "sangeet",
            "गाना",
            "गीत",
            "संगीत",
            "أغنية",
            "موسيقى",
            "podcast",
            "radio",
        }
    ),
    "movies": frozenset(
        {
            "movie",
            "movies",
            "film",
            "films",
            "video",
            "documentary",
            "cinema",
            "फिल्म",
            "फ़िल्म",
            "वीडियो",
            "فيلم",
            "فيديو",
        }
    ),
    "texts": frozenset(
        {
            "book",
            "books",
            "pdf",
            "epub",
            "novel",
            "text",
            "manuscript",
            "kitab",
            "किताब",
            "पुस्तक",
            "كتاب",
            "مخطوطة",
        }
    ),
    "image": frozenset({"photo", "photos", "image", "images", "picture", "map", "तस्वीर", "صورة"}),
}


# Folded the same way as queries.
INTENT_WORDS: dict[str, frozenset[str]] = {
    media: frozenset(w for hint in hints for w in words(hint))
    for media, hints in _INTENT_TEXT.items()
}
MUSIC_COLLECTIONS = frozenset({"etree", "audio_music", "georgeblood", "78rpm", "oldtimeradio"})
MEDIA_ALIASES = {"etree": "audio"}


def intents(query: str) -> set[str]:
    asked = words(query)
    return {media for media, hints in INTENT_WORDS.items() if asked & hints}


def _share(asked: set[str], text: Iterable[str]) -> float:
    if not asked:
        return 0.0
    return len(asked & words(" ".join(text))) / len(asked)


def score(hit: SearchHit, query: str) -> float:
    wanted = intents(query)
    hints = set().union(*(INTENT_WORDS[m] for m in wanted)) if wanted else set()
    asked = words(query) - hints or words(query)
    media = MEDIA_ALIASES.get(hit.mediatype or "", hit.mediatype or "")
    collections = set(hit.collection or [])
    music = media == "audio" or bool(collections & MUSIC_COLLECTIONS)

    title = _share(asked, [hit.title])
    subject = _share(asked, hit.subject or [])
    creator = _share(asked, [hit.creator or ""])
    phrase = _phrase_in(query, hints, hit.title)
    total = 2.0 * title + 1.0 * subject + (0.5 if phrase else 0.0)
    if wanted:
        total += 1.0 if media in wanted else -0.5
    elif music and creator >= 1.0:
        total -= 1.5  # e.g. "Taj Mahal" the musician, when nobody asked for music
    elif music:
        total -= 0.5
    total += min(math.log10((hit.downloads or 0) + 1), 6.0) / 30  # ties only
    return total


def _phrase_in(query: str, hints: set[str], title: str) -> bool:
    kept = [w for w in re.split(r"\s+", query.casefold().strip()) if w and not words(w) & hints]
    phrase = " ".join(kept)
    return bool(phrase) and phrase in title.casefold()


def rank_hits(hits: list[SearchHit], query: str) -> list[SearchHit]:
    """Most relevant first; equal scores keep their original order."""
    scored = sorted(enumerate(hits), key=lambda item: (-score(item[1], query), item[0]))
    return [hit for _, hit in scored]
