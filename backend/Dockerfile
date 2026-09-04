# Build context = repo root: docker build -f backend/Dockerfile -t genesis-intelligence .
FROM python:3.11-slim

WORKDIR /srv
# Copy files required for package installation first to optimize Docker layer caching.
# Application code changes in backend/ or packages/genesis_core/ will not bust the dependency cache.
COPY requirements.txt /srv/requirements.txt
COPY packages/genesis_core/pyproject.toml /srv/packages/genesis_core/pyproject.toml

# sentence-transformers depends on torch. The default PyPI resolution currently pulls the
# multi-GB CUDA runtime even though these containers run embeddings on CPU. Installing a
# compatible CPU wheel first satisfies that dependency without the nvidia-* wheel set.
ARG PYTORCH_CPU_INDEX_URL=https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir --index-url "${PYTORCH_CPU_INDEX_URL}" torch

# Create package stub to satisfy hatchling during dependency installation, then install all requirements.
# sqlglot parses generated SQL for the NLQ validator's AST allowlist; pyyaml loads the
# semantic catalog. Both are imported at app.main import time via the nlq router.
# requests/beautifulsoup4/lxml crawl the macro sources and APScheduler drives the weekly
# refresh. Only the macro-pipeline service uses them, but it shares this image.
RUN mkdir -p /srv/packages/genesis_core/src/genesis_core \
    && touch /srv/packages/genesis_core/src/genesis_core/__init__.py \
    && pip install --no-cache-dir -r /srv/requirements.txt

# Copy package source code and reinstall in editable mode without refetching dependencies
COPY packages/genesis_core /srv/packages/genesis_core
RUN pip install --no-cache-dir --no-deps -e /srv/packages/genesis_core

COPY backend /srv/backend
WORKDIR /srv/backend

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
