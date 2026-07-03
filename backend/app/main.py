"""Moneypal Genesis Intelligence — single FastAPI application.

One app, three domain routers (macro, competitive, regulatory) mounted together.

Run (from backend/):  uvicorn app.main:app --port 8000 --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import competitive, macro, regulatory


def create_app() -> FastAPI:
    app = FastAPI(title="Moneypal Genesis Intelligence API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(macro.router)
    app.include_router(competitive.router)
    app.include_router(regulatory.router)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "genesis-intelligence"}

    return app


app = create_app()
