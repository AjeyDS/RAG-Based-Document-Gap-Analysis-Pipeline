"""Base module for Document Gap Analysis pipeline."""
from typing import Protocol

class LLMProvider(Protocol):
    def complete(self, system_prompt: str, user_content: str) -> str:
        """Generate a structured JSON response from the LLM (as string)."""
        ...

class EmbeddingProvider(Protocol):
    @property
    def dimensions(self) -> int:
        """The total number of dimensions in generated embeddings."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of strings."""
        ...
