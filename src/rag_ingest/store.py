"""Store module for Document Gap Analysis pipeline."""
from __future__ import annotations

import json
import time
from pathlib import Path
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
                            chunk_id TEXT UNIQUE NOT NULL,
                            chunk_type TEXT NOT NULL, 
                            content TEXT NOT NULL,
                            embedding vector({self.settings.embedding_dimensions}) NOT NULL,
                            story_id TEXT NOT NULL,
                            metadata JSONB NOT NULL DEFAULT '{{}}',
                            source_path TEXT NOT NULL
                        );
                    """)
                    cur.execute(f"""
                        CREATE INDEX IF NOT EXISTS idx_chunks_embedding 
                        ON document_chunks USING ivfflat (embedding vector_cosine_ops) 
                        WITH (lists = {self.settings.ivfflat_lists});
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT NOT NULL UNIQUE,
                            username TEXT NOT NULL UNIQUE,
                            password_hash TEXT NOT NULL,
                            role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
                            created_at TIMESTAMP NOT NULL DEFAULT NOW()
                        );
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS sessions (
                            id SERIAL PRIMARY KEY,
                            token TEXT NOT NULL UNIQUE,
                            user_id TEXT NOT NULL REFERENCES users(user_id),
                            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                            expires_at TIMESTAMP NOT NULL
                        );
                    """)
            conn.commit()
        finally:
            self._pool.putconn(conn)

    def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        return self.embedding_provider.embed(texts)

    def _validate_chunk(self, chunk_id: str, chunk_type: str, content: str | None, story_id: str | None, metadata: dict | None, source_path: str | None) -> tuple[str, str, dict, str]:
        if not chunk_type or chunk_type not in ("story", "criteria"):
            raise ValueError(f"Invalid or null chunk_type: {chunk_type}")
        if content is None or str(content).strip() == "":
            content = "NA"
        if not story_id:
            raise ValueError(f"story_id cannot be null/empty for chunk {chunk_id}")
        if metadata is None or not isinstance(metadata, dict):
            raise ValueError(f"metadata must be a valid JSONB object, got {type(metadata)} for chunk {chunk_id}")
        if not source_path:
            raise ValueError(f"source_path cannot be null/empty for chunk {chunk_id}")
        return content, story_id, metadata, source_path

    def _normalize_source_path(self, source_path: str) -> str:
        """Normalize path to be relative to the upload directory for cross-environment consistency."""
        if not source_path:
            return ""
        try:
            normalized = source_path.replace("\\", "/")
            if "data/uploads/" in normalized:
                return normalized.split("data/uploads/")[-1]
            return Path(source_path).name
        except Exception:
            return source_path

    @db_operation
    def add_document_chunks(
        self,
        chunks_result: dict[str, Any],
        source_path: str = "",
    ) -> dict[str, int]:
        source_path = self._normalize_source_path(source_path)
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
                        texts = [c["text"] if c.get("text") is not None else "NA" for c in story_chunks]
                        embeddings = self._get_embeddings(texts)
                        for i, c in enumerate(story_chunks):
                            scoped_id = f"{source_path}::{c.get('id', 'NA')}"
                            content, story_id, meta, src = self._validate_chunk(
                                scoped_id, "story", c.get("text"), c.get("metadata", {}).get("story_id"), c.get("metadata"), source_path
                            )
                            
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
                                content,
                                embeddings[i],
                                story_id,
                                json.dumps(meta),
                                src
                            ))
                        counts["story_chunks"] = len(story_chunks)

                    # Insert AC chunks
                    if ac_chunks:
                        texts = [c["text"] if c.get("text") is not None else "NA" for c in ac_chunks]
                        embeddings = self._get_embeddings(texts)
                        for i, c in enumerate(ac_chunks):
                            scoped_id = f"{source_path}::{c.get('id', 'NA')}"
                            content, story_id, meta, src = self._validate_chunk(
                                scoped_id, "criteria", c.get("text"), c.get("metadata", {}).get("story_id"), c.get("metadata"), source_path
                            )
                            
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
                                content,
                                embeddings[i],
                                story_id,
                                json.dumps(meta),
                                src
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
    def reset_db(self):
        """Drops and recreates the database schema to apply new constraints during first deploy."""
        conn = self._pool.getconn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("DROP TABLE IF EXISTS document_chunks CASCADE;")
            conn.commit()
            self._init_db_internal()
        finally:
            self._pool.putconn(conn)

    @db_operation
    def delete_by_source(self, source_path: str) -> int:
        source_path = self._normalize_source_path(source_path)
        conn = self._pool.getconn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM document_chunks WHERE source_path LIKE %s;", (f"%{source_path}",))
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
                cur.execute("SET ivfflat.probes = %s;", (self.settings.ivfflat_lists,))
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

    @db_operation
    def get_story_metadata(self, story_id: str) -> dict | None:
        """Return the metadata dict of the story chunk for story_id, or None if not found."""
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT metadata FROM document_chunks WHERE story_id = %s AND chunk_type = 'story' LIMIT 1;",
                    (story_id,),
                )
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            self._pool.putconn(conn)

    @db_operation
    def query_all_chunks(self, query_text: str, top_k: int = 5) -> list[dict]:
        """Embed query_text and return the top_k most similar chunks across all chunk types.

        Returns a list of dicts with keys: id, document, distance, metadata, source, chunk_type.
        """
        if not query_text:
            return []
            
        embeddings = self._get_embeddings([query_text])
        embedding = embeddings[0]
        conn = self._pool.getconn()
        register_vector(conn)
        
        try:
            with conn.cursor() as cur:
                cur.execute("SET ivfflat.probes = %s;", (self.settings.ivfflat_lists,))
                cur.execute("""
                    SELECT chunk_id, content, embedding <=> %s::vector AS distance, metadata, source_path, chunk_type, story_id
                    FROM document_chunks
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
                        "source": r[4],
                        "chunk_type": r[5],
                        "story_id": r[6],
                    })
            return results
        finally:
            self._pool.putconn(conn)
