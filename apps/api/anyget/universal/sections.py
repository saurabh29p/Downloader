"""Sections (v2 Phase 4): Movies, Books, Music, Video, Declassified and More.

Each section lists the sources it asks, its pre-built searches (a saved query plus
filters, e.g. an archive.org collection) and official sites that have no open API,
shown as "Search on …" links with the query filled in. Labels are translated by the
web (keys under Sections.*); queries and URLs are data.

Legal rules: no torrent, piracy or mirror sources, ever. Copyrighted films only show
where to watch them legally (TMDB). Declassified means officially released records.
"""

from dataclasses import dataclass, field

from anyget.universal.models import Media, SourceName


@dataclass(frozen=True)
class Preset:
    id: str
    query: str
    # Extra filters per source, e.g. {"archive": {"collection": "prelinger"}}.
    filters: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass(frozen=True)
class SiteLink:
    label: str
    # "{q}" is replaced by the URL-encoded query.
    url: str


@dataclass(frozen=True)
class Section:
    id: str
    media: tuple[Media, ...]
    sources: tuple[SourceName, ...]
    presets: tuple[Preset, ...]
    links: tuple[SiteLink, ...] = ()
    # "More" groups smaller sections and AnyGet's other pages.
    parent: str | None = None
    pages: tuple[str, ...] = ()


def _archive(collection: str, mediatype: str | None = None) -> dict[str, dict[str, str]]:
    filters = {"collection": collection}
    if mediatype:
        filters["mediatype"] = mediatype
    return {"archive": filters}


def _texts() -> dict[str, dict[str, str]]:
    return {"archive": {"mediatype": "texts"}}


