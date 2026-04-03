import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from rag_ingest.ingest import Ingestor
from rag_ingest.extractor import LLMExtractor
from rag_ingest.chunking import chunk_document
from rag_ingest.store import VectorStore

_ROOT = Path(__file__).resolve().parent
DATA_DIR = _ROOT / "data"
CHROMA_DIR = DATA_DIR / "chroma_db"

docx_path = Path("/Users/ajeyds/Projects/Doc Gap Analysis/data/uploads/kb/bdc38fa7-a1ab-413d-9923-65754b4723be_Rise User Stories.docx")

extractor = LLMExtractor(
    model=os.environ.get("LLM_MODEL", "gpt-4o"),
    prompt_path=str(_ROOT / "ingestion_prompt.py"),
)
ingestor = Ingestor(extractor=extractor)
vs = VectorStore(persist_dir=CHROMA_DIR)

documents = ingestor.ingest(docx_path)
for doc in documents:
    chunks_result = chunk_document(doc.extracted_json)
    try:
        vs.add_document_chunks(chunks_result, source_path=str(docx_path))
        print("ADDED SUCCESSFULLY")
    except Exception as e:
        print("ERROR IN ADD_DOCUMENT_CHUNKS:", e)
        
print("DB count now:", vs.count())
