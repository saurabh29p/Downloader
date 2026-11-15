# ruff: noqa: S105  (fake test keys)
"""The optional AI helper (v2 Phase 5): OpenRouter calls, fallbacks, limits, privacy."""

import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from anyget.core.db import Database
from anyget.core.net import Net
from anyget.core.settings import Settings, get_settings
from anyget.llm.brain import Brain
from anyget.llm.client import API, OpenRouter
from anyget.llm.models import router_models, summary_models
from anyget.llm.store import LlmStore
from anyget.main import create_app
from anyget.universal.models import ResultCard

KEY = "sk-or-test-key"


def reply(payload: Any, cost: float = 0.0001) -> httpx.Response:
    content = payload if isinstance(payload, str) else json.dumps(payload)
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30, "cost": cost},
        },
    )


ROUTER_OK = {
    "kind": "question",
    "intent": "explore",
    "media": ["photo"],
    "language": "hi",
    "queries": [
        {"source": "commons", "q": "Taj Mahal construction"},
        {"source": "archive", "q": "Taj Mahal history"},
        {"source": "torrents", "q": "nope"},
    ],
    "answer_needed": True,
}


@pytest.fixture
async def brain(settings: Settings) -> AsyncIterator[Brain]:
    settings.openrouter_key = KEY
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(settings)
    db.create_all()
    net = Net(settings)
    yield Brain(OpenRouter(net, settings, LlmStore(db)), settings)
    await net.aclose()
    db.dispose()


def card(card_id: str, title: str) -> ResultCard:
    return ResultCard(
        id=card_id,
        source="archive",
        source_label="Internet Archive",
        title=title,
        url=f"https://archive.org/details/{card_id}",
        media="book",
    )


def test_model_lists_and_free_mode(settings: Settings) -> None:
    assert router_models(settings)[0] == "google/gemini-2.5-flash-lite"
    assert len(summary_models(settings)) == 2
    settings.llm_free_mode = True
    assert all(m.endswith(":free") for m in router_models(settings) + summary_models(settings))
    settings.llm_router_models = ["a/b", "c/d:free"]
    assert router_models(settings) == ["c/d:free"]


def test_model_lists_from_env_are_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    # .env.example documents these as comma separated; a bare list type made start-up fail.
    monkeypatch.setenv("ANYGET_LLM_ROUTER_MODELS", "google/gemma-4-31b-it:free, openai/gpt-5-nano")
    monkeypatch.setenv("ANYGET_LLM_SUMMARY_MODELS", "")
    loaded = Settings(_env_file=None)
    assert loaded.llm_router_models == ["google/gemma-4-31b-it:free", "openai/gpt-5-nano"]
    assert loaded.llm_summary_models == []


@respx.mock
async def test_router_plan_request_shape_and_privacy(brain: Brain) -> None:
    route = respx.post(API).mock(return_value=reply(ROUTER_OK))
    planned = await brain.plan("ताज महल किसने बनवाया?")
    assert planned.router == "llm" and planned.kind == "question" and planned.answer_needed
    assert [q.source for q in planned.queries] == ["commons", "archive"]  # unknown dropped
    assert planned.language == "hi"
    request = route.calls[0].request
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert request.headers["x-title"] == "AnyGet"
    assert request.headers["http-referer"].startswith("https://")
    body = json.loads(request.content)
    assert body["models"][0] == "google/gemini-2.5-flash-lite"
    assert body["provider"] == {"require_parameters": True, "sort": "latency"}
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert KEY not in json.dumps(body)  # the key is only in the header
    assert "ताज महल किसने बनवाया?" in body["messages"][1]["content"]
    assert brain.client.store.today().calls == 1


@respx.mock
async def test_retry_once_then_keywords(brain: Brain) -> None:
    route = respx.post(API)
    route.side_effect = [reply("not json"), reply(ROUTER_OK)]
    assert (await brain.plan("who built the Taj Mahal?")).router == "llm"
    route.side_effect = [reply("{}"), reply("still bad")]
    fallback = await brain.plan("who painted the Mona Lisa?")
    assert fallback.router == "keyword" and fallback.queries


@respx.mock
async def test_cache_and_daily_limit(brain: Brain) -> None:
    route = respx.post(API).mock(return_value=reply(ROUTER_OK))
    await brain.plan("Taj Mahal history")
    await brain.plan("Taj Mahal history")
    assert route.call_count == 1  # cached for 24 h
    brain.settings.llm_daily_limit = 1
    assert (await brain.plan("something else entirely")).router == "keyword"
    assert route.call_count == 1


@respx.mock
async def test_refused_key_falls_back(brain: Brain) -> None:
    respx.post(API).mock(return_value=httpx.Response(401, json={}))
    assert (await brain.plan("Taj Mahal")).router == "keyword"


async def test_no_key_means_no_calls(settings: Settings) -> None:
    db = Database(settings)
    db.create_all()
    net = Net(settings)
    brain = Brain(OpenRouter(net, settings, LlmStore(db)), settings)
    assert not brain.active
    assert (await brain.plan("Taj Mahal")).router == "keyword"
    assert await brain.answer("why?", "en", [card("a", "A")]) is None
    assert await brain.suggestions("books") == [
        "Premchand",
        "science fiction",
        "India history primary sources",
        "textbook",
        "Bhagavad Gita Upanishads translation",
        "हिन्दी साहित्य",
    ]
    await net.aclose()


