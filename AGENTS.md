# Repository Guidelines

## Project Structure & Module Organization

`backend/app/` contains the FastAPI API, configuration, MCP integrations, and Workbench/NLQ services. Backend tests live in `backend/tests/`, grouped by feature (for example, `backend/tests/workbench/`). `frontend/app/` holds Next.js routes, `frontend/components/` holds React UI, and `frontend/lib/` holds client utilities and its Node test. Shared Python code is in `packages/genesis_core/`; deployment files and contributor documentation live in `docker-compose.yml`, `nginx/`, and `docs/`. Static images are in `assets/` and `frontend/public/`.

## Workflow

- Make **surgical, minimal changes**. Do not refactor, reformat, or "improve" code outside the scope of the task.

## Python Style

- Follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) with the project-specific rules in `ruff.toml`.
- Use four spaces, an 80-character formatting target, and double-quoted strings. Use Google-style `Args:`, `Returns:`, and `Raises:` sections when a docstring needs them.
- Prefer descriptive names and short functions. Add comments or docstrings when they explain a public contract, a business rule, or a non-obvious decision; avoid narrating the implementation.
- Use absolute imports. Keep standard-library, third-party, and project imports grouped. Imports inside functions are allowed for circular dependencies, optional integrations, or expensive initialization.
- Use precise types and explicit `None` handling. Use Pydantic validation for external tool and API inputs, and `ty` for static type checking.
- Keep FastAPI dependency declarations and Pydantic models compatible with their frameworks. Package initializers may expose imports.
- Test directories and files named `test_*.py` or `*_test.py` are excluded from Ruff lint and formatting, including explicitly passed paths. Continue type checking and running tests.
- Keep logging arguments separate from format strings. Preserve existing PII and secret-redaction boundaries when adding logs.
- Check changed Python files with `ruff check`, `ruff format --check`, and `ty check`. Do not reformat unrelated files to adopt new rules.

## Instructions

- Run `ruff check` and `ty check` in the backend.
- Write code so that comments are not necessary by naming the functions and variables that matches what it does and what it is. Comments are commonly discouraged.
- Work on one thing at a time write code, test if it works, only after verifying then move on to the next thing.
- Do not write tests for everything, tests are also a liability as it slows you down, so only write tests for critical things.
- If something is not tested then assume it does not work. You should not report something is complete or fixed without verification.
