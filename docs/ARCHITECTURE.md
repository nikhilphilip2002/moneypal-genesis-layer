# Moneypal architecture

This diagram shows the Docker Compose deployment and its configured external dependencies. PostgreSQL, Qdrant, the model endpoint, and Exa are not services in `docker-compose.yml`.

![Moneypal architecture diagram](architecture.png)

The editable Mermaid version is below.

```mermaid
flowchart LR
    browser[Browser] -->|pages and /api requests| nginx[nginx :4321]

    subgraph stack[Docker Compose stack]
        nginx -->|pages| frontend[Next.js :3000]

        subgraph backend[FastAPI application]
            api[FastAPI :8000]
            api --> routes[Feature APIs: macro, competitive, regulatory, reports, policy, review, NLQ]
            api --> workbench[Workbench agent and source policy]
            workbench --> local_mcp[In-process Workbench MCP tools]
            routes -->|RAG features| core[genesis_core RAG and shared schemas]
            local_mcp --> core
        end

        postgres_mcp[PostgreSQL MCP :8001<br/>Gold catalog validation and read-only SQL]
        worker[Scheduled macro pipeline]
        macro_data[(Macro download and state volume)]
        worker --> macro_data
    end

    nginx -->|/api/* and Workbench SSE| api
    workbench -->|governed query tool| postgres_mcp
    postgres_mcp -->|nlq_readonly role| postgres[(PostgreSQL: loan book, Gold views, app records)]
    api -->|history, signals, reports, other API data| postgres
    workbench -->|model calls| llm[OpenAI-compatible LLM endpoint]
    routes -->|model calls| llm
    local_mcp -->|public web search, when enabled| exa[Exa hosted MCP]
    core -->|semantic retrieval| qdrant[(Qdrant collections)]
    worker -->|crawl| macro_sources[Public macro sources]
    worker -->|embed and refresh| qdrant
    ingest[Manual document ingestion scripts] -->|regulatory and competitor documents| qdrant
    routes -->|generated brief cache| sqlite[(Local SQLite cache)]
```

The browser calls `/api/*` on the same origin; nginx strips `/api` before forwarding to FastAPI. The Workbench streams answers through this path. Its local MCP tools run inside the API process, while PostgreSQL queries use the separate MCP container. The macro worker refreshes Qdrant on a schedule; document ingestion scripts populate other collections when run manually.

Sources: `docker-compose.yml`, `nginx/nginx.conf`, `backend/app/main.py`, `backend/app/mcp/`, `backend/app/services/workbench/`, `backend/app/services/brief_cache.py`, and `backend/scripts/macro_pipeline/`.