@respx.mock
async def test_answer_rerank_and_suggestions(brain: Brain) -> None:
    cards = [card("a1", "Agra photographs"), card("b2", "Taj Mahal band"), card("c3", "Mughal")]
    route = respx.post(API)
    route.side_effect = [
        reply({"text": "शाहजहाँ ने बनवाया।", "citations": ["c3", "zz"]}),
        reply({"ids": ["c3", "a1", "nope"]}),
        reply({"queries": ["Mughal gardens", " ", "Hampi ruins"]}),
    ]
    answer = await brain.answer("ताज महल किसने बनवाया?", "hi", cards)
    assert answer is not None and answer.citations == ["c3"]  # unknown ids dropped
    first = json.loads(route.calls[0].request.content)["messages"]
    assert "Hindi" in first[0]["content"] and "c3 | Mughal" in first[1]["content"]
    assert await brain.rerank("Taj Mahal", cards) == ["c3", "a1", "b2"]
    assert await brain.suggestions("photos") == ["Mughal gardens", "Hampi ruins"]


@respx.mock
async def test_prompts_never_carry_secrets(brain: Brain) -> None:
    brain.settings.github_token = "ghp_secret_value"
    brain.settings.tmdb_key = "tmdb_secret_value"
    route = respx.post(API).mock(return_value=reply({"ids": ["a", "b", "c"]}))
    await brain.rerank("x", [card("a", "A"), card("b", "B"), card("c", "C")])
    sent = route.calls[0].request.content.decode()
    assert "ghp_secret_value" not in sent and "tmdb_secret_value" not in sent


@pytest.fixture
def client(env_settings: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


@respx.mock(assert_all_called=False)
def test_stream_sends_rerank_and_answer(client: TestClient, respx_mock: respx.MockRouter) -> None:
    respx_mock.route(host="testserver").pass_through()
    respx_mock.get(url__startswith="https://archive.org/advancedsearch.php").mock(
        return_value=httpx.Response(
            200,
            json={
                "response": {
                    "numFound": 3,
                    "docs": [
                        {"identifier": i, "title": f"Taj Mahal {i}", "mediatype": "texts"}
                        for i in ("one", "two", "three")
                    ],
                }
            },
        )
    )
    respx_mock.get(url__startswith="https://commons.wikimedia.org").mock(
        return_value=httpx.Response(200, json={"query": {"pages": []}})
    )
    route = respx_mock.post(API)
    route.side_effect = [
        reply({**ROUTER_OK, "queries": [{"source": "archive", "q": "Taj Mahal"}]}),
        reply({"ids": ["archive:three", "archive:one", "archive:two"]}),
        reply({"text": "Shah Jahan built it.", "citations": ["archive:three"]}),
        reply({"queries": ["Nosferatu", "Metropolis"]}),
    ]
    text = client.get("/api/universal", params={"q": "who built the Taj Mahal?"}).text
    names = [
        line.removeprefix("event: ") for line in text.splitlines() if line.startswith("event:")
    ]
    assert names == ["plan", "source", "rerank", "answer", "done"]
    assert '"router": "llm"' in text and "Shah Jahan built it." in text
    status = client.get("/api/llm").json()
    assert status["available"] is True and status["today"]["calls"] == 3
    assert status["daily_limit"] == 500
    suggested = client.get("/api/sections/movies/suggestions").json()
    assert suggested == {"queries": ["Nosferatu", "Metropolis"], "source": "ai"}


@pytest.mark.parametrize(
    ("response", "issue"),
    [
        (httpx.Response(401, json={}), "bad_key"),
        (
            httpx.Response(402, json={"error": {"code": 402, "message": "Insufficient credits"}}),
            "no_credits",
        ),
        (httpx.Response(403, json={}), "refused"),
        (httpx.Response(429, json={}), "rate_limited"),
        (httpx.Response(502, json={}), "provider_error"),
        (httpx.Response(200, json={"error": {"code": 402, "message": "credits"}}), "no_credits"),
    ],
)
@respx.mock
async def test_failures_are_told_apart(brain: Brain, response: httpx.Response, issue: str) -> None:
    route = respx.post(API).mock(return_value=response)
    plan = await brain.plan("who built the Taj Mahal?")
    assert plan.router == "keyword" and plan.queries  # the search still works
    assert brain.issue() == issue
    assert route.call_count == 1  # 429 is not retried with a long back-off


@respx.mock
async def test_no_credits_cools_down_then_recovers(brain: Brain) -> None:
    route = respx.post(API).mock(return_value=httpx.Response(402, json={}))
    await brain.plan("Taj Mahal history")
    await brain.plan("Qutub Minar history")
    assert route.call_count == 1  # no second call while credits are known to be gone
    brain.client.last_issue = None  # e.g. 10 minutes later
    route.mock(return_value=reply(ROUTER_OK))
    assert (await brain.plan("Qutub Minar history")).router == "llm"
    assert brain.issue() is None


@respx.mock(assert_all_called=False)
def test_stream_says_when_ai_could_not_help(
    client: TestClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.route(host="testserver").pass_through()
    respx_mock.get(url__startswith="https://archive.org/advancedsearch.php").mock(
        return_value=httpx.Response(
            200,
            json={
                "response": {
                    "numFound": 1,
                    "docs": [{"identifier": "a", "title": "Taj", "mediatype": "texts"}],
                }
            },
        )
    )
    respx_mock.get(url__startswith="https://commons.wikimedia.org").mock(
        return_value=httpx.Response(200, json={"query": {"pages": []}})
    )
    respx_mock.post(API).mock(return_value=httpx.Response(402, json={}))
    text = client.get("/api/universal", params={"q": "who built the Taj Mahal?"}).text
    assert "event: answer" not in text  # no AI answer card is made up
    assert '"router": "keyword"' in text and '"ai_issue": "no_credits"' in text
    status = client.get("/api/llm").json()
    assert status["issue"] == "no_credits" and KEY not in str(status)
