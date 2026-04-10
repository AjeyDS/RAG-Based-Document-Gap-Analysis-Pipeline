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

    # LLM
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_max_tokens: int = 16384
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
