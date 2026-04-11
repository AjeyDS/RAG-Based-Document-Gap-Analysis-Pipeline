"""App module for Document Gap Analysis pipeline."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.logging_config import setup_logging
from src.rag_api.routes import knowledge_base, documents, gaps, auth, chat
from src.rag_ingest.exceptions import (
    DocumentParsingError,
    LLMExtractionError,
    StorageError,
    GapAnalysisError
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield

app = FastAPI(title="RAG API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(DocumentParsingError)
async def document_parsing_exception_handler(request: Request, exc: DocumentParsingError):
    return JSONResponse(
        status_code=422,
        content={"error": "DocumentParsingError", "message": str(exc)},
    )

@app.exception_handler(LLMExtractionError)
async def llm_extraction_exception_handler(request: Request, exc: LLMExtractionError):
    return JSONResponse(
        status_code=502,
        content={"error": "LLMExtractionError", "message": str(exc)},
    )

@app.exception_handler(StorageError)
async def storage_exception_handler(request: Request, exc: StorageError):
    return JSONResponse(
        status_code=503,
        content={"error": "StorageError", "message": str(exc)},
    )

@app.exception_handler(GapAnalysisError)
async def gap_analysis_exception_handler(request: Request, exc: GapAnalysisError):
    return JSONResponse(
        status_code=502,
        content={"error": "GapAnalysisError", "message": str(exc)},
    )

app.include_router(knowledge_base.router)
app.include_router(documents.router)
app.include_router(gaps.router)
app.include_router(auth.router)
app.include_router(chat.router)
