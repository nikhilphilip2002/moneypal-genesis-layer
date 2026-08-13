# Build context = repo root: docker build -f backend/Dockerfile -t genesis-intelligence .
FROM python:3.11-slim

WORKDIR /srv
COPY packages/genesis_core /srv/packages/genesis_core
# sqlglot parses generated SQL for the NLQ validator's AST allowlist; pyyaml loads the
# semantic catalog. Both are imported at app.main import time via the nlq router, so a
# missing one is a crash loop, not a degraded feature.
# langgraph orchestrates the workbench chat (route -> dispatch -> synthesize); langchain-core
# is its state/runnable base. Imported at app.main import time via the workbench router.
RUN pip install --no-cache-dir /srv/packages/genesis_core fastapi "uvicorn[standard]" psycopg2-binary pg8000 openpyxl sqlglot pyyaml langgraph langchain-core "mcp==1.29.0"


COPY backend /srv/backend
WORKDIR /srv/backend



EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
