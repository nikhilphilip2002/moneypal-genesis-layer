"""Moneypal Genesis Intelligence — single FastAPI application.

One app, three domain routers (macro, competitive, regulatory) mounted together.

Run (from backend/):  uvicorn app.main:app --port 8000 --reload
"""
import asyncio
import logging
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, auth, competitive, intelligence, macro, nlq, policy, regulatory, review, workbench
from app.core.config import settings
from app.core.logging import bind_trace, start_logging, stop_logging


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    start_logging()
    from app.services.workbench.prompts import warm_agent_gold_schema

    catalog_version, schema_chars = warm_agent_gold_schema()
    _app.state.agent_gold_schema_version = catalog_version
    _app.state.agent_gold_schema_chars = schema_chars
    logging.getLogger(__name__).info(
        "workbench Gold schema prefix initialized version=%s chars=%d",
        catalog_version, schema_chars,
    )

    from app.mcp import postgres_client

    try:
        # Container dependency ordering does not guarantee service readiness. Bound startup
        # discovery so unrelated APIs can still start; a later Workbench request retries it.
        mcp_status = await asyncio.wait_for(postgres_client.initialize(), timeout=10.0)
        logging.getLogger(__name__).info(
            "PostgreSQL MCP initialized tools=%s", mcp_status["tools"],
        )
    except Exception as exc:  # noqa: BLE001 - readiness remains visible and retryable
        logging.getLogger(__name__).warning(
            "PostgreSQL MCP startup initialization unavailable: %s", exc,
        )
    # Workbench execution is intentionally not a rollout switch: every request uses the
    # provider-native tool loop.
    logging.getLogger(__name__).info(
        "workbench execution=native_only context_window=%d "
        "compaction_enabled=%s observation_max_chars=%d llm_model=%s",
        settings.workbench_context_window, settings.workbench_compaction_enabled,
        settings.workbench_agent_observation_max_chars, settings.llm_model,
    )
    warmup_task = None
    from app.services.nlq.llm import warm_catalog_prompt_cache

    # Become ready immediately; catalog prompt evaluation happens before the first
    # analyst question normally arrives, without making API health depend on the LLM.
    warmup_task = asyncio.create_task(warm_catalog_prompt_cache())
    # The signal scan runs on a schedule rather than on a question: "what are the emerging
    # issues?" has no answer at request time, because there is no baseline to compare against
    # and nothing has been ranked yet.
    from app.services.signals import scheduler as signal_scheduler

    scan_task = signal_scheduler.start(_app.state)

    from app.services.curiosity_graph import warm_curiosity_graph
    warm_graph_task = asyncio.create_task(asyncio.to_thread(warm_curiosity_graph))

    yield

    await signal_scheduler.stop(scan_task)
    if warmup_task is not None and not warmup_task.done():
        warmup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await warmup_task
    if warm_graph_task is not None and not warm_graph_task.done():
        warm_graph_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await warm_graph_task
    stop_logging()


def create_app() -> FastAPI:
    app = FastAPI(title="Moneypal Genesis Intelligence API", lifespan=_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def trace_context_middleware(request, call_next):
        trace_id = request.headers.get("x-trace-id") or request.headers.get("x-request-id")
        with bind_trace(trace_id=trace_id):
            response = await call_next(request)
            return response

    app.include_router(auth.router)
    app.include_router(macro.router)
    app.include_router(competitive.router)
    app.include_router(regulatory.router)
    app.include_router(admin.router)
    app.include_router(review.router)
    app.include_router(policy.router)
    app.include_router(intelligence.router)
    app.include_router(nlq.router)
    app.include_router(workbench.router)

    @app.get("/health")
    def health():
        """Process health plus cached startup state; never performs network I/O."""
        from app.mcp import postgres_client

        return {
            "status": "ok",
            "service": "genesis-intelligence",
            "workbench": {
                "postgres_mcp": postgres_client.readiness(),
                "gold_schema": {
                    "status": (
                        "ok" if getattr(app.state, "agent_gold_schema_version", "")
                        else "unavailable"
                    ),
                    "version": getattr(app.state, "agent_gold_schema_version", ""),
                    "characters": getattr(app.state, "agent_gold_schema_chars", 0),
                },
            },
        }

    return app


app = create_app()