SECTIONS: tuple[Section, ...] = (
    Section(
        "movies",
        ("movie",),
        ("tmdb", "archive", "videos"),
        (
            Preset("classic-hindi", "hindi film", _archive("feature_films", "movies")),
            Preset("silent-era", "silent film", _archive("silent_films", "movies")),
            Preset("film-noir", "film noir", _archive("Film_Noir", "movies")),
            Preset("fifties-scifi", "science fiction 1950s", _archive("SciFi_Horror", "movies")),
            Preset("oscar-winners", "Academy Award Best Picture"),
            Preset("youtube-free", "full movie free official channel", {"videos": {}}),
            Preset("prelinger", "Prelinger", _archive("prelinger", "movies")),
        ),
        (
            SiteLink("JustWatch India", "https://www.justwatch.com/in/search?q={q}"),
            SiteLink(
                "Internet Archive Feature Films",
                "https://archive.org/details/feature_films?query={q}",
            ),
        ),
    ),
    Section(
        "books",
        ("book",),
        ("books", "archive", "libraries"),
        (
            Preset("premchand", "Premchand"),
            Preset("classic-scifi", "science fiction"),
            Preset(
                "indian-history",
                "India history primary sources",
                {"archive": {"mediatype": "texts"}},
            ),
            Preset("textbooks", "textbook", _archive("opensource", "texts")),
            Preset("gita-upanishads", "Bhagavad Gita Upanishads translation"),
            Preset("hindi-sahitya", "हिन्दी साहित्य"),
        ),
        (
            SiteLink("Open Library", "https://openlibrary.org/search?q={q}"),
            SiteLink("Project Gutenberg", "https://www.gutenberg.org/ebooks/search/?query={q}"),
        ),
    ),
    Section(
        "music",
        ("music",),
        ("archive", "videos"),
        (
            Preset("hindi-78rpm", "hindi film songs", _archive("georgeblood", "audio")),
            Preset("ragas", "raga classical", _archive("audio_music", "audio")),
            Preset("old-radio", "radio drama", _archive("oldtimeradio", "audio")),
            Preset("great-78", "78rpm", _archive("georgeblood", "audio")),
        ),
        (
            SiteLink("Free Music Archive", "https://freemusicarchive.org/search?quicksearch={q}"),
            SiteLink("Musopen", "https://musopen.org/music/?q={q}"),
        ),
    ),
    Section(
        "video",
        ("video",),
        ("archive", "videos"),
        (
            Preset("nasa", "NASA mission footage", _archive("nasa", "movies")),
            Preset("partition", "Partition of India documentary"),
            Preset("mit-lectures", "MIT OpenCourseWare lecture"),
            Preset("newsreels", "newsreel", _archive("newsandpublicaffairs", "movies")),
        ),
        (SiteLink("NASA Image and Video Library", "https://images.nasa.gov/search?q={q}"),),
    ),
    Section(
        "declassified",
        ("declassified",),
        ("archive",),
        (
            Preset("jfk", "JFK assassination records"),
            Preset("uap", "UFO UAP files"),
            Preset("cold-war", "Cold War operations declassified"),
            Preset("mkultra", "MKUltra"),
            Preset("area51", "Area 51"),
        ),
        (
            SiteLink("CIA FOIA Reading Room", "https://www.cia.gov/readingroom/search/site/{q}"),
            SiteLink("FBI Vault", "https://vault.fbi.gov/search?SearchableText={q}"),
            SiteLink("US National Archives", "https://catalog.archives.gov/search?q={q}"),
            SiteLink(
                "UK National Archives",
                "https://discovery.nationalarchives.gov.uk/results/r?_q={q}",
            ),
            SiteLink("MuckRock", "https://www.muckrock.com/foi/list/?q={q}"),
            SiteLink("The Black Vault", "https://www.theblackvault.com/documentarchive/?s={q}"),
        ),
    ),
    Section(
        "more",
        ("other",),
        ("archive",),
        (),
        pages=("archive", "wayback", "code", "images", "libraries"),
    ),
    Section(
        "maps",
        ("map",),
        ("libraries", "archive"),
        (
            Preset("delhi-1900", "Delhi map 1800s"),
            Preset("mughal", "Mughal empire map"),
            Preset("survey-of-india", "Survey of India sheet"),
        ),
        (
            SiteLink(
                "David Rumsey Map Collection",
                "https://www.davidrumsey.com/luna/servlet/view/search?q={q}",
            ),
            SiteLink("Old Maps Online", "https://www.oldmapsonline.org/en/search?q={q}"),
            SiteLink("Library of Congress maps", "https://www.loc.gov/maps/?q={q}"),
        ),
        parent="more",
    ),
    Section(
        "newspapers",
        ("newspaper",),
        ("libraries", "archive"),
        (
            Preset("aug-1947", "15 August 1947 independence India newspaper"),
            Preset("chronicling-america", "newspaper 1900"),
        ),
        (
            SiteLink(
                "Chronicling America", "https://www.loc.gov/collections/chronicling-america/?q={q}"
            ),
            SiteLink(
                "Trove newspapers",
                "https://trove.nla.gov.au/search/category/newspapers?keyword={q}",
            ),
            SiteLink(
                "British Newspaper Archive",
                "https://www.britishnewspaperarchive.co.uk/search/results?basicsearch={q}",
            ),
        ),
        parent="more",
    ),
    Section(
        "photos",
        ("photo",),
        ("commons", "libraries", "archive"),
        (
            Preset("india-1900s", "India 1900s street"),
            Preset("old-bombay", "Bombay 1890s photograph"),
        ),
        (
            SiteLink("Flickr Commons", "https://www.flickr.com/search/?text={q}&is_commons=true"),
            SiteLink(
                "NYPL Digital Collections",
                "https://digitalcollections.nypl.org/search/index?keywords={q}",
            ),
            SiteLink("Library of Congress photos", "https://www.loc.gov/photos/?q={q}"),
        ),
        parent="more",
    ),
    Section(
        "manuscripts",
        ("manuscript",),
        ("libraries", "archive"),
        (
            Preset("sanskrit", "Sanskrit manuscript"),
            Preset("illuminated", "illuminated manuscript"),
        ),
        (
            SiteLink(
                "British Library manuscripts", "https://www.bl.uk/manuscripts/Default.aspx?q={q}"
            ),
            SiteLink("Vatican Library", "https://digi.vatlib.it/search?q={q}"),
            SiteLink("Digital Bodleian", "https://digital.bodleian.ox.ac.uk/search/?q={q}"),
            SiteLink(
                "Gallica",
                "https://gallica.bnf.fr/services/engine/search/sru?query=(gallica%20all%20%22{q}%22)",
            ),
        ),
        parent="more",
    ),
)
BY_ID: dict[str, Section] = {s.id: s for s in SECTIONS}


def preset_of(section_id: str | None, preset_id: str | None) -> Preset | None:
    section = BY_ID.get(section_id or "")
    if section is None or not preset_id:
        return None
    return next((p for p in section.presets if p.id == preset_id), None)
