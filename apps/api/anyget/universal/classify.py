"""Is the text links, a search, or a question — and in which language?"""

import re

from anyget.core.text import words
from anyget.universal.models import Kind

_URL = re.compile(r"(?:https?://|magnet:\?)\S+", re.IGNORECASE)
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_ARABIC = re.compile(r"[؀-ۿ]")

QUESTION_STARTS = frozenset(
    words(
        "what who whom whose where when why how which is are was were can could does do "
        "did should would will tell explain kya kaun kab kahan kaise kyun kyon "
        "क्या कौन कब कहाँ कहां कैसे क्यों ما ماذا من متى أين اين كيف لماذا هل"
    )
)
# Common Hindi words written in Latin letters (Hinglish).
HINGLISH = frozenset(
    words("hai hain kya ka ki ke ko mein me se wala wali gaana gana kaise kahan chahiye dikhao")
)


def links_in(text: str) -> list[str]:
    seen: list[str] = []
    for match in _URL.findall(text):
        url = match.rstrip(").,;'\"»”>")
        if url not in seen:
            seen.append(url)
    return seen


def language_of(text: str) -> str:
    if _DEVANAGARI.search(text):
        return "hi"
    if _ARABIC.search(text):
        return "ar"
    if len(words(text) & HINGLISH) >= 1 and len(words(text)) >= 2:
        return "hinglish"
    return "en"


def classify(text: str) -> tuple[Kind, list[str]]:
    """("url", links) when the text is mainly links; else "question" or "search"."""
    links = links_in(text)
    rest = _URL.sub(" ", text).strip()
    if links and len(words(rest)) <= 3:
        return "url", links
    stripped = text.strip()
    tokens = stripped.split()
    first = words(tokens[0]) if tokens else set()
    if stripped.endswith(("?", "؟")) or (first & QUESTION_STARTS and len(tokens) >= 3):
        return "question", []
    return "search", []
