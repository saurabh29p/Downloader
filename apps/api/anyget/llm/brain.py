"""What the optional AI adds to universal search, each with a no-AI fallback.

- plan: understand the input (JSON in the RouterPlan shape) → keyword router if not
- answer: a short answer to a question, citing result cards by id
- rerank: put the most relevant cards first
- suggestions: searches to try in a section
Only the typed text and result metadata (title, source, year, creator, media) are
sent. Answers come back in the language the user wrote in.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from anyget.core.settings import Settings
from anyget.llm.client import AiIssue, LlmUnavailable, OpenRouter
from anyget.llm.models import router_models, summary_models
from anyget.universal.keyword_router import ALL_SOURCES
from anyget.universal.keyword_router import plan as keyword_plan
from anyget.universal.models import Intent, Media, QuerySpec, ResultCard, RouterPlan
from anyget.universal.sections import BY_ID as SECTIONS
from anyget.universal.sections import preset_of

log = logging.getLogger("anyget.llm")

COOL_DOWN_ISSUES = ("no_credits", "bad_key")
COOL_DOWN = timedelta(minutes=10)
RECENT = timedelta(minutes=10)

LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "hinglish": "Hinglish", "ar": "Arabic"}
MAX_CARDS = 30
ITEMS_HEADER = "Items (id | title | source | year | creator | kind):\n"


class _Strict(BaseModel):
    # Strict JSON schema: every field required, nothing extra.
    model_config = ConfigDict(extra="forbid")


class RouterQuery(_Strict):
    # Checked against the sources AnyGet knows after the answer arrives.
    source: str = Field(max_length=20)
    q: str = Field(min_length=1, max_length=200)


class RouterAnswer(_Strict):
    kind: Literal["search", "question"]
    intent: Intent
    media: list[Media]
    language: str
    queries: list[RouterQuery]
    answer_needed: bool


class Answer(_Strict):
    text: str = Field(max_length=2000)
    citations: list[str]  # result card ids


class Reranked(_Strict):
    ids: list[str]


class Suggestions(_Strict):
    queries: list[str]


ROUTER_SYSTEM = (
    "You plan searches for AnyGet, a personal tool that finds legally downloadable or "
    "legally watchable items (public domain, Creative Commons, official releases). "
    "Read the user's text (English, Hindi, Hinglish or Arabic) and answer in JSON. "
    "kind: 'question' if they ask something, else 'search'. media: the kinds of items "
    "wanted, empty if any. language: en, hi, hinglish or ar. queries: 1 to 4 short "
    "English keyword searches, each for one source: archive (archive.org), books, "
    "videos (YouTube), libraries (national libraries), tmdb (films: where to watch), "
    "commons (photos). Never plan searches for pirated copies."
)


class Brain:
    def __init__(self, client: OpenRouter, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    @property
    def active(self) -> bool:
        if not (self.client.configured and self.client.under_limit()):
            return False
        # After "no credits" or a refused key, don't ask again for a while: every
        # search would wait for the same refusal.
        last = self.client.last_issue
        return not (
            last is not None
            and last[0] in COOL_DOWN_ISSUES
            and datetime.now(UTC) - last[1] < COOL_DOWN
        )

    def issue(self) -> AiIssue | None:
        """Why AI isn't helping right now (None if it is, or if no key is set)."""
        if not self.client.configured:
            return None
        if not self.client.under_limit():
            return "daily_limit"
        last = self.client.last_issue
        if last is not None and datetime.now(UTC) - last[1] < RECENT:
            return last[0]
        return None

    async def plan(
        self, text: str, section: str | None = None, preset: str | None = None
    ) -> RouterPlan:
        base = keyword_plan(text, section, preset)
        if base.kind == "url" or preset_of(section, preset) is not None or not self.active:
            return base
        user = f"Section: {section or 'any'}\nText: {text.strip()[:500]}"
        try:
            got = await self.client.ask(
                "router", router_models(self.settings), ROUTER_SYSTEM, user, RouterAnswer
            )
        except LlmUnavailable as exc:
            log.info("router fell back to keywords: %s", exc)
            return base
        scope = SECTIONS.get(section or "")
        allowed = set(scope.sources) if scope and scope.id != "more" else set(ALL_SOURCES)
        allowed |= {"tmdb", "commons"} if scope is None else set()
        queries = [
            QuerySpec(source=q.source, q=q.q.strip())
            for q in got.queries
            if q.source in allowed and q.q.strip()
        ][:4]
        if not queries:
            return base
        # Keep the keyword plan's filters (archive mediatype) for matching sources.
        filters = {q.source: q.filters for q in base.queries}
        for query in queries:
            query.filters = dict(filters.get(query.source, {}))
        return RouterPlan(
            kind=got.kind,
            intent=got.intent,
            media=list(scope.media) if scope and scope.id != "more" else got.media,
            language=got.language if got.language in LANGUAGE_NAMES else base.language,
            queries=queries,
            answer_needed=got.answer_needed or got.kind == "question",
            router="llm",
        )

    @staticmethod
    def _listing(cards: list[ResultCard]) -> str:
        lines = []
        for card in cards[:MAX_CARDS]:
            bits = [card.title, card.source_label, card.year or "", card.creator or "", card.media]
            lines.append(f"{card.id} | " + " | ".join(b for b in bits if b))
        return "\n".join(lines)

    async def answer(self, question: str, language: str, cards: list[ResultCard]) -> Answer | None:
        if not self.active or not cards:
            return None
        name = LANGUAGE_NAMES.get(language, "English")
        system = (
            "Answer the question in a few sentences, in "
            f"{name}, using only the listed items as sources. Cite the ids you used. "
            "If the items don't answer it, say so in one sentence and cite nothing."
        )
        user = f"Question: {question.strip()[:500]}\n{ITEMS_HEADER}"
        try:
            got = await self.client.ask(
                "answer",
                summary_models(self.settings),
                system,
                user + self._listing(cards),
                Answer,
            )
        except LlmUnavailable as exc:
            log.info("no answer card: %s", exc)
            return None
        known = {c.id for c in cards}
        return Answer(text=got.text, citations=[c for c in got.citations if c in known])

    async def rerank(self, query: str, cards: list[ResultCard]) -> list[str] | None:
        if not self.active or len(cards) < 3:
            return None
        system = (
            "Order the items from most to least relevant to the search. Return their ids. "
            "Prefer items that are the thing asked for over items merely named after it."
        )
        user = (
            f"Search: {query.strip()[:300]}\nItems (id | title | source | year | creator | kind):\n"
        )
        try:
            got = await self.client.ask(
                "rerank",
                summary_models(self.settings),
                system,
                user + self._listing(cards),
                Reranked,
            )
        except LlmUnavailable as exc:
            log.info("no re-ranking: %s", exc)
            return None
        known = [c.id for c in cards[:MAX_CARDS]]
        ordered = [i for i in dict.fromkeys(got.ids) if i in known]
        return ordered + [i for i in known if i not in ordered]

    async def suggestions(self, section: str) -> list[str]:
        scope = SECTIONS.get(section)
        if scope is None:
            return []
        fallback = [p.query for p in scope.presets]
        if not self.active:
            return fallback
        system = (
            "Suggest 6 short searches (2 to 5 words each) for a section of AnyGet, a tool "
            "for legally downloadable public-domain and openly licensed items. Return them "
            "as queries. Vary topics; include India-related ideas."
        )
        user = f"Section: {section}\nExisting searches: " + "; ".join(fallback)
        try:
            got = await self.client.ask(
                "suggestions", summary_models(self.settings), system, user, Suggestions
            )
        except LlmUnavailable:
            return fallback
        clean = [q.strip()[:80] for q in got.queries if q.strip()]
        return clean[:8] or fallback
