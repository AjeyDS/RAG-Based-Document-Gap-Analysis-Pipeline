"""Runtime LLM settings (in-memory; not persisted to .env)."""
from __future__ import annotations

import logging
import time
from typing import Literal

import openai
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.rag_api.dependencies import get_current_user, get_settings
from src.rag_ingest.llm.resolve import resolve_llm_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

_LLM_URL_KEYS = frozenset(
    {
        "llm_base_url",
        "llm_ingestion_base_url",
        "llm_comparison_base_url",
        "llm_chat_base_url",
    }
)


class SettingsUpdate(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    llm_ingestion_model: str | None = None
    llm_ingestion_base_url: str | None = None
    llm_comparison_model: str | None = None
    llm_comparison_base_url: str | None = None
    llm_chat_model: str | None = None
    llm_chat_base_url: str | None = None


def _settings_payload(settings) -> dict:
    return {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "llm_base_url": settings.llm_base_url,
        "llm_ingestion_model": settings.llm_ingestion_model,
        "llm_ingestion_base_url": settings.llm_ingestion_base_url,
        "llm_comparison_model": settings.llm_comparison_model,
        "llm_comparison_base_url": settings.llm_comparison_base_url,
        "llm_chat_model": settings.llm_chat_model,
        "llm_chat_base_url": settings.llm_chat_base_url,
    }


@router.get("/")
def get_current_settings(settings=Depends(get_settings), user: dict = Depends(get_current_user)):
    return _settings_payload(settings)


@router.post("/")
def update_settings(update: SettingsUpdate, settings=Depends(get_settings), user: dict = Depends(get_current_user)):
    patch = update.model_dump(exclude_unset=True)
    if "llm_provider" in patch and patch["llm_provider"] is not None:
        settings.llm_provider = patch["llm_provider"]
    if "llm_model" in patch and patch["llm_model"] is not None:
        m = str(patch["llm_model"]).strip()
        if m:
            settings.llm_model = m
    for key in _LLM_URL_KEYS:
        if key not in patch:
            continue
        v = patch[key]
        setattr(settings, key, v if (v is not None and str(v).strip()) else None)
    for key in ("llm_ingestion_model", "llm_comparison_model", "llm_chat_model"):
        if key not in patch:
            continue
        v = patch[key]
        if v is None:
            setattr(settings, key, None)
        else:
            m = str(v).strip()
            setattr(settings, key, m if m else None)

    return {"status": "success", "settings": _settings_payload(settings)}


class PingRequest(BaseModel):
    target: Literal["ingestion", "comparison", "chat"] = Field(
        ...,
        description="Which resolved LLM endpoint to probe",
    )


@router.post("/ping")
def ping_llm_endpoint(
    req: PingRequest,
    settings=Depends(get_settings),
    user: dict = Depends(get_current_user),
) -> dict:
    """Check reachability of the resolved OpenAI-compatible endpoint for ``target``."""
    model, base_url = resolve_llm_connection(settings, req.target)
    kwargs: dict = {"api_key": settings.openai_api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = openai.OpenAI(**kwargs)

    t0 = time.perf_counter()

    def _latency() -> int:
        return int((time.perf_counter() - t0) * 1000)

    try:
        client.models.list()
        return {
            "ok": True,
            "latency_ms": _latency(),
            "detail": f"Endpoint reachable (models.list), model={model!r}",
            "model": model,
            "base_url": base_url,
        }
    except Exception as first_err:
        logger.debug("settings ping models.list failed: %s", first_err)
        t0 = time.perf_counter()
        try:
            client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Reply with exactly: ok"},
                    {"role": "user", "content": "ping"},
                ],
                max_tokens=4,
                temperature=0,
            )
            return {
                "ok": True,
                "latency_ms": _latency(),
                "detail": f"Endpoint reachable (chat completion), model={model!r}",
                "model": model,
                "base_url": base_url,
            }
        except Exception as err:
            return {
                "ok": False,
                "latency_ms": _latency(),
                "error": str(err),
                "model": model,
                "base_url": base_url,
            }
