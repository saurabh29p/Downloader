"""OpenRouter's OpenAI-compatible chat API, asked for JSON that matches a schema.

Every call:
- goes through `Net` (SSRF guard, retries on 429/503);
- sends a `models` fallback list and `provider: {require_parameters, sort: latency}`;
- asks for `response_format: json_schema` and validates the answer with Pydantic,
  retrying once before giving up (the caller then falls back to the keyword path);
- is counted per day (calls, tokens, cost) and refused past ANYGET_LLM_DAILY_LIMIT;
- is cached for 24 h by its request.

Prompts carry only what the user typed and result metadata (titles, sources, years):
never cookies, keys or file contents. The key is never logged.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any, Literal, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from anyget.core.net import BlockedURLError, Net
from anyget.core.settings import Settings
from anyget.llm.store import LlmStore

log = logging.getLogger("anyget.llm")

API = "https://openrouter.ai/api/v1/chat/completions"
T = TypeVar("T", bound=BaseModel)


# Why the AI helper did not answer (shown to the user without any secret details).
AiIssue = Literal[
    "no_key",  # no OpenRouter key set
    "bad_key",  # OpenRouter refused the key (401)
    "no_credits",  # the account has no credits left (402)
    "refused",  # OpenRouter refused this request (403, e.g. moderation)
    "rate_limited",  # too many requests right now (429)
    "provider_error",  # OpenRouter or the model provider failed (5xx, timeouts)
    "network",  # OpenRouter could not be reached
    "daily_limit",  # AnyGet's own daily cap (ANYGET_LLM_DAILY_LIMIT)
    "bad_answer",  # two answers that did not match the schema
]


class LlmUnavailable(Exception):  # noqa: N818 - a state, not an error to report
    """No key, daily limit reached, or no valid answer: use the keyword path."""

    def __init__(self, code: AiIssue, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code: AiIssue = code


def _issue_for(status: int) -> AiIssue:
    if status == 401:
        return "bad_key"
    if status == 402:
        return "no_credits"
    if status == 403:
        return "refused"
    if status == 429:
        return "rate_limited"
    return "provider_error"


class OpenRouter:
    def __init__(self, net: Net, settings: Settings, store: LlmStore) -> None:
        self.net = net
        self.settings = settings
        self.store = store
        # The last failure (code, when), cleared by the next good answer.
        self.last_issue: tuple[AiIssue, datetime] | None = None

    @property
    def configured(self) -> bool:
        return bool(self.settings.openrouter_key)

    def under_limit(self) -> bool:
        limit = self.settings.llm_daily_limit
        return limit > 0 and self.store.today().calls < limit

    def _body(
        self, models: list[str], system: str, user: str, name: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "models": models,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": name, "strict": True, "schema": schema},
            },
            "provider": {"require_parameters": True, "sort": "latency"},
            "temperature": 0,
            "usage": {"include": True},
        }

    async def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.app_url,
            "X-Title": "AnyGet",
        }
        # No long back-off on 429: the search goes on without AI instead of waiting.
        response = await self.net.request(
            "POST", API, headers=headers, content=json.dumps(body).encode(), retries=0
        )
        if response.status_code >= 400:
            raise LlmUnavailable(
                _issue_for(response.status_code), f"OpenRouter answered {response.status_code}"
            )
        data: dict[str, Any] = response.json()
        # OpenRouter can answer 200 with an error object (e.g. a provider failure).
        error = data.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            raise LlmUnavailable(
                _issue_for(code if isinstance(code, int) else 502), "error in the answer"
            )
        return data

    def _fail(self, exc: LlmUnavailable) -> LlmUnavailable:
        self.last_issue = (exc.code, datetime.now(UTC))
        return exc

    def _count(self, data: dict[str, Any]) -> None:
        usage = data.get("usage") or {}
        self.store.record(
            int(usage.get("prompt_tokens") or 0),
            int(usage.get("completion_tokens") or 0),
            float(usage.get("cost") or 0.0),
        )

    async def ask(
        self,
        kind: str,
        models: list[str],
        system: str,
        user: str,
        answer: type[T],
        *,
        cache: bool = True,
    ) -> T:
        """A validated `answer`, from the cache or OpenRouter; LlmUnavailable otherwise."""
        request = {"models": models, "system": system, "user": user}
        if cache:
            hit = self.store.cached(kind, request)
            if hit is not None:
                try:
                    return answer.model_validate(hit)
                except ValidationError:
                    pass  # an old shape: ask again
        if not self.configured:
            raise LlmUnavailable("no_key")
        if not self.under_limit():
            raise self._fail(LlmUnavailable("daily_limit"))
        schema = answer.model_json_schema()
        body = self._body(models, system, user, answer.__name__, schema)
        for attempt in (1, 2):
            try:
                data = await self._post(body)
            except LlmUnavailable as exc:
                raise self._fail(exc) from exc
            except httpx.TimeoutException as exc:
                raise self._fail(LlmUnavailable("provider_error", "timeout")) from exc
            except (httpx.HTTPError, BlockedURLError) as exc:
                raise self._fail(LlmUnavailable("network", type(exc).__name__)) from exc
            except ValueError as exc:  # not JSON
                raise self._fail(LlmUnavailable("provider_error", "not JSON")) from exc
            self._count(data)
            try:
                content = data["choices"][0]["message"]["content"]
                parsed = answer.model_validate(json.loads(content))
            except (KeyError, IndexError, TypeError, ValueError, ValidationError):
                log.info("%s: answer %d did not match the schema", kind, attempt)
                continue
            if cache:
                self.store.remember(kind, request, parsed.model_dump(mode="json"))
            self.last_issue = None
            return parsed
        raise self._fail(LlmUnavailable("bad_answer"))
