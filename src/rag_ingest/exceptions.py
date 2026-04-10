"""Exceptions module for Document Gap Analysis pipeline."""
class IngestionError(Exception):
    """Base exception for all pipeline errors."""
    pass

class DocumentParsingError(IngestionError):
    """Docling failures."""
    pass

class LLMExtractionError(IngestionError):
    """LLM returned invalid/unparseable response."""
    pass

class EmbeddingError(IngestionError):
    """Embedding API failure after retries exhausted."""
    pass

class StorageError(IngestionError):
    """pgvector/database errors."""
    pass

class GapAnalysisError(IngestionError):
    """Gap analysis prompt failures."""
    pass
