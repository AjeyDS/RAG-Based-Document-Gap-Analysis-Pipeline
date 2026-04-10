import uuid
import bcrypt
import psycopg2
from src.config import settings

def _get_connection():
    return psycopg2.connect(
        host=settings.pg_host,
        port=settings.pg_port,
        dbname=settings.pg_database,
        user=settings.pg_user,
        password=settings.pg_password
    )

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_session(user_id: str) -> str:
    token = str(uuid.uuid4())
    conn = _get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO sessions (token, user_id, expires_at)
                    VALUES (%s, %s, NOW() + INTERVAL '24 hours');
                """, (token, user_id))
        return token
    finally:
        conn.close()

def validate_session(token: str) -> dict | None:
    conn = _get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT u.user_id, u.role, u.username
                    FROM sessions s
                    JOIN users u ON s.user_id = u.user_id
                    WHERE s.token = %s AND s.expires_at > NOW();
                """, (token,))
                row = cur.fetchone()
                if row:
                    return {"user_id": row[0], "role": row[1], "username": row[2]}
                return None
    finally:
        conn.close()

def delete_session(token: str):
    conn = _get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE token = %s;", (token,))
    finally:
        conn.close()
