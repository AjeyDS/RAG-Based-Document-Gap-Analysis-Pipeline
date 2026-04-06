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
        self.stories_col = self.client.get_or_create_collection(
            name="stories",
            embedding_function=embedding_fn,
            metadata={"description": "Story-level chunks for semantic matching"}
        )
        self.criteria_col = self.client.get_or_create_collection(
            name="criteria",
            embedding_function=embedding_fn,
            metadata={"description": "AC-level chunks linked to parent stories"}
        )


    def add_document_chunks(
        self,
        chunks_result: dict[str, Any],
        source_path: str = "",
    ) -> dict[str, int]:
        story_chunks = chunks_result.get("story_chunks", [])
        ac_chunks = chunks_result.get("ac_chunks", [])

        if story_chunks:
            ids, docs, metas = [], [], []
            for c in story_chunks:
                meta = _sanitise_metadata(c["metadata"])
                meta["source"] = source_path
                ids.append(f"{source_path}::{c['id']}")
                docs.append(c["text"])
                metas.append(meta)
            self.stories_col.upsert(ids=ids, documents=docs, metadatas=metas)

        if ac_chunks:
            ids, docs, metas = [], [], []
            for c in ac_chunks:
                meta = _sanitise_metadata(c["metadata"])
                meta["source"] = source_path
                ids.append(f"{source_path}::{c['id']}")
                docs.append(c["text"])
                metas.append(meta)
            self.criteria_col.upsert(ids=ids, documents=docs, metadatas=metas)

        return {"story_chunks": len(story_chunks), "ac_chunks": len(ac_chunks)}

    def count(self) -> int:
        return self.stories_col.count() + self.criteria_col.count()

    def delete_by_source(self, source_path: str) -> int:
        """Delete all chunks for a given source file. Returns count deleted."""
        count = 0
        for col in self.client.list_collections():
            result = col.get(where={"source": source_path}, include=[])
            ids = result.get("ids", [])
            if ids:
                col.delete(ids=ids)
            count += len(ids)
        return count

