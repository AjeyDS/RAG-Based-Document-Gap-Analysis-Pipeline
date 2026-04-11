# Setup & Quick Start

Follow this guide to spin up a fully functioning environment natively supporting RAG document gap capabilities iteratively. 

## Prerequisites
- **Python 3.11+**
- **Node.js 20+**
- **Docker & Docker Compose**
- **OpenAI API Key** (Sufficient permissions logic enabling GPT-4o capabilities)

## Quick Start (Docker)

To rapidly spin up the application utilizing standard containers, simply execute:
1. `git clone <repository_url> && cd <repository_folder>`
2. `cp .env.example .env` (fill in `OPENAI_API_KEY`, ensure `PG_HOST=db`)
3. `make up`

*Wait a moment for PostgreSQL to initialize pgvector constraints natively.*
*(Note: the docker-entrypoint automatically runs `seed_users` on startup)*

**Default Credentials:**
- admin1/admin1pass (ADM-001, admin)
- admin2/admin2pass (ADM-002, admin)
- user1/user1pass (USR-001, user)
- user2/user2pass (USR-002, user)
*(Change these credentials for production deployment)*

## Local Development Setup

If natively modifying API behaviors without Docker mapping logic:

### Dependent Steps: PostgreSQL Storage Setup
If not using the nested Compose Docker DB, natively install PostgreSQL 16 globally and successfully add the `pgvector` extension locally. 

### Backend Local Initialization
1. Create environment: `python3 -m venv .venv && source .venv/bin/activate`
2. Install pip dependencies: `pip install -r requirements.txt`
3. Clone variables flexibly: `cp .env.example .env` (Set `OPENAI_API_KEY` and match local `PG_USER` mappings ensuring `PG_HOST=localhost`)
4. Spin environment natively: `python -m uvicorn src.rag_api.app:app --reload --port 8000`

### Frontend UI Initialization
1. Route inside UI context: `cd frontend`
2. Install nested dependencies efficiently: `npm install`
3. Trigger application locally: `npm run dev`

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|--------|-------------|
| `OPENAI_API_KEY` | **Yes** | - | OpenAI authentication token |
| `PG_HOST` | No | `localhost` | Logical Postgres IP mapping routing (`db` in compose) |
| `PG_PORT` | No | `5432` | Mapping port logical listener |
| `PG_USER` | No | `postgres` | Active connection user mapping |
| `PG_PASSWORD` | **Yes** | - | Validation constraint password logical execution |
| `PG_DATABASE` | No | `rag_gap` | Storage cluster nomenclature identifier |
| `LLM_MODEL` | No | `gpt-4o` | Chat model executing chunk boundaries and gap analysis |
| `EMBEDDING_MODEL`| No | `text-embedding-3-small`| String-to-Vector target mapping model heavily required |
| `LOG_FORMAT` | No | `json` | Centralized formatter setting (`json` or `text`) |

## Adding Users

Use `src/rag_api/add_user.py` to add users without modifying the seed script.

**Inside Docker:**
```bash
docker exec -it docgapanalysis-backend-1 python -m src.rag_api.add_user \
  --user-id USR003 --username newuser --password s3cur3pass --role user
```

**Local dev** (override `PG_HOST` since `.env` points to the Docker internal hostname):
```bash
PG_HOST=localhost PG_PORT=5433 python -m src.rag_api.add_user \
  --user-id USR003 --username newuser --password s3cur3pass --role user
```

| Parameter | Required | Values |
|-----------|----------|--------|
| `--user-id` | Yes | Unique ID, e.g. `USR003`, `ADM003` |
| `--username` | Yes | Login username |
| `--password` | Yes | Plaintext (stored as bcrypt hash) |
| `--role` | No | `user` (default) or `admin` |

> Note: `PG_PORT=5433` is needed locally because the Docker DB is remapped to avoid conflict with a local PostgreSQL instance on 5432. Adjust if your setup differs.

## Verification Logic

Validate backend API listener behaviors naturally directly firing curl logic executing internally:

**Healthcheck / Fetch Listed files:**
```bash
curl http://localhost:8000/api/knowledge-base
```

**Evaluate Document Match Functionality (Expect clean JSON output constraints):**
```bash
curl -X POST http://localhost:8000/api/documents/compare \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{"uploadedText": "Testing doc...", "matches": []}'
```

**Evaluate Auth / Login Login Logic:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin1","password":"admin1pass"}'
```
