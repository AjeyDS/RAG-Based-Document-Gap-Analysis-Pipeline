import argparse
from src.rag_api.auth import hash_password, _get_connection
from src.rag_api.dependencies import get_vector_store

def seed_users():
    # Trigger DB init
    get_vector_store()
    
    users = [
        ("ADM001", "admin1", "admin1pass", "admin"),
        ("ADM002", "admin2", "admin2pass", "admin"),
        ("USR001", "user1", "user1pass", "user"),
        ("USR002", "user2", "user2pass", "user"),
    ]
    
    conn = _get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                for user_id, username, password, role in users:
                    pwd_hash = hash_password(password)
                    cur.execute("""
                        INSERT INTO users (user_id, username, password_hash, role)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (user_id) DO NOTHING;
                    """, (user_id, username, pwd_hash, role))
        print("Users seeded successfully.")
    except Exception as e:
        print(f"Error seeding users: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    seed_users()
