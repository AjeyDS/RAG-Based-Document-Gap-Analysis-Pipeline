"""Store module for Document Gap Analysis pipeline."""
from __future__ import annotations

import json
import time
from typing import Any
import psycopg2
import psycopg2.pool
from pgvector.psycopg2 import register_vector
from src.config import Config
from src.rag_ingest.llm.base import EmbeddingProvider
from src.rag_ingest.exceptions import StorageError
import logging
from functools import wraps
logger = logging.getLogger(__name__)

def db_operation(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except psycopg2.OperationalError as e:
            logger.error("Database connection failed, check PG_HOST and credentials")
            raise StorageError("Database connection failed") from e
        except psycopg2.Error as e:
            raise StorageError(f"Database operation failed: {e}") from e
    return wrapper

class VectorStore:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        settings: Config,
    ) -> None:
        self.settings = settings
        self.embedding_provider = embedding_provider
        self.db_url = f"postgresql://{settings.pg_user}:{settings.pg_password}@{settings.pg_host}:{settings.pg_port}/{settings.pg_database}"
        
        try:
            self._pool = psycopg2.pool.ThreadedConnectionPool(settings.pg_pool_min, settings.pg_pool_max, self.db_url)
            self._init_db_internal()
        except psycopg2.OperationalError as e:
            logger.error("Database connection failed, check PG_HOST and credentials")
            raise StorageError("Database connection failed") from e
        except psycopg2.Error as e:
            raise StorageError(f"Storage initialization failed: {e}") from e

    def _init_db_internal(self):
        conn = self._pool.getconn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                    cur.execute(f"""
                        CREATE TABLE IF NOT EXISTS document_chunks (
                            id SERIAL PRIMARY KEY,
                            chunk_id TEXT UNIQUE,
                            chunk_type TEXT, 
                            content TEXT,
                            embedding vector({self.settings.embedding_dimensions}),
                            story_id TEXT,
                            metadata JSONB,
                            source_path TEXT
                        );
                    """)
                    cur.execute(f"""
                        CREATE INDEX IF NOT EXISTS idx_chunks_embedding 
                        ON document_chunks USING ivfflat (embedding vector_cosine_ops) 
                        WITH (lists = {self.settings.ivfflat_lists});
                    """)
            conn.commit()
        finally:
            self._pool.putconn(conn)

    def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        return self.embedding_provider.embed(texts)

    @db_operation
    def add_document_chunks(
        self,
        chunks_result: dict[str, Any],
        source_path: str = "",
    ) -> dict[str, int]:
        story_chunks = chunks_result.get("story_chunks", [])
        ac_chunks = chunks_result.get("ac_chunks", [])
        
        if not story_chunks and not ac_chunks:
            logger.warning("No document chunks provided to add_document_chunks.")
            return {"story_chunks": 0, "ac_chunks": 0}
        
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

        logger.info(
            "Document chunks upserted",
            extra={
                "story_chunk_count": len(story_chunks),
                "ac_chunk_count": len(ac_chunks),
                "source_path": source_path
            }
        )
        
        return counts

    @db_operation
    def count(self) -> int:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM document_chunks;")
                return cur.fetchone()[0]
        finally:
            self._pool.putconn(conn)

    @db_operation
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

    @db_operation
    def query_stories_batch(self, query_texts: list[str], top_k: int = 3) -> list[list[dict]]:
        if not query_texts:
            return []
            
        embeddings = self._get_embeddings(query_texts)
        conn = self._pool.getconn()
        register_vector(conn)
        
        batch_results = []
        try:
            start_time = time.time()
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
                    
            duration = time.time() - start_time
            logger.debug(
                "Queried stories batch",
                extra={
                    "query_text_preview": query_texts[0][:100] if query_texts else "",
                    "result_count": sum(len(res) for res in batch_results),
                    "latency_ms": round(duration * 1000, 2)
                }
            )
            return batch_results
        finally:
            self._pool.putconn(conn)

    def query_stories(self, query_text: str, top_k: int = 3) -> list[dict]:
        """Convenience method for a single query."""
        results = self.query_stories_batch([query_text], top_k=top_k)
        return results[0] if results else []

    @db_operation
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
