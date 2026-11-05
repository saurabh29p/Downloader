"""Every book and library source, in the order results are merged."""

from anyget.books import (
    bhl,
    ddb,
    digitalnz,
    dpla,
    europeana,
    gallica,
    google_books,
    gutendex,
    hathitrust,
    internet_archive,
    loc,
    ndl,
    ndli,
    open_library,
    standard_ebooks,
    trove,
    wayback,
    wikisource,
)
from anyget.books.base import Adapter

ADAPTERS: tuple[Adapter, ...] = tuple(
    module.ADAPTER
    for module in (
        standard_ebooks,
        gutendex,
        internet_archive,
        open_library,
        wikisource,
        google_books,
        hathitrust,
        loc,
        gallica,
        ndl,
        europeana,
        dpla,
        bhl,
        trove,
        digitalnz,
        ddb,
        ndli,
        wayback,
    )
)
BY_NAME = {a.name: a for a in ADAPTERS}
