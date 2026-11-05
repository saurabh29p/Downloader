"""Words for matching titles and queries in any script."""

import unicodedata


def _wordish(char: str) -> bool:
    # Letters, digits, and marks (Devanagari and Arabic vowel signs belong to the word).
    return char.isalnum() or unicodedata.category(char).startswith("M")


def words(text: str) -> set[str]:
    """Lowercase words without Latin accents ("Café" → "cafe"); other scripts keep marks.

    One-letter Latin words ("a") are dropped; single letters in other scripts are kept.
    """
    out: list[str] = []
    after_latin = False
    for char in unicodedata.normalize("NFKD", text.casefold()):
        if unicodedata.combining(char) and after_latin:
            continue
        out.append(char if _wordish(char) else " ")
        if not unicodedata.combining(char):
            after_latin = char.isascii() and char.isalpha()
    return {w for w in "".join(out).split() if len(w) > 1 or not w.isascii()}
