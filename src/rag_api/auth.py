"""Authentication utilities: password hashing, session creation, and user lookup."""
import uuid
import logging

import bcrypt
import psycopg2

from src.config import settings
from src.rag_ingest.exceptions import StorageError

logger = logging.getLogger(__name__)


def _get_connection() -> psycopg2.extensions.connection:
    """Open and return a raw database connection from configured settings."""
    return psycopg2.connect(
        host=settings.pg_host,
        port=settings.pg_port,
        dbname=settings.pg_database,
        user=settings.pg_user,
        password=settings.pg_password,
    )


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the given plaintext password."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Return True if password matches the bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def get_user_by_username(username: str) -> tuple | None:
    """Return (user_id, password_hash, role) for the given username, or None if not found."""
    try:
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT user_id, password_hash, role FROM users WHERE username = %s;",
                        (username,),
                    )
                    return cur.fetchone()
        finally:
            conn.close()
    except psycopg2.Error as e:
        raise StorageError(f"User lookup failed: {e}") from e


def create_session(user_id: str) -> str:
    """Insert a new 24-hour session for user_id and return the generated token."""
    token = str(uuid.uuid4())
    try:
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO sessions (token, user_id, expires_at)
                        VALUES (%s, %s, NOW() + INTERVAL '24 hours');
                        """,
                        (token, user_id),
                    )
            return token
        finally:
            conn.close()
    except psycopg2.Error as e:
        raise StorageError(f"Session creation failed: {e}") from e


def validate_session(token: str) -> dict | None:
    """Return {user_id, role, username} for a valid non-expired token, or None."""
    try:
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT u.user_id, u.role, u.username
                        FROM sessions s
                        JOIN users u ON s.user_id = u.user_id
                        WHERE s.token = %s AND s.expires_at > NOW();
                        """,
                        (token,),
                    )
                    row = cur.fetchone()
                    if row:
                        return {"user_id": row[0], "role": row[1], "username": row[2]}
                    return None
        finally:
            conn.close()
    except psycopg2.Error as e:
        raise StorageError(f"Session validation failed: {e}") from e


def delete_session(token: str) -> None:
    """Revoke a session by deleting it from the database."""
    try:
        conn = _get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM sessions WHERE token = %s;", (token,))
        finally:
            conn.close()
    except psycopg2.Error as e:
        raise StorageError(f"Session deletion failed: {e}") from e
