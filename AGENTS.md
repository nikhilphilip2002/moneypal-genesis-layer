# Repository Guidelines
 
## Project Structure & Module Organization
 
`backend/app/` contains the FastAPI API, configuration, MCP integrations, and Workbench/NLQ services. Backend tests live in `backend/tests/`, grouped by feature (for example, `backend/tests/workbench/`). `frontend/app/` holds Next.js routes, `frontend/components/` holds React UI, and `frontend/lib/` holds client utilities and its Node test. Shared Python code is in `packages/genesis_core/`; deployment files and contributor documentation live in `docker-compose.yml`, `nginx/`, and `docs/`. Static images are in `assets/` and `frontend/public/`.
 
## Critical rules — never violate
 
- **NEVER** commit directly to `main`. It is a protected branch — always create a new branch with a descriptive name (e.g., `fix/login-timeout`).
- **DO NOT** modify the agent loop or prompts. You may read these files for context, but never edit them.
 
## Workflow
 
- Make **surgical, minimal changes**. Do not refactor, reformat, or "improve" code outside the scope of the task.
- Keep PRs small and coherent: **one logical change per PR**.
 
## Before finishing
 
- Run `uv run ruff check` in `backend/` and `npm run lint` in `frontend/`. Both must pass before you consider the work done.
- If lint fails in code you did not touch, leave it as-is and note it in the PR description.
 
 
