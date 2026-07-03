from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.regulatory import router as regulatory_router
from app.core.config import settings


app = FastAPI(
    title="Moneypal Genesis Regulatory Intelligence API",
    version="0.1.0",
    description="RAG backend for RBI/NBFC regulatory intelligence.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "regulatory-intelligence"}


app.include_router(regulatory_router, prefix="/regulatory", tags=["regulatory"])
