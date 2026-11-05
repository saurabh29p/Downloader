"""The optional AI helper's state: GET /api/llm (key set, today's use, limit, models)."""

from fastapi import APIRouter
from pydantic import BaseModel

from anyget.api.deps import ServicesDep
from anyget.llm.models import router_models, summary_models

router = APIRouter(tags=["llm"])


class LlmToday(BaseModel):
    calls: int
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float  # as OpenRouter reports it; free models cost 0


class LlmStatus(BaseModel):
    available: bool  # an OpenRouter key is set (env or Connections)
    free_mode: bool
    daily_limit: int
    today: LlmToday
    router_models: list[str]
    summary_models: list[str]


@router.get("/llm", operation_id="llmStatus")
async def llm_status(services: ServicesDep) -> LlmStatus:
    s = services.settings
    today = services.brain.client.store.today()
    return LlmStatus(
        available=bool(s.openrouter_key),
        free_mode=s.llm_free_mode,
        daily_limit=s.llm_daily_limit,
        today=LlmToday(
            calls=today.calls,
            prompt_tokens=today.prompt_tokens,
            completion_tokens=today.completion_tokens,
            cost_usd=round(today.cost_usd, 6),
        ),
        router_models=router_models(s),
        summary_models=summary_models(s),
    )
