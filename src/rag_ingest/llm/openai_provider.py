"""Openai Provider module for Document Gap Analysis pipeline."""
import logging
import time
import openai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, RetryError

from src.config import Config
from .base import LLMProvider, EmbeddingProvider

from src.rag_ingest.exceptions import LLMExtractionError, EmbeddingError

logger = logging.getLogger(__name__)

class OpenAILLM(LLMProvider):
    def __init__(self, settings: Config):
        self.settings = settings
        self.api_key = settings.openai_api_key
        self.client = openai.OpenAI(api_key=self.api_key)

    def complete(self, system_prompt: str, user_content: str) -> str:
        @retry(
            retry=retry_if_exception_type((openai.RateLimitError, openai.APITimeoutError)),
            wait=wait_exponential(multiplier=self.settings.retry_backoff_multiplier, max=self.settings.retry_max_wait),
            stop=stop_after_attempt(self.settings.max_retries),
            before_sleep=lambda retry_state: logger.warning(
                "Retrying LLM complete", 
                extra={
                    "attempt": retry_state.attempt_number, 
                    "error_type": type(retry_state.outcome.exception()).__name__
                }
            ),
            reraise=True
        )
        def _call_api():
            response = self.client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                max_tokens=self.settings.llm_max_tokens,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            return content

        try:
            start_time = time.time()
            content = _call_api()
            duration = time.time() - start_time
            logger.info(
                "LLM call completed",
                extra={
                    "model": self.settings.llm_model,
                    "estimated_input_tokens": len(system_prompt + user_content) // 4,
                    "response_time_seconds": round(duration, 2)
                }
            )
            return content
        except RetryError as e:
            raise LLMExtractionError("LLM API exhausted retries") from e.last_attempt.exception()

class OpenAIEmbedding(EmbeddingProvider):
    def __init__(self, settings: Config):
        self.settings = settings
        self.api_key = settings.openai_api_key
        self.client = openai.OpenAI(api_key=self.api_key)
        self._dimensions = settings.embedding_dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        @retry(
            retry=retry_if_exception_type((openai.RateLimitError, openai.APITimeoutError)),
            wait=wait_exponential(multiplier=self.settings.retry_backoff_multiplier, max=self.settings.retry_max_wait),
            stop=stop_after_attempt(self.settings.max_retries),
            before_sleep=lambda retry_state: logger.warning(
                "Retrying Embedding", 
                extra={
                    "attempt": retry_state.attempt_number, 
                    "error_type": type(retry_state.outcome.exception()).__name__
                }
            ),
            reraise=True
        )
        def _call_api_batch(batch_texts: list[str]):
            response = self.client.embeddings.create(
                model=self.settings.embedding_model,
                input=batch_texts,
                dimensions=self.settings.embedding_dimensions
            )
            # Ensure order matches identical response ordering
            sorted_data = sorted(response.data, key=lambda x: x.index)
            return [d.embedding for d in sorted_data]

        all_embeddings = []
        batch_size = self.settings.embedding_batch_size
        total_texts = len(texts)

        try:
            for i in range(0, total_texts, batch_size):
                batch = texts[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (total_texts + batch_size - 1) // batch_size
                
                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} texts) out of {total_texts} total texts.")
                start_time = time.time()
                batch_embeddings = _call_api_batch(batch)
                duration = time.time() - start_time
                all_embeddings.extend(batch_embeddings)
                
                logger.info(
                    "Embedding batch completed",
                    extra={
                        "batch_number": batch_num,
                        "text_count": len(batch),
                        "response_time_seconds": round(duration, 2)
                    }
                )
        except RetryError as e:
            raise EmbeddingError("Embedding API exhausted retries") from e.last_attempt.exception()

        return all_embeddings
