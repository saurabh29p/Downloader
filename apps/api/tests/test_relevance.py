"""Search relevance: a place is not a band; asked-for media comes first."""

from anyget.handlers.archive_org import SearchHit
from anyget.universal.relevance import intents, rank_hits


def hit(
    identifier: str,
    title: str,
    mediatype: str,
    *,
    creator: str | None = None,
    subject: list[str] | None = None,
    collection: list[str] | None = None,
    downloads: int = 0,
) -> SearchHit:
    return SearchHit(
        identifier=identifier,
        title=title,
        mediatype=mediatype,
        creator=creator,
        subject=subject,
        collection=collection,
        downloads=downloads,
        thumbnail=f"https://archive.org/services/img/{identifier}",
    )


# archive.org's own order (by downloads): the musician's concerts first.
TAJ = [
    hit(
        "taj1973",
        "Taj Mahal Live at Fillmore",
        "etree",
        creator="Taj Mahal",
        collection=["etree", "TajMahal"],
        downloads=90_000,
    ),
    hit(
        "taj1999",
        "Taj Mahal - Blues Concert",
        "audio",
        creator="Taj Mahal",
        collection=["audio_music"],
        downloads=50_000,
    ),
    hit(
        "monument",
        "The Taj Mahal, Agra (photographs)",
        "image",
        subject=["Taj Mahal", "Agra", "Mughal architecture"],
        downloads=800,
    ),
    hit(
        "doc",
        "Taj Mahal: the story of a monument",
        "movies",
        subject=["Taj Mahal", "India"],
        downloads=1_200,
    ),
    hit("other", "Red Fort, Delhi", "image", subject=["Delhi"], downloads=5_000),
]


def ids(hits: list[SearchHit]) -> list[str]:
    return [h.identifier for h in hits]


def test_a_place_beats_a_band_of_the_same_name() -> None:
    ranked = ids(rank_hits(TAJ, "Taj Mahal"))
    assert ranked.index("monument") < ranked.index("taj1973")
    assert ranked.index("doc") < ranked.index("taj1999")
    assert ranked[-1] in ("other", "taj1973")


def test_asking_for_music_brings_the_concerts_back() -> None:
    ranked = ids(rank_hits(TAJ, "Taj Mahal live concert"))
    assert ranked[:2] == ["taj1973", "taj1999"]


def test_media_words_in_other_languages() -> None:
    assert intents("ताज महल फिल्म") == {"movies"}
    assert intents("taj mahal gaana") == {"audio"}
    assert intents("كتاب تاج محل") == {"texts"}
    ranked = ids(rank_hits(TAJ, "taj mahal film"))
    assert ranked[0] == "doc"


def test_equal_scores_keep_their_order() -> None:
    same = [hit("a", "Moon", "texts"), hit("b", "Moon", "texts")]
    assert ids(rank_hits(same, "moon")) == ["a", "b"]


def test_words_keep_hindi_and_arabic_whole() -> None:
    from anyget.core.text import words

    assert words("गोदान — प्रेमचंद") == {"गोदान", "प्रेमचंद"}
    assert words("ألف ليلة وليلة") == {"ألف", "ليلة", "وليلة"}
    assert words("Les Misérables, a novel") == {"les", "miserables", "novel"}
