"""Main Entrypoint module for Document Gap Analysis pipeline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # noqa: E402

from .ingest import Ingestor, dumps
from .store import VectorStore
from src.config import settings
from src.rag_ingest.llm import create_llm, create_embedding_provider
from src.rag_ingest.pipeline import IngestionPipeline
from src.logging_config import setup_logging


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
        "store", help="Ingest → LLM extract → chunk → upsert into pgvector"
    )
    store_parser.add_argument("path", help="File or directory to ingest and store")
    store_parser.add_argument(
        "--db-url", default=None, help="PostgreSQL connection string (default: from .env)"
    )
    store_parser.add_argument(
        "--model",
        default=settings.embedding_model,
        help=f"OpenAI embedding model (default: {settings.embedding_model})",
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
        "--db-url", default=None, help="PostgreSQL connection string (default: from .env)"
    )
    query_parser.add_argument(
        "--model",
        default=settings.embedding_model,
        help=f"OpenAI embedding model (default: {settings.embedding_model})",
    )
    query_parser.add_argument(
        "-n", "--n-results", type=int, default=5, help="Number of results (default: 5)"
    )

    return parser


def main() -> int:
    setup_logging()
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "ingest":
        pipeline = IngestionPipeline(ingestor=Ingestor())
        documents = pipeline.run_partial(args.path, through="ingest")
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
        llm = create_llm(settings)
        extractor = LLMExtractor(llm_provider=llm, prompt_name=args.prompt)
        pipeline = IngestionPipeline(ingestor=Ingestor(), extractor=extractor)
        all_chunks = pipeline.run_partial(args.path, through="chunk")
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
        llm = create_llm(settings)
        embed_provider = create_embedding_provider(settings)
        extractor = LLMExtractor(llm_provider=llm, prompt_name=args.prompt)
        vs = VectorStore(embedding_provider=embed_provider, settings=settings)
        
        pipeline = IngestionPipeline(ingestor=Ingestor(), extractor=extractor, store=vs)
        results = pipeline.run_partial(args.path, through="store")

        total_stories = 0
        total_ac = 0
        for res in results:
            counts = res["counts"]
            total_stories += counts["story_chunks"]
            total_ac += counts["ac_chunks"]
            sys.stdout.write(
                f"Stored {counts['story_chunks']} story chunks + {counts['ac_chunks']} AC chunks "
                f"from {res['source']}\n"
            )

        sys.stdout.write(
            f"Total: {total_stories} story chunks, {total_ac} AC chunks. "
            f"Store size: {vs.count()}\n"
        )
        return 0

    if args.command == "query":
        embed_provider = create_embedding_provider(settings)
        vs = VectorStore(embedding_provider=embed_provider, settings=settings)
        hits = vs.query_stories(args.text, top_k=args.n_results)
        sys.stdout.write(json.dumps(hits, indent=2, ensure_ascii=True))
        sys.stdout.write("\n")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
