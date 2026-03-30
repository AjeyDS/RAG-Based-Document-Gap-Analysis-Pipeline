"""
End-to-end pipeline: ingest a file → chunk → embed → store in ChromaDB → inspect as DataFrame.

Usage:
    python inspect_store.py path/to/file.docx
    python inspect_store.py path/to/file.docx --db ./chroma_db --limit 20
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.rag_ingest.ingest import Ingestor
from src.rag_ingest.store import DEFAULT_COLLECTION, DEFAULT_EMBED_MODEL, VectorStore


def run(file_path: str, db_dir: str, limit: int) -> None:
    path = Path(file_path).expanduser().resolve()
    print(f"\n--- Ingesting: {path.name} ---")

    documents = Ingestor().ingest(path)
    vs = VectorStore(persist_dir=db_dir)

    total = 0
    for doc in documents:
        added = vs.add_chunks(doc.chunks, source_path=str(path))
        total += added
        print(f"  Stored {added} chunks  |  title: {doc.title}")

    print(f"\nCollection '{DEFAULT_COLLECTION}' total size: {vs.count()} chunks\n")

    print(f"--- DataFrame preview (first {limit} rows) ---")
    df = vs.peek_df(limit=limit)

    # Show all columns except the full embedding vector
    display_cols = ["chunk_id", "parent_context", "source", "text"]
    print(df[display_cols].to_string(index=False, max_colwidth=80))

    print(f"\n--- Embedding shape: {len(df['embedding'].iloc[0])} dimensions ---")
    print(df[["chunk_id", "embedding"]].head(3).to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest file and inspect ChromaDB contents")
    parser.add_argument("path", help="File to ingest")
    parser.add_argument("--db", default="./chroma_db", help="ChromaDB directory (default: ./chroma_db)")
    parser.add_argument("--limit", type=int, default=10, help="Max rows to preview (default: 10)")
    args = parser.parse_args()

    run(args.path, args.db, args.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
