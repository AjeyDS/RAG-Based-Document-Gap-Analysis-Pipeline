from __future__ import annotations

from unittest.mock import patch

import pytest

from rag_ingest.models import Chunk
from rag_ingest.store import VectorStore


class _FakeEmbeddingFunction:
    """Returns deterministic fixed-length embeddings without calling OpenAI."""

    def name(self) -> str:
        return "fake"

    def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002
        return [[float(i) / 100] * 384 for i in range(len(input))]

    def embed_query(self, input: list[str]) -> list[list[float]]:  # noqa: A002
        return self(input)


@pytest.fixture()
def store(tmp_path):
    with patch("rag_ingest.store.OpenAIEmbeddingFunction", return_value=_FakeEmbeddingFunction()):
        vs = VectorStore(persist_dir=tmp_path, openai_api_key="test-key")
    return vs


def test_add_chunks_returns_count(store):
    chunks = [
        Chunk(chunk_id="US-1.1 Login", parent_context="US-1.1 Login", text="Context: US-1.1 Login\nRequirement: US-1.1 Login\nbody"),
        Chunk(chunk_id="AC-1.1 Creds", parent_context="US-1.1 Login", text="Context: US-1.1 Login\nRequirement: AC-1.1 Creds\nbody"),
    ]
    assert store.add_chunks(chunks, source_path="file.docx") == 2
    assert store.count() == 2


def test_add_chunks_empty_is_noop(store):
    assert store.add_chunks([], source_path="file.docx") == 0
    assert store.count() == 0


def test_upsert_does_not_duplicate(store):
    chunk = Chunk(chunk_id="US-1.1 Login", parent_context="US-1.1 Login", text="body")
    store.add_chunks([chunk], source_path="file.docx")
    store.add_chunks([chunk], source_path="file.docx")
    assert store.count() == 1


def test_query_returns_hits(store):
    chunks = [
        Chunk(chunk_id="US-1.1 Login", parent_context="US-1.1 Login", text="user login story"),
        Chunk(chunk_id="US-2.1 Signup", parent_context="US-2.1 Signup", text="user signup story"),
    ]
    store.add_chunks(chunks, source_path="stories.docx")

    hits = store.query("login", n_results=1)

    assert len(hits) == 1
    assert hits[0]["chunk_id"] in {"US-1.1 Login", "US-2.1 Signup"}
    assert "distance" in hits[0]
    assert "text" in hits[0]
    assert hits[0]["source"] == "stories.docx"


def test_raises_without_api_key(tmp_path):
    with patch("rag_ingest.store.OpenAIEmbeddingFunction"), \
         patch("rag_ingest.store.os.environ.get", return_value=None):
        with pytest.raises(ValueError, match="OpenAI API key"):
            VectorStore(persist_dir=tmp_path)
