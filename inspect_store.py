"""
End-to-end pipeline: ingest a file → chunk → embed → store in pgvector → inspect.

Usage:
    python inspect_store.py path/to/file.docx
    python inspect_store.py path/to/file.docx --db-url "postgresql://..." --limit 20
"""
from __future__ import annotations

import argparse
import sys
import os
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.rag_ingest.ingest import Ingestor
from src.rag_ingest.extractor import LLMExtractor
from src.rag_ingest.chunking import chunk_for_storage
from src.rag_ingest.store import VectorStore


def run(file_path: str, db_url: str | None, limit: int) -> None:
    path = Path(file_path).expanduser().resolve()
    print(f"\n--- Ingesting: {path.name} ---")

    extractor = LLMExtractor()
    documents = Ingestor(extractor=extractor).ingest(path)
    vs = VectorStore(db_url=db_url)

    for doc in documents:
        if not doc.extracted_json:
            print(f"  Skipping {doc.title}: No extracted JSON")
            continue
        chunks_result = chunk_for_storage(doc.extracted_json)
        counts = vs.add_document_chunks(chunks_result, source_path=str(path))
        print(f"  Stored {counts['story_chunks']} story chunks + {counts['ac_chunks']} AC chunks | title: {doc.title}")

    print(f"\nStore total size: {vs.count()} chunks\n")

    print(f"--- Recent chunks (limit {limit}) ---")
    # Using my new query_stories as a proxy for "show me stuff"
    # Actually, let's just query a generic term or print count
    print(f"Total chunks in 'document_chunks' table: {vs.count()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest file and inspect pgvector contents")
    parser.add_argument("path", help="File to ingest")
    parser.add_argument("--db-url", default=None, help="PostgreSQL connection string")
    parser.add_argument("--limit", type=int, default=10, help="Max rows to preview (default: 10)")
    args = parser.parse_args()

    run(args.path, args.db_url, args.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
