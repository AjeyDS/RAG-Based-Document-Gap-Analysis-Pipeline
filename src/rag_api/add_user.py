"""CLI script to add a single user to the database."""
import argparse
import logging
import sys

from src.rag_api.auth import hash_password, _get_connection
from src.rag_ingest.exceptions import StorageError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def add_user(user_id: str, username: str, password: str, role: str) -> None:
    conn = _get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM users WHERE user_id = %s OR username = %s;", (user_id, username))
                if cur.fetchone():
                    logger.error("A user with user_id '%s' or username '%s' already exists.", user_id, username)
                    sys.exit(1)

                cur.execute(
                    "INSERT INTO users (user_id, username, password_hash, role) VALUES (%s, %s, %s, %s);",
                    (user_id, username, hash_password(password), role),
                )
        print(f"User '{username}' ({user_id}) created successfully with role '{role}'.")
    except StorageError as e:
        logger.error("Failed to add user: %s", e)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add a new user to the database.")
    parser.add_argument("--user-id", required=True, help="Unique user ID (e.g. USR003)")
    parser.add_argument("--username", required=True, help="Login username")
    parser.add_argument("--password", required=True, help="Plaintext password (will be hashed)")
    parser.add_argument("--role", choices=["user", "admin"], default="user", help="User role (default: user)")
    args = parser.parse_args()

    add_user(args.user_id, args.username, args.password, args.role)
