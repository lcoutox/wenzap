# Nexbrain

AI agent orchestration platform for business operations.

## Quick start

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- Node.js 20+

### 1. Start the database

```bash
make db
```

> **Note:** The main Postgres runs on port **5434** (not 5432) to avoid conflict with a local PostgreSQL installation. The test database runs on **5433**.

### 2. Configure environment variables

```bash
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env.local
```

Fill in your Clerk credentials in both `.env` files.

### 3. Install dependencies and run migrations

```bash
cd apps/api
uv sync
uv run alembic upgrade head
```

### 4. Start the API

```bash
make dev-api
# or: cd apps/api && uv run fastapi dev app/main.py
```

API runs at http://localhost:8000

Docs at http://localhost:8000/docs

### 5. Install frontend dependencies and start

```bash
cd apps/web
npm install
npm run dev
```

Frontend runs at http://localhost:3000

### Run tests

```bash
make test-api
```

## Project structure

```
nexbrain/
  apps/
    api/      # FastAPI backend
    web/      # Next.js frontend
  packages/
    shared/   # Shared types (minimal for now)
  docs/       # Product and architecture docs
```

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 |
| Database | PostgreSQL 16 |
| Auth | Clerk |
| Frontend | Next.js 15, TypeScript, Tailwind CSS |
| Tests | Pytest |
