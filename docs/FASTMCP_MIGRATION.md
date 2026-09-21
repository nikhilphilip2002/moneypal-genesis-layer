# FastMCP architecture and operations

Moneypal uses FastMCP 4 with MCP SDK v2. Model-visible tool contracts always originate from
MCP discovery. Application code does not maintain a second tool-description or JSON-schema
registry.

## Topology

```text
Workbench agent
    -> ToolCatalog (canonical discovery, ownership, policy projection)
       -> in-process FastMCP server: curated search, web, visualization, terminal tools
       -> HTTP FastMCP client: separately deployed read-only PostgreSQL MCP server

Governed web handler -> hosted Exa MCP over Streamable HTTP
```

The PostgreSQL server remains a separate container and database security boundary. The local
server uses FastMCP's in-memory legacy transport because its retrieval handlers offload blocking
work to threads; direct dispatch currently does not shut down reliably after those calls.

## Contracts

- FastMCP function signatures own names, descriptions, fields, schemas, and validation.
- `agent_tools.py` contains runtime policy only: source, sensitivity, timeout, observation
  limit, and parallel-safety metadata.
- `ToolCatalog` caches canonical definitions, rejects duplicate or unclassified names, applies
  request policy to copies, and emits deterministic provider definitions.
- `provider_schema.py` is the only MCP-to-provider schema adapter.
- Moneypal-owned tools return `{"success": true, "data": ...}` or
  `{"success": false, "error": {...}}`. Callers consume FastMCP `result.data`.
- Exa response fallback remains isolated because Moneypal does not control that server.

## Startup and health

API startup requires successful local discovery and runtime-policy coverage. PostgreSQL MCP
discovery and health are bounded and may start degraded because it is separately deployed.
`GET /health` reports local and PostgreSQL status plus catalog ownership, MCP/FastMCP versions,
negotiated protocol versions, and a schema fingerprint. It never returns schemas or result rows.

The deployment must set:

```env
FASTMCP_MCP_CAMELCASE_COMPAT=false
POSTGRES_MCP_URL=http://postgres-mcp:8001/mcp
POSTGRES_MCP_MODEL_TOOLS=query
```

## Verification and rollout

```bash
FASTMCP_MCP_CAMELCASE_COMPAT=false uv run pytest backend/tests/workbench -q
FASTMCP_MCP_CAMELCASE_COMPAT=false uv run pytest backend/tests -q
docker compose config --quiet
docker compose up -d --build postgres-mcp backend
docker compose ps
curl -fsS http://localhost:4321/api/health
python backend/scripts/verify_workbench_rollout.py \
  --base-url http://localhost:4321/api --token "$WORKBENCH_SMOKE_TOKEN"
docker compose down
```

Verify that health lists the five Workbench tools under the `workbench` owner, `query` under
`postgres`, a non-empty 64-character fingerprint, and protocol `2025-11-25` (or the explicitly
approved protocol after a dependency upgrade). Canary error, timeout, and policy-denial telemetry
before broad rollout. There is no legacy execution flag: reintroducing a second dispatch path
would recreate the contract drift this migration removes. Roll back by reverting the migration
commit and rebuilding both backend containers together.
