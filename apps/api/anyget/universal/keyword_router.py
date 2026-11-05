"""The router that needs no AI: media and intent from words, then one query per source.

It is the default and the fallback when the optional LLM router (Phase 5) has no key,
hits its daily limit or answers badly. Words are matched in English, Hindi, Hinglish
and Arabic.
"""

from anyget.core.text import words
from anyget.universal.classify import classify, language_of
from anyget.universal.models import Intent, Media, QuerySpec, RouterPlan, SourceName

_MEDIA_TEXT: dict[Media, str] = {
    "movie": "movie movies film films cinema feature फिल्म फ़िल्म पिक्चर فيلم أفلام سينما",
    "music": "song songs music album concert band mp3 track gaana gana geet sangeet "
    "गाना गीत संगीत أغنية موسيقى",
    "video": "video videos documentary lecture clip वीडियो फ़ुटेज فيديو",
    "book": "book books ebook pdf epub novel kitab किताब पुस्तक كتاب رواية",
    "declassified": "declassified foia cia fbi classified jfk archives गोपनीय سري",
    "map": "map maps atlas naksha नक्शा मानचित्र خريطة خرائط",
    "newspaper": "newspaper newspapers gazette akhbar अख़बार अखबार समाचारपत्र صحيفة جريدة",
    "photo": "photo photos photograph image images picture pictures तस्वीर फोटो صورة صور",
    "manuscript": "manuscript manuscripts पांडुलिपि हस्तलिपि مخطوطة مخطوطات",
}
MEDIA_WORDS: dict[Media, frozenset[str]] = {m: frozenset(words(t)) for m, t in _MEDIA_TEXT.items()}

_INTENT_TEXT: dict[Intent, str] = {
    "download": "download save get dl डाउनलोड تنزيل تحميل",
    "watch": "watch stream dekho देखो देखें شاهد مشاهدة",
    "read": "read padho पढ़ो पढ़ें اقرأ قراءة",
    "listen": "listen suno सुनो سماع استمع",
}
INTENT_WORDS: dict[Intent, frozenset[str]] = {
    i: frozenset(words(t)) for i, t in _INTENT_TEXT.items()
}
FILLER = frozenset(words("free full online hd best legal the a an of for me please chahiye"))

# Sections (Phase 4) narrow the media; "more" and unknown sections leave it open.
SECTION_MEDIA: dict[str, list[Media]] = {
    "movies": ["movie"],
    "books": ["book"],
    "music": ["music"],
    "video": ["video"],
    "declassified": ["declassified"],
    "maps": ["map"],
    "newspapers": ["newspaper"],
    "photos": ["photo"],
    "manuscripts": ["manuscript"],
}

# Which sources can answer for each media, and archive.org's mediatype for it.
SOURCES_FOR: dict[Media, tuple[SourceName, ...]] = {
    "movie": ("archive", "videos"),
    "music": ("archive", "videos"),
    "video": ("archive", "videos"),
    "book": ("books", "archive", "libraries"),
    "manuscript": ("libraries", "archive"),
    "map": ("libraries", "archive"),
    "newspaper": ("libraries", "archive"),
    "photo": ("archive", "libraries"),
    "declassified": ("archive",),
    "other": ("archive",),
}
ARCHIVE_MEDIATYPE: dict[Media, str] = {
    "movie": "movies",
    "video": "movies",
    "music": "audio",
    "book": "texts",
    "manuscript": "texts",
    "newspaper": "texts",
    "declassified": "texts",
    "map": "image",
    "photo": "image",
}
ALL_SOURCES: tuple[SourceName, ...] = ("archive", "books", "videos", "libraries")


def clean_query(text: str) -> str:
    """The words that name the thing, without media/intent words and filler."""
    drop = FILLER.union(*MEDIA_WORDS.values(), *INTENT_WORDS.values())
    kept = [w for w in text.split() if not (words(w) and words(w) <= drop)]
    return " ".join(kept).strip(" ?؟.,!") or text.strip(" ?؟.,!")


def plan(text: str, section: str | None = None) -> RouterPlan:
    kind, urls = classify(text)
    language = language_of(text)
    if kind == "url":
        return RouterPlan(kind="url", intent="download", language=language, urls=urls)
    asked = words(text)
    media: list[Media] = [m for m, hints in MEDIA_WORDS.items() if asked & hints]
    if section in SECTION_MEDIA:
        media = SECTION_MEDIA[section]
    intent: Intent = next((i for i, hints in INTENT_WORDS.items() if asked & hints), "find")
    if kind == "question":
        intent = "explore"
    q = clean_query(text)[:300]
    queries: list[QuerySpec] = []
    sources: list[SourceName] = []
    for m in media or []:
        for source in SOURCES_FOR[m]:
            if source not in sources:
                sources.append(source)
    for source in sources or list(ALL_SOURCES):
        filters: dict[str, str] = {}
        if source == "archive" and len(media) == 1 and media[0] in ARCHIVE_MEDIATYPE:
            filters["mediatype"] = ARCHIVE_MEDIATYPE[media[0]]
        queries.append(QuerySpec(source=source, q=q, filters=filters))
    return RouterPlan(
        kind=kind,
        intent=intent,
        media=media,
        language=language,
        queries=queries,
        answer_needed=kind == "question",
    )
