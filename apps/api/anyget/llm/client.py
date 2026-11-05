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
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from anyget.core.net import BlockedURLError, Net
from anyget.core.settings import Settings
from anyget.llm.store import LlmStore

log = logging.getLogger("anyget.llm")

API = "https://openrouter.ai/api/v1/chat/completions"
T = TypeVar("T", bound=BaseModel)


class LlmUnavailable(Exception):  # noqa: N818 - a state, not an error to report
    """No key, daily limit reached, or no valid answer: use the keyword path."""


class OpenRouter:
    def __init__(self, net: Net, settings: Settings, store: LlmStore) -> None:
        self.net = net
        self.settings = settings
        self.store = store

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
        response = await self.net.request(
            "POST", API, headers=headers, content=json.dumps(body).encode()
        )
        if response.status_code in (401, 402, 403):
            raise LlmUnavailable(f"OpenRouter refused the request ({response.status_code})")
        if response.status_code >= 400:
            raise LlmUnavailable(f"OpenRouter answered {response.status_code}")
        data: dict[str, Any] = response.json()
        return data

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
            raise LlmUnavailable("no OpenRouter key")
        if not self.under_limit():
            raise LlmUnavailable("the daily AI limit is reached")
        schema = answer.model_json_schema()
        body = self._body(models, system, user, answer.__name__, schema)
        for attempt in (1, 2):
            try:
                data = await self._post(body)
            except (httpx.HTTPError, BlockedURLError, ValueError) as exc:
                raise LlmUnavailable(type(exc).__name__) from exc
            self._count(data)
            try:
                content = data["choices"][0]["message"]["content"]
                parsed = answer.model_validate(json.loads(content))
            except (KeyError, IndexError, TypeError, ValueError, ValidationError):
                log.info("%s: answer %d did not match the schema", kind, attempt)
                continue
            if cache:
                self.store.remember(kind, request, parsed.model_dump(mode="json"))
            return parsed
        raise LlmUnavailable("no valid answer")
