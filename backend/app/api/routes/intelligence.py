"""Dashboard intelligence feeds (executive landing page widgets)."""
from fastapi import APIRouter

from app.services import intelligence

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("/recent")
def recent(limit: int = 5):
    """Recently (re)generated intelligence, newest first."""
    return intelligence.recent(limit)


@router.get("/action-items")
def action_items():
    """Open action items: flagged intelligence + high-severity regulatory alerts."""
    return intelligence.action_items()
