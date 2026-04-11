#!/bin/bash
set -e
echo "Waiting for database..."
python -c "
import time, psycopg2, os
for i in range(30):
    try:
        psycopg2.connect(
            host=os.environ['PG_HOST'],
            port=os.environ.get('PG_PORT', 5432),
            dbname=os.environ['PG_DATABASE'],
            user=os.environ.get('PG_USER', 'postgres'),
            password=os.environ.get('PG_PASSWORD', '')
        )
        print('Database ready')
        break
    except: time.sleep(1)
"
echo "Seeding users..."
python -m src.rag_api.seed_users
echo "Starting server..."
exec uvicorn src.rag_api.app:app --host 0.0.0.0 --port 8000
