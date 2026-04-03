from __future__ import annotations

import json
import os
from pathlib import Path

from openai import OpenAI

DEFAULT_MODEL = "gpt-4o"


class LLMExtractor:
    """Sends full markdown to GPT-4o and returns a structured JSON schema."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        prompt_path: str | Path | None = None,
    ) -> None:
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not resolved_key:
            raise ValueError(
                "OpenAI API key required. Pass api_key= or set OPENAI_API_KEY."
            )
        self.client = OpenAI(api_key=resolved_key)
        self.model = model
        self.system_prompt = self._load_prompt(prompt_path)

    def _load_prompt(self, prompt_path: str | Path | None) -> str:
        if prompt_path:
            return Path(prompt_path).expanduser().resolve().read_text(encoding="utf-8")
        # Default: look for ingestion_prompt.py in cwd, then walk up to find it.
        # (Also support the legacy prompt.txt name.)
        for candidate in [
            Path.cwd() / "ingestion_prompt.py",
            Path(__file__).parent.parent.parent / "ingestion_prompt.py",
            Path.cwd() / "prompt.txt",
            Path(__file__).parent.parent.parent / "prompt.txt",
        ]:
            if candidate.exists():
                return candidate.read_text(encoding="utf-8")
        raise FileNotFoundError(
            "Prompt file not found. Pass prompt_path= or place ingestion_prompt.py (or legacy prompt.txt) in the project root."
        )

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
            messages = [{"role": "system", "content": system_prompt}]
        else:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": markdown_text},
            ]

        response = self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=messages,
            max_tokens=16384,
        )
        raw = response.choices[0].message.content
        return json.loads(raw)
