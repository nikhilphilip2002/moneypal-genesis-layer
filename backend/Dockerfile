# Build context = repo root: docker build -f backend/Dockerfile -t genesis-intelligence .
FROM python:3.11-slim

WORKDIR /srv
COPY packages/genesis_core /srv/packages/genesis_core
RUN pip install --no-cache-dir /srv/packages/genesis_core fastapi "uvicorn[standard]" psycopg2-binary

COPY backend /srv/backend
WORKDIR /srv/backend

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
