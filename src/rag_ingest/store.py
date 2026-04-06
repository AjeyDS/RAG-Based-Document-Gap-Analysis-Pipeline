from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any
import psycopg2
from psycopg2 import pool
from pgvector.psycopg2 import register_vector
from openai import OpenAI

DEFAULT_EMBED_MODEL = "text-embedding-3-small"

class VectorStore:
    def __init__(
        self,
        db_url: str | None = None,
        openai_api_key: str | None = None,
        embed_model: str = DEFAULT_EMBED_MODEL,
    ) -> None:
        self.db_url = db_url or os.environ.get("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL not found in environment.")
        
        api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY required.")
            
        self.openai_client = OpenAI(api_key=api_key)
        self.embed_model = embed_model
        
        # Initialize connection pool
        self._pool = psycopg2.pool.ThreadedConnectionPool(1, 10, self.db_url)
        self._init_db()

    def _init_db(self):
        conn = self._pool.getconn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS document_chunks (
                            id SERIAL PRIMARY KEY,
                            chunk_id TEXT UNIQUE,
                            chunk_type TEXT, 
                            content TEXT,
                            embedding vector(1536),
                            story_id TEXT,
                            metadata JSONB,
                            source_path TEXT
                        );
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_chunks_embedding 
                        ON document_chunks USING ivfflat (embedding vector_cosine_ops) 
                        WITH (lists = 100);
                    """)
            conn.commit()
        finally:
            self._pool.putconn(conn)

    def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.openai_client.embeddings.create(
            input=texts,
            model=self.embed_model
        )
        return [e.embedding for e in response.data]

    def add_document_chunks(
        self,
        chunks_result: dict[str, Any],
        source_path: str = "",
    ) -> dict[str, int]:
        story_chunks = chunks_result.get("story_chunks", [])
        ac_chunks = chunks_result.get("ac_chunks", [])
        
        counts = {"story_chunks": 0, "ac_chunks": 0}
        
        conn = self._pool.getconn()
        register_vector(conn)
        try:
            with conn:
                with conn.cursor() as cur:
                    # Insert story chunks
                    if story_chunks:
                        texts = [c["text"] for c in story_chunks]
                        embeddings = self._get_embeddings(texts)
                        for i, c in enumerate(story_chunks):
                            scoped_id = f"{source_path}::{c['id']}"
                            cur.execute("""
                                INSERT INTO document_chunks (chunk_id, chunk_type, content, embedding, story_id, metadata, source_path)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (chunk_id) DO UPDATE SET
                                    chunk_type = EXCLUDED.chunk_type,
                                    content = EXCLUDED.content,
                                    embedding = EXCLUDED.embedding,
                                    story_id = EXCLUDED.story_id,
                                    metadata = EXCLUDED.metadata,
                                    source_path = EXCLUDED.source_path;
                            """, (
                                scoped_id,
                                "story",
                                c["text"],
                                embeddings[i],
                                c["metadata"].get("story_id"),
                                json.dumps(c["metadata"]),
                                source_path
                            ))
                        counts["story_chunks"] = len(story_chunks)

                    # Insert AC chunks
                    if ac_chunks:
                        texts = [c["text"] for c in ac_chunks]
                        embeddings = self._get_embeddings(texts)
                        for i, c in enumerate(ac_chunks):
                            scoped_id = f"{source_path}::{c['id']}"
                            cur.execute("""
                                INSERT INTO document_chunks (chunk_id, chunk_type, content, embedding, story_id, metadata, source_path)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (chunk_id) DO UPDATE SET
                                    chunk_type = EXCLUDED.chunk_type,
                                    content = EXCLUDED.content,
                                    embedding = EXCLUDED.embedding,
                                    story_id = EXCLUDED.story_id,
                                    metadata = EXCLUDED.metadata,
                                    source_path = EXCLUDED.source_path;
                            """, (
                                scoped_id,
                                "criteria",
                                c["text"],
                                embeddings[i],
                                c["metadata"].get("story_id"),
                                json.dumps(c["metadata"]),
                                source_path
                            ))
                        counts["ac_chunks"] = len(ac_chunks)
            conn.commit()
        finally:
            self._pool.putconn(conn)

        return counts

    def count(self) -> int:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM document_chunks;")
                return cur.fetchone()[0]
        finally:
            self._pool.putconn(conn)

    def delete_by_source(self, source_path: str) -> int:
        conn = self._pool.getconn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM document_chunks WHERE source_path = %s;", (source_path,))
                    deleted = cur.rowcount
            conn.commit()
            return deleted
        finally:
            self._pool.putconn(conn)

    # Helper for similarity search used by API
    def query_stories_batch(self, query_texts: list[str], top_k: int = 3) -> list[list[dict]]:
        if not query_texts:
            return []
            
        embeddings = self._get_embeddings(query_texts)
        conn = self._pool.getconn()
        register_vector(conn)
        
        batch_results = []
        try:
            with conn.cursor() as cur:
                for embedding in embeddings:
                    cur.execute("""
                        SELECT chunk_id, content, embedding <=> %s::vector AS distance, metadata, source_path
                        FROM document_chunks
                        WHERE chunk_type = 'story'
                        ORDER BY distance ASC
                        LIMIT %s;
                    """, (embedding, top_k))
                    rows = cur.fetchall()
                    results = []
                    for r in rows:
                        results.append({
                            "id": r[0],
                            "document": r[1],
                            "distance": r[2],
                            "metadata": r[3],
                            "source": r[4]
                        })
                    batch_results.append(results)
            return batch_results
        finally:
            self._pool.putconn(conn)

    def query_stories(self, query_text: str, top_k: int = 3) -> list[dict]:
        """Convenience method for a single query."""
        results = self.query_stories_batch([query_text], top_k=top_k)
        return results[0] if results else []

    def get_criteria_for_story(self, story_id: str) -> list[dict]:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT chunk_id, content, metadata
                    FROM document_chunks
                    WHERE chunk_type = 'criteria' AND story_id = %s;
                """, (story_id,))
                rows = cur.fetchall()
                return [
                    {"id": r[0], "content": r[1], "metadata": r[2]}
                    for r in rows
                ]
        finally:
            self._pool.putconn(conn)
