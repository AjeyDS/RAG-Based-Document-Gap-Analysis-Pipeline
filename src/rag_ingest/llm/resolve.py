"""Resolve per-use-case LLM model and base URL from Config with legacy fallbacks."""
from __future__ import annotations

from typing import Literal

from src.config import Config

LLMUseCase = Literal["ingestion", "comparison", "chat"]


def resolve_llm_connection(settings: Config, use_case: LLMUseCase) -> tuple[str, str | None]:
    """Return (model, base_url) for the use case.

    Per-use-case fields override legacy ``llm_model`` / ``llm_base_url`` when set.
    - Model: empty or missing override → ``settings.llm_model``.
    - Base URL: ``None`` on override → inherit ``settings.llm_base_url``.
      Explicit empty string → ``None`` (official OpenAI endpoint for that feature).
    """
    if use_case == "ingestion":
        model_override = settings.llm_ingestion_model
        url_override = settings.llm_ingestion_base_url
    elif use_case == "comparison":
        model_override = settings.llm_comparison_model
        url_override = settings.llm_comparison_base_url
    else:
        model_override = settings.llm_chat_model
        url_override = settings.llm_chat_base_url

    model = (model_override or "").strip() or settings.llm_model

    if url_override is None:
        base_url = settings.llm_base_url
    else:
        stripped = url_override.strip()
        base_url = None if not stripped else stripped

    return model, base_url
