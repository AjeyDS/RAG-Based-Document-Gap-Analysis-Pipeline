"""Factory module for Document Gap Analysis pipeline."""
from src.config import Config
from .base import LLMProvider, EmbeddingProvider
from .openai_provider import OpenAILLM, OpenAIEmbedding

def create_llm(settings: Config) -> LLMProvider:
    provider_name = settings.llm_provider.lower()
    if provider_name == "openai":
        return OpenAILLM(settings)
    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}. Supported: openai")

def create_embedding_provider(settings: Config) -> EmbeddingProvider:
    provider_name = settings.embedding_provider.lower()
    if provider_name == "openai":
        return OpenAIEmbedding(settings)
    else:
        raise ValueError(f"Unknown Embedding provider: {provider_name}. Supported: openai")
