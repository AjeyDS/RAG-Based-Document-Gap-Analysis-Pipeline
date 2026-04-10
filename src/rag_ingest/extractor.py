"""Extractor module for Document Gap Analysis pipeline."""
from __future__ import annotations

import json

import logging
from src.rag_ingest.llm.base import LLMProvider
from src.rag_ingest.prompts import load_prompt, INGESTION_PROMPT
from src.rag_ingest.exceptions import LLMExtractionError

logger = logging.getLogger(__name__)


class LLMExtractor:
    """Sends full markdown to GPT-4o and returns a structured JSON schema."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_name: str | None = INGESTION_PROMPT,
    ) -> None:
        self.llm_provider = llm_provider
        self.system_prompt = self._load_prompt(prompt_name or INGESTION_PROMPT)

    def _load_prompt(self, prompt_name: str) -> str:
        return load_prompt(prompt_name)

    def extract(self, markdown_text: str) -> dict:
        """Send markdown to GPT-4o and return parsed JSON schema."""
        # If the prompt template contains the literal placeholder `{markdown_content}`,
        # splice the full markdown into the prompt. (The prompt file also contains
        # JSON examples with many braces, so we avoid .format() here.)
        if "{markdown_content}" in self.system_prompt:
            system_prompt = self.system_prompt.replace(
                "{markdown_content}",
                markdown_text,
            )
        else:
            system_prompt = self.system_prompt

        raw_response = self.llm_provider.complete(system_prompt, markdown_text)
        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError:
            logger.error(f"Raw response: {raw_response[:500]}")
            raise LLMExtractionError("Failed to parse LLM response as JSON")

        for key in ["document_title", "stories"]:
            if key not in parsed:
                raise LLMExtractionError(f"LLM response missing required field: {key}")

        if not parsed.get("stories"):
            logger.warning("LLM response contains an empty stories list.")

        return parsed
