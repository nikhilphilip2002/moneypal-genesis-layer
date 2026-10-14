# Moneypal

Moneypal is an intelligence workspace for banking teams. It combines a Next.js frontend with a FastAPI backend for the Workbench, loan-book analysis, and macro, competitive, and regulatory research. PostgreSQL provides governed loan-book data, Qdrant supports document search, and an OpenAI-compatible model powers question answering.

## Prerequisites

- Docker Compose for the full-stack setup, or Python 3.13+, [`uv`](https://docs.astral.sh/uv/), and Node.js for local development.
- Reachable PostgreSQL, Qdrant, and OpenAI-compatible LLM services. The service addresses and credentials are configured in `.env`.

## Configuration

Copy `.env.example` to `.env` and set the LLM, PostgreSQL, and Qdrant connection values for your environment. `.env.example` documents the available settings. Keep credentials in `.env`; do not commit them.

## Run with Docker Compose

From the repository root, start the services:

```bash
docker compose up --build
```

Open the application at [http://localhost:4321](http://localhost:4321). The API is available through the same origin under `/api`, and its health endpoint is [http://localhost:4321/health](http://localhost:4321/health).

## Local development

Install the Python workspace dependencies from the repository root:

```bash
uv sync
```

Start the backend in one terminal:

```bash
uv run uvicorn app.main:app --app-dir backend --reload --port 8000
```

Install and start the frontend in another terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at [http://localhost:3000](http://localhost:3000), and the backend health endpoint is [http://localhost:8000/health](http://localhost:8000/health). Local runs still require reachable PostgreSQL, Qdrant, and LLM services configured in `.env`.

## Repository layout

- `backend/app/` — FastAPI API, Workbench, MCP integrations, and services.
- `backend/tests/` — backend tests grouped by feature.
- `frontend/app/`, `frontend/components/`, and `frontend/lib/` — Next.js routes, UI components, and client utilities.
- `packages/genesis_core/` — shared Python functionality.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the deployment diagram and service boundaries.
