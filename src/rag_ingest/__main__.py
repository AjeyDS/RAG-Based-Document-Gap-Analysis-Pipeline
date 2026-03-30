from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from .ingest import Ingestor, dumps
from .store import DEFAULT_COLLECTION, DEFAULT_EMBED_MODEL, VectorStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rag_ingest",
        description="Ingest PDFs and documentation files into a structure-preserving JSON format.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest a file or directory")
    ingest_parser.add_argument("path", help="File or directory to ingest")
    ingest_parser.add_argument(
        "-o",
        "--output",
        help="Optional JSON output path. Prints to stdout when omitted.",
    )

    chunk_parser = subparsers.add_parser(
        "chunk", help="Run LLM extraction and output chunks for a file"
    )
    chunk_parser.add_argument("path", help="File to extract and chunk")
    chunk_parser.add_argument(
        "-o",
        "--output",
        help="Optional JSON output path. Prints to stdout when omitted.",
    )
    chunk_parser.add_argument(
        "--prompt",
        default="./ingestion_prompt.py",
        help="Path to the system prompt file (default: ./ingestion_prompt.py)",
    )
    chunk_parser.add_argument(
        "--llm-model",
        default="gpt-4o",
        help="OpenAI chat model for extraction (default: gpt-4o)",
    )

    store_parser = subparsers.add_parser(
        "store", help="Ingest → LLM extract → chunk → upsert into ChromaDB"
    )
    store_parser.add_argument("path", help="File or directory to ingest and store")
    store_parser.add_argument(
        "--db", default="./chroma_db", help="ChromaDB persist directory (default: ./chroma_db)"
    )
    store_parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION,
        help=f"Collection name (default: {DEFAULT_COLLECTION})",
    )
    store_parser.add_argument(
        "--model",
        default=DEFAULT_EMBED_MODEL,
        help=f"OpenAI embedding model (default: {DEFAULT_EMBED_MODEL})",
    )
    store_parser.add_argument(
        "--prompt",
        default="./ingestion_prompt.py",
        help="Path to the system prompt file (default: ./ingestion_prompt.py)",
    )
    store_parser.add_argument(
        "--llm-model",
        default="gpt-4o",
        help="OpenAI chat model for extraction (default: gpt-4o)",
    )

    query_parser = subparsers.add_parser("query", help="Semantic search over stored chunks")
    query_parser.add_argument("text", help="Query text")
    query_parser.add_argument(
        "--db", default="./chroma_db", help="ChromaDB persist directory (default: ./chroma_db)"
    )
    query_parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION,
        help=f"Collection name (default: {DEFAULT_COLLECTION})",
    )
    query_parser.add_argument(
        "--model",
        default=DEFAULT_EMBED_MODEL,
        help=f"OpenAI embedding model (default: {DEFAULT_EMBED_MODEL})",
    )
    query_parser.add_argument(
        "-n", "--n-results", type=int, default=5, help="Number of results (default: 5)"
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "ingest":
        documents = Ingestor().ingest(args.path)
        payload = dumps(documents)
        if args.output:
            output_path = Path(args.output).expanduser().resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(payload, encoding="utf-8")
        else:
            sys.stdout.write(payload)
            sys.stdout.write("\n")
        return 0

    if args.command == "chunk":
        from .extractor import LLMExtractor
        from .chunking import chunk_document

        extractor = LLMExtractor(model=args.llm_model, prompt_path=args.prompt)
        documents = Ingestor(extractor=extractor).ingest(args.path)
        all_chunks = []
        for doc in documents:
            if doc.extracted_json:
                result = chunk_document(doc.extracted_json)
                all_chunks.append(
                    {
                        "source": doc.source_path,
                        "document_entry": result["document_entry"],
                        "ac_chunks": result["ac_chunks"],
                    }
                )
        payload = json.dumps(all_chunks, indent=2, ensure_ascii=True)
        if args.output:
            output_path = Path(args.output).expanduser().resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(payload, encoding="utf-8")
        else:
            sys.stdout.write(payload)
            sys.stdout.write("\n")
        return 0

    if args.command == "store":
        from .extractor import LLMExtractor
        from .chunking import chunk_document

        extractor = LLMExtractor(model=args.llm_model, prompt_path=args.prompt)
        documents = Ingestor(extractor=extractor).ingest(args.path)
        vs = VectorStore(persist_dir=args.db, collection_name=args.collection, embed_model=args.model)

        total_docs = 0
        total_ac = 0
        for doc in documents:
            if doc.extracted_json is None:
                sys.stderr.write(
                    f"WARNING: LLM extraction returned nothing for {doc.source_path}, skipping.\n"
                )
                continue
            chunks_result = chunk_document(doc.extracted_json)
            counts = vs.add_document_chunks(chunks_result, source_path=doc.source_path)
            total_docs += counts["document_entries"]
            total_ac += counts["ac_chunks"]
            sys.stdout.write(
                f"Stored 1 document entry + {counts['ac_chunks']} AC chunks"
                f" from {doc.source_path}\n"
            )

        sys.stdout.write(
            f"Total: {total_docs} document entries, {total_ac} AC chunks."
            f" Collection size: {vs.count()}\n"
        )
        return 0

    if args.command == "query":
        vs = VectorStore(persist_dir=args.db, collection_name=args.collection, embed_model=args.model)
        hits = vs.query(args.text, n_results=args.n_results)
        sys.stdout.write(json.dumps(hits, indent=2, ensure_ascii=True))
        sys.stdout.write("\n")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
