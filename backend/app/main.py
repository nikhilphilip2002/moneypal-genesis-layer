"""Moneypal Genesis Intelligence — single FastAPI application.

One app, three domain routers (macro, competitive, regulatory) mounted together.

Run (from backend/):  uvicorn app.main:app --port 8000 --reload
"""
import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, auth, competitive, intelligence, macro, nlq, policy, regulatory, review, workbench
from app.core.config import settings


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    warmup_task = None
    if settings.nlq_llm_provider == "llamacpp":
        from app.services.nlq.llm import warm_catalog_prompt_cache

        # Become ready immediately; catalog prompt evaluation happens before the first
        # analyst question normally arrives, without making API health depend on the LLM.
        warmup_task = asyncio.create_task(warm_catalog_prompt_cache())
    yield
    if warmup_task is not None and not warmup_task.done():
        warmup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await warmup_task


def create_app() -> FastAPI:
    app = FastAPI(title="Moneypal Genesis Intelligence API", lifespan=_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
        return {"status": "ok", "service": "genesis-intelligence"}

    return app


app = create_app()
