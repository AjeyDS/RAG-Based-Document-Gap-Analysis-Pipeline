"""Config module for Document Gap Analysis pipeline."""
from pydantic_settings import BaseSettings, SettingsConfigDict

class Config(BaseSettings):
    # Database
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_database: str = "rag_gap"
    pg_user: str = "postgres"
    pg_password: str
    pg_pool_min: int = 1
    pg_pool_max: int = 10

    # LLM (legacy globals = defaults when per-use-case fields are unset)
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_base_url: str | None = None
    # Per-use-case overrides (None = inherit from llm_model / llm_base_url above)
    llm_ingestion_model: str | None = None
    llm_ingestion_base_url: str | None = None
    llm_comparison_model: str | None = None
    llm_comparison_base_url: str | None = None
    llm_chat_model: str | None = None
    llm_chat_base_url: str | None = None
    llm_max_tokens: int = 16384
    llm_temperature: float = 0.0
    llm_seed: int = 42
    openai_api_key: str

    # Embeddings
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_batch_size: int = 100

    # Vector Search
    ivfflat_lists: int = 100
    search_top_k: int = 5

    # Retry
    max_retries: int = 3
    retry_backoff_multiplier: float = 1.0
    retry_max_wait: int = 30

    # Paths
    data_dir: str = "data"
    upload_dir: str = "data/uploads/kb"
    metadata_file: str = "data/kb_metadata.json"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Config()
