import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from rag_ingest.ingest import Ingestor
from rag_ingest.extractor import LLMExtractor
from rag_ingest.chunking import chunk_document

docx_path = Path("/Users/ajeyds/Projects/Doc Gap Analysis/data/uploads/kb/bdc38fa7-a1ab-413d-9923-65754b4723be_Rise User Stories.docx")

if not docx_path.exists():
    print("FILE NOT FOUND")
    exit(1)

extractor = LLMExtractor(
    model=os.environ.get("LLM_MODEL", "gpt-4o"),
    prompt_path=str(Path("ingestion_prompt.py").resolve()),
)
ingestor = Ingestor(extractor=extractor)

print(f"File size: {docx_path.stat().st_size} bytes")

documents = ingestor.ingest(docx_path)
for doc in documents:
    print(f"Extracted markdown length: {len(doc.text)}")
    print(f"Extracted json keys: {doc.extracted_json.keys() if doc.extracted_json else None}")
    chunks = chunk_document(doc.extracted_json)
    print(f"Number of AC chunks: {len(chunks['ac_chunks'])}")
    print("Extracted stories from JSON:", doc.extracted_json.get("stories", []))
