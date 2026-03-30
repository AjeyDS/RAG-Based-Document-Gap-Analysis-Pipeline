from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

from .models import Chunk

DEFAULT_COLLECTION = "rag_chunks"
DEFAULT_EMBED_MODEL = "text-embedding-3-small"

_ALLOWED_META_TYPES = (str, int, float, bool)


def _sanitise_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    """Strip None values and coerce unsupported types to str for ChromaDB."""
    sanitised: dict[str, Any] = {}
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, _ALLOWED_META_TYPES):
            sanitised[k] = v
        else:
            sanitised[k] = str(v)
    return sanitised


def _chunk_id(source_path: str, chunk_id: str) -> str:
    """Stable unique ID scoped to source file + chunk_id."""
    raw = f"{source_path}::{chunk_id}"
    return hashlib.sha256(raw.encode()).hexdigest()


class VectorStore:
    def __init__(
        self,
        persist_dir: str | Path,
        openai_api_key: str | None = None,
        collection_name: str = DEFAULT_COLLECTION,
        embed_model: str = DEFAULT_EMBED_MODEL,
    ) -> None:
        api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key required. Pass openai_api_key= or set OPENAI_API_KEY."
            )
        self.client = chromadb.PersistentClient(path=str(persist_dir))
        embedding_fn = OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name=embed_model,
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_fn,
        )

    def add_chunks(self, chunks: list[Chunk], source_path: str = "") -> int:
        """Embed and upsert chunks into the collection. Returns number added."""
        if not chunks:
            return 0
        self.collection.upsert(
            ids=[_chunk_id(source_path, chunk.chunk_id) for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            metadatas=[
                {
                    "chunk_id": chunk.chunk_id,
                    "parent_context": chunk.parent_context,
                    "source": source_path,
                }
                for chunk in chunks
            ],
        )
        return len(chunks)

    def query(
        self, query_text: str, n_results: int = 5
    ) -> list[dict]:
        """Return top-n matching chunks with metadata and distances."""
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        hits = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            hits.append(
                {
                    "chunk_id": meta["chunk_id"],
                    "parent_context": meta["parent_context"],
                    "source": meta["source"],
                    "distance": dist,
                    "text": doc,
                }
            )
        return hits

    def add_document_chunks(
        self,
        chunks_result: dict[str, Any],
        source_path: str = "",
    ) -> dict[str, int]:
        """
        Store the output of chunk_document() into ChromaDB.

        Expects:
            {
                "document_entry": { "text": ..., "metadata": {...} },
                "ac_chunks":      [ { "text": ..., "metadata": {...} }, ... ]
            }

        Returns a dict with "document_entries" and "ac_chunks" counts.
        """
        document_entry = chunks_result["document_entry"]
        ac_chunks = chunks_result["ac_chunks"]

        # ── Document-level entry ──────────────────────────────────────────────
        doc_meta = _sanitise_metadata(document_entry["metadata"])
        doc_meta["source"] = source_path
        doc_meta["chunk_type"] = "document"
        # Keep metadata shape consistent with `add_chunks()` so query helpers work.
        doc_meta["chunk_id"] = "document_entry"
        doc_meta["parent_context"] = doc_meta.get("document_title", "document")
        self.collection.upsert(
            ids=[_chunk_id(source_path, "document_entry")],
            documents=[document_entry["text"]],
            metadatas=[doc_meta],
        )

        # ── AC-level chunks ───────────────────────────────────────────────────
        if ac_chunks:
            ids, docs, metas = [], [], []
            seen_keys: dict[str, int] = {}
            for ac in ac_chunks:
                ac_id_val = ac["metadata"].get("ac_id", "unknown")
                story_id = ac["metadata"].get("story_id", "")
                # Build a key that is unique per story + AC to avoid hash collisions
                # when the LLM returns the same ac_id under different stories.
                raw_key = f"ac::{story_id}::{ac_id_val}"
                count = seen_keys.get(raw_key, 0)
                seen_keys[raw_key] = count + 1
                if count > 0:
                    raw_key = f"{raw_key}::{count}"
                meta = _sanitise_metadata(ac["metadata"])
                meta["source"] = source_path
                meta["chunk_type"] = "ac"
                meta["chunk_id"] = ac_id_val
                meta["parent_context"] = meta.get("story_title") or meta.get(
                    "story_id", "story"
                )
                ids.append(_chunk_id(source_path, raw_key))
                docs.append(ac["text"])
                metas.append(meta)
            self.collection.upsert(ids=ids, documents=docs, metadatas=metas)

        return {"document_entries": 1, "ac_chunks": len(ac_chunks)}

    def count(self) -> int:
        return self.collection.count()

    def delete_by_source(self, source_path: str) -> int:
        """Delete all chunks for a given source file. Returns count deleted."""
        result = self.collection.get(where={"source": source_path}, include=[])
        ids = result["ids"]
        if ids:
            self.collection.delete(ids=ids)
        return len(ids)

    def get_chunks_by_source(self, source_path: str) -> list[dict]:
        """Return all stored chunks for a given source file."""
        result = self.collection.get(
            where={"source": source_path},
            include=["documents", "metadatas"],
        )
        return [
            {
                "chunk_id": meta["chunk_id"],
                "parent_context": meta["parent_context"],
                "text": doc,
            }
            for doc, meta in zip(result["documents"], result["metadatas"])
        ]

    def peek_df(self, limit: int | None = None):
        """Return all stored chunks as a pandas DataFrame, including embedding vectors."""
        import pandas as pd

        n = limit or self.collection.count()
        if n == 0:
            return pd.DataFrame(columns=["chunk_id", "parent_context", "source", "text", "embedding"])

        result = self.collection.get(
            limit=n,
            include=["documents", "metadatas", "embeddings"],
        )
        rows = []
        for doc, meta, emb in zip(
            result["documents"],
            result["metadatas"],
            result["embeddings"],
        ):
            rows.append(
                {
                    "chunk_id": meta["chunk_id"],
                    "parent_context": meta["parent_context"],
                    "source": meta["source"],
                    "text": doc,
                    "embedding": list(emb),
                }
            )
        return pd.DataFrame(rows)
