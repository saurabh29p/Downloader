"""Libraries and archives by region, and how AnyGet reads each one.

`access` says what works: "iiif" (paste an item link; pages are saved at full
size), "search" (also searchable from AnyGet), "pdf" (direct file links),
"page" (the web page handler lists the files), "link" (read on the site only).
`hosts` are matched by the IIIF handler; `adapter` names a books/ source.
"""

from typing import Literal

from pydantic import BaseModel

from anyget.books.base import Region

Access = Literal["iiif", "search", "pdf", "page", "link"]


class Library(BaseModel):
    id: str
    name: str
    region: Region
    country: str  # ISO 3166-1 alpha-2, or "INT"
    homepage: str
    access: list[Access]
    hosts: list[str] = []
    adapter: str | None = None
    key_setting: str | None = None


def _lib(
    id: str,
    name: str,
    region: Region,
    country: str,
    homepage: str,
    access: list[Access],
    hosts: list[str] | None = None,
    adapter: str | None = None,
    key_setting: str | None = None,
) -> Library:
    return Library(
        id=id,
        name=name,
        region=region,
        country=country,
        homepage=homepage,
        access=access,
        hosts=hosts or [],
        adapter=adapter,
        key_setting=key_setting,
    )


LIBRARIES: tuple[Library, ...] = (
    # Global
    _lib(
        "ia",
        "Internet Archive",
        "global",
        "INT",
        "https://archive.org/",
        ["search", "pdf"],
        adapter="internet_archive",
    ),
    _lib(
        "wayback",
        "Wayback Machine",
        "global",
        "INT",
        "https://web.archive.org/",
        ["search"],
        adapter="wayback",
    ),
    _lib(
        "gutenberg",
        "Project Gutenberg",
        "global",
        "INT",
        "https://www.gutenberg.org/",
        ["search", "pdf"],
        adapter="gutendex",
    ),
    _lib(
        "openlibrary",
        "Open Library",
        "global",
        "INT",
        "https://openlibrary.org/",
        ["search"],
        adapter="open_library",
    ),
    _lib(
        "wikisource",
        "Wikisource",
        "global",
        "INT",
        "https://wikisource.org/",
        ["search"],
        adapter="wikisource",
    ),
    _lib(
        "commons", "Wikimedia Commons", "global", "INT", "https://commons.wikimedia.org/", ["page"]
    ),
    _lib(
        "bhl",
        "Biodiversity Heritage Library",
        "global",
        "INT",
        "https://www.biodiversitylibrary.org/",
        ["search", "pdf"],
        adapter="bhl",
        key_setting="bhl_key",
    ),
    _lib(
        "unesco", "UNESCO Digital Library", "global", "INT", "https://unesdoc.unesco.org/", ["page"]
    ),
    # Europe
    _lib(
        "gallica",
        "Gallica (BnF)",
        "europe",
        "FR",
        "https://gallica.bnf.fr/",
        ["iiif", "search"],
        ["gallica.bnf.fr"],
        "gallica",
    ),
    _lib(
        "europeana",
        "Europeana",
        "europe",
        "INT",
        "https://www.europeana.eu/",
        ["iiif", "search"],
        ["europeana.eu", "iiif.europeana.eu"],
        "europeana",
        "europeana_key",
    ),
    _lib(
        "bl",
        "British Library",
        "europe",
        "GB",
        "https://www.bl.uk/",
        ["iiif"],
        ["iiif.bl.uk", "bl.digirati.io"],
    ),
    _lib(
        "ddb",
        "Deutsche Digitale Bibliothek",
        "europe",
        "DE",
        "https://www.deutsche-digitale-bibliothek.de/",
        ["search", "link"],
        adapter="ddb",
        key_setting="ddb_key",
    ),
    _lib(
        "mdz",
        "Munich Digitization Center (BSB)",
        "europe",
        "DE",
        "https://www.digitale-sammlungen.de/",
        ["iiif"],
        ["api.digitale-sammlungen.de", "digitale-sammlungen.de"],
    ),
    _lib("delpher", "Delpher", "europe", "NL", "https://www.delpher.nl/", ["page"]),
    _lib(
        "bdh", "Biblioteca Digital Hispánica (BNE)", "europe", "ES", "https://bdh.bne.es/", ["page"]
    ),
    _lib(
        "culturaitalia",
        "Internet Culturale",
        "europe",
        "IT",
        "https://www.internetculturale.it/",
        ["page"],
    ),
    _lib(
        "rsl",
        "Russian State Library (public domain)",
        "europe",
        "RU",
        "https://search.rsl.ru/",
        ["page"],
    ),
    _lib(
        "bodleian",
        "Bodleian Libraries (Oxford)",
        "europe",
        "GB",
        "https://digital.bodleian.ox.ac.uk/",
        ["iiif"],
        ["iiif.bodleian.ox.ac.uk"],
    ),
    _lib(
        "ecodices",
        "e-codices",
        "europe",
        "CH",
        "https://www.e-codices.unifr.ch/",
        ["iiif"],
        ["www.e-codices.unifr.ch", "e-codices.unifr.ch"],
    ),
    _lib(
        "wellcome",
        "Wellcome Collection",
        "europe",
        "GB",
        "https://wellcomecollection.org/",
        ["iiif"],
        ["iiif.wellcomecollection.org"],
    ),
    # Asia
    _lib(
        "ndl",
        "National Diet Library",
        "asia",
        "JP",
        "https://dl.ndl.go.jp/",
        ["iiif", "search"],
        ["dl.ndl.go.jp", "www.dl.ndl.go.jp"],
        "ndl",
    ),
    _lib("nlk", "National Library of Korea", "asia", "KR", "https://www.nl.go.kr/", ["page"]),
    _lib(
        "ndli",
        "National Digital Library of India",
        "asia",
        "IN",
        "https://ndl.iitkgp.ac.in/",
        ["link"],
        adapter="ndli",
    ),
    _lib("nlb", "NLB Singapore (BookSG)", "asia", "SG", "https://eresources.nlb.gov.sg/", ["page"]),
    _lib(
        "kyoto",
        "Kyoto University Rare Materials",
        "asia",
        "JP",
        "https://rmda.kulib.kyoto-u.ac.jp/",
        ["iiif"],
        ["rmda.kulib.kyoto-u.ac.jp"],
    ),
    _lib(
        "nijl",
        "National Institute of Japanese Literature",
        "asia",
        "JP",
        "https://kokusho.nijl.ac.jp/",
        ["iiif"],
        ["kokusho.nijl.ac.jp"],
    ),
    # Oceania
    _lib(
        "trove",
        "Trove (National Library of Australia)",
        "oceania",
        "AU",
        "https://trove.nla.gov.au/",
        ["search", "link"],
        adapter="trove",
        key_setting="trove_key",
    ),
    _lib(
        "digitalnz",
        "DigitalNZ and Papers Past",
        "oceania",
        "NZ",
        "https://digitalnz.org/",
        ["search", "link"],
        adapter="digitalnz",
        key_setting="digitalnz_key",
    ),
    # Middle East and Africa
    _lib(
        "qdl",
        "Qatar Digital Library",
        "middle_east_africa",
        "QA",
        "https://www.qdl.qa/",
        ["iiif"],
        ["www.qdl.qa", "qdl.qa"],
    ),
    _lib(
        "alexandrina",
        "Bibliotheca Alexandrina",
        "middle_east_africa",
        "EG",
        "https://www.bibalex.org/",
        ["page"],
    ),
    _lib(
        "eap",
        "Endangered Archives Programme (BL)",
        "middle_east_africa",
        "INT",
        "https://eap.bl.uk/",
        ["iiif"],
        ["eap.bl.uk"],
    ),
    _lib(
        "disa",
        "Digital Innovation South Africa",
        "middle_east_africa",
        "ZA",
        "https://disa.ukzn.ac.za/",
        ["page"],
    ),
    _lib(
        "nli",
        "National Library of Israel",
        "middle_east_africa",
        "IL",
        "https://www.nli.org.il/",
        ["iiif"],
        ["iiif.nli.org.il"],
    ),
    # Americas
    _lib(
        "loc",
        "Library of Congress (incl. World Digital Library)",
        "americas",
        "US",
        "https://www.loc.gov/",
        ["iiif", "search"],
        ["loc.gov", "www.loc.gov"],
        "loc",
    ),
    _lib(
        "dpla",
        "Digital Public Library of America",
        "americas",
        "US",
        "https://dp.la/",
        ["search", "link"],
        adapter="dpla",
        key_setting="dpla_key",
    ),
    _lib(
        "hathitrust",
        "HathiTrust (public domain)",
        "americas",
        "US",
        "https://www.hathitrust.org/",
        ["search", "link"],
        adapter="hathitrust",
    ),
    _lib(
        "bndigital",
        "Biblioteca Nacional Digital Brasil",
        "americas",
        "BR",
        "https://bndigital.bn.gov.br/",
        ["page"],
    ),
    _lib(
        "canadiana",
        "Canadiana",
        "americas",
        "CA",
        "https://www.canadiana.ca/",
        ["iiif"],
        ["www.canadiana.ca", "canadiana.ca"],
    ),
    _lib(
        "bnm",
        "Biblioteca Nacional de México",
        "americas",
        "MX",
        "https://bnm.iib.unam.mx/",
        ["page"],
    ),
    _lib(
        "bnargentina",
        "Biblioteca Nacional Mariano Moreno",
        "americas",
        "AR",
        "https://www.bn.gov.ar/",
        ["page"],
    ),
)

BY_ID = {library.id: library for library in LIBRARIES}
REGIONS: tuple[Region, ...] = (
    "global",
    "europe",
    "asia",
    "oceania",
    "middle_east_africa",
    "americas",
)


def library_for_host(host: str) -> Library | None:
    host = host.lower()
    for library in LIBRARIES:
        if any(host == h or host.endswith("." + h) for h in library.hosts):
            return library
    return None
