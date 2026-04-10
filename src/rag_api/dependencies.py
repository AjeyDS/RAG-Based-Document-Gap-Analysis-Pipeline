"""Dependencies module for Document Gap Analysis pipeline."""
from functools import lru_cache
from pathlib import Path

from src.config import Config, settings
from src.rag_ingest.store import VectorStore
from src.rag_ingest.llm import create_embedding_provider, create_llm, LLMProvider
from src.rag_ingest.extractor import LLMExtractor
from src.rag_ingest.pipeline import IngestionPipeline
from src.rag_ingest.ingest import Ingestor
from src.rag_ingest.prompts import INGESTION_PROMPT
from fastapi import Request, HTTPException, Depends
from src.rag_api.auth import validate_session

_ROOT = Path(__file__).resolve().parents[2]

@lru_cache()
def get_settings() -> Config:
    return settings

@lru_cache()
def get_vector_store() -> VectorStore:
    s = get_settings()
    provider = create_embedding_provider(s)
    return VectorStore(embedding_provider=provider, settings=s)

def get_llm() -> LLMProvider:
    s = get_settings()
    return create_llm(s)
def get_pipeline() -> IngestionPipeline:
    vs = get_vector_store()
    llm = get_llm()
    extractor = LLMExtractor(
        llm_provider=llm,
        prompt_name=INGESTION_PROMPT,
    )
    ingestor = Ingestor()
    return IngestionPipeline(ingestor=ingestor, extractor=extractor, store=vs)

def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth_header.split(" ")[1]
    user = validate_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
