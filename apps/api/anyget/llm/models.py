"""Which OpenRouter models AnyGet asks, most preferred first (OpenRouter falls back).

Override with ANYGET_LLM_ROUTER_MODELS / ANYGET_LLM_SUMMARY_MODELS (comma separated).
Free mode keeps only ":free" models. IDs follow the v2 prompt; `anyget llm-models`
checks them against https://openrouter.ai/api/v1/models.
"""

from anyget.core.settings import Settings

# Understanding the input (small JSON answers).
ROUTER = ("google/gemini-2.5-flash-lite", "openai/gpt-5-nano", "google/gemma-4-31b-it:free")
# Answers, suggestions and re-ranking.
SUMMARY = ("google/gemini-3.1-flash-lite", "deepseek/deepseek-v3.2")
# Long documents and OCR clean-up (later), with a free option.
LONG = ("google/gemini-3.1-flash-lite",)
FREE = ("google/gemma-4-31b-it:free", "nvidia/nemotron-3.5-super-vl:free")


def _pick(configured: list[str], default: tuple[str, ...], free_mode: bool) -> list[str]:
    models = list(configured) or list(default)
    if free_mode:
        models = [m for m in models if m.endswith(":free")] or list(FREE)
    return models[:3]  # OpenRouter accepts up to 3 fallback models


def router_models(settings: Settings) -> list[str]:
    return _pick(settings.llm_router_models, ROUTER, settings.llm_free_mode)


def summary_models(settings: Settings) -> list[str]:
    return _pick(settings.llm_summary_models, SUMMARY, settings.llm_free_mode)


def all_models() -> list[str]:
    return sorted({*ROUTER, *SUMMARY, *LONG, *FREE})
