"""Pipeline module for Document Gap Analysis pipeline."""
import logging
import time
from pathlib import Path
from typing import Callable, Any

from src.rag_ingest.ingest import Ingestor
from src.rag_ingest.extractor import LLMExtractor
from src.rag_ingest.store import VectorStore
from src.rag_ingest.chunking import chunk_for_storage
from src.rag_ingest.exceptions import (
    IngestionError,
    DocumentParsingError,
    LLMExtractionError,
    StorageError,
)

logger = logging.getLogger(__name__)

class IngestionPipeline:
    def __init__(
        self, 
        ingestor: Ingestor, 
        extractor: "LLMExtractor | None" = None, 
        store: "VectorStore | None" = None
    ):
        self.ingestor = ingestor
        self.extractor = extractor
        self.store = store

    def run(self, file_path: Path, on_status: Callable[[str], None] | None = None) -> dict:
        """
        Full pipeline: ingest -> extract -> chunk -> embed -> store.
        
        on_status callback receives stage names: "docling", "llm", "chunking", "embedding", "ready", "error"
        
        Returns the extracted JSON dict.
        
        On any exception:
          - calls on_status("error") if callback provided
          - logs the full traceback with logger.exception()
          - re-raises the exception
        """
        current_stage = "init"
        def trigger(status: str):
            nonlocal current_stage
            current_stage = status
            logger.info("Pipeline stage started", extra={"stage": status, "file_name": file_path.name})
            if on_status:
                on_status(status)

        start_time = time.time()
        # Temporary intercept ingestor extraction behavior as pipeline actively directs it
        old_extractor = self.ingestor.extractor
        self.ingestor.extractor = None

        try:
            trigger("docling")
            try:
                documents = self.ingestor.ingest(file_path)
                if not documents:
                    raise DocumentParsingError("No documents were produced by the ingestor.")
                doc = documents[0]
            except Exception as e:
                if isinstance(e, IngestionError):
                    raise
                raise DocumentParsingError("Failed during document parsing") from e
            
            trigger("llm")
            try:
                if not self.extractor:
                    raise ValueError("Extractor not provided to IngestionPipeline")
                extracted_json = self.extractor.extract(doc.text)
                doc.extracted_json = extracted_json
            except Exception as e:
                if isinstance(e, IngestionError):
                    raise
                raise LLMExtractionError("Failed during LLM extraction") from e
            
            trigger("chunking")
            chunks_result = chunk_for_storage(extracted_json)
            
            trigger("embedding")
            try:
                if not self.store:
                    raise ValueError("Store not provided to IngestionPipeline")
                self.store.add_document_chunks(chunks_result, str(file_path))
            except Exception as e:
                if isinstance(e, IngestionError):
                    raise
                raise StorageError("Failed during embedding or storage") from e
            
            trigger("ready")
            duration = time.time() - start_time
            logger.info("Pipeline completed", extra={"file_name": file_path.name, "duration_seconds": round(duration, 2)})
            return extracted_json
            
        except Exception as e:
            trigger("error")
            logger.exception("IngestionPipeline failed execution", extra={"stage": current_stage, "file_name": file_path.name})
            raise e
        finally:
            self.ingestor.extractor = old_extractor

    def run_partial(self, file_path: Path, through: str = "chunk") -> Any:
        """
        Run pipeline up to a specific stage. Useful for CLI commands.
        through: "ingest" | "extract" | "chunk" | "store"
        Returns whatever data is available at that stage.
        """
        old_extractor = self.ingestor.extractor
        self.ingestor.extractor = None
        
        try:
            documents = self.ingestor.ingest(file_path)
            if through == "ingest":
                return documents
                
            results = []
            for doc in documents:
                if not self.extractor:
                    raise ValueError("Extractor dependency missing for this stage.")
                    
                extracted_json = self.extractor.extract(doc.text)
                doc.extracted_json = extracted_json
                if through == "extract":
                    results.append(extracted_json)
                    continue
                    
                chunks = chunk_for_storage(extracted_json)
                if through == "chunk":
                    results.append({
                        "source": doc.source_path,
                        "story_chunks": chunks.get("story_chunks", []),
                        "ac_chunks": chunks.get("ac_chunks", [])
                    })
                    continue
                    
                if through == "store":
                    if not self.store:
                        raise ValueError("Store dependency missing for this stage.")
                    counts = self.store.add_document_chunks(chunks, doc.source_path)
                    results.append({
                        "source": doc.source_path,
                        "counts": counts
                    })
                    
            return results
        finally:
            self.ingestor.extractor = old_extractor
