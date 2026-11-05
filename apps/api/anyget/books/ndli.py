"""National Digital Library of India: no open search API, so a search link only."""

from anyget.books.base import Adapter

ADAPTER = Adapter(
    "ndli",
    "National Digital Library of India",
    "asia",
    None,
    search_url="https://ndl.iitkgp.ac.in/se_search?q={q}",
    kinds=("books", "libraries"),
)
