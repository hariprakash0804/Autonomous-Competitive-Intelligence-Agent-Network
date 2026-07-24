import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.snapshot import Snapshot
from app.models.competitor import Competitor
from app.services.ingestion import ingest_competitor_urls

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


@router.get("/competitor/{competitor_id}")
def get_competitor_snapshots(
    competitor_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Lists snapshots for a specific competitor owned by current user."""
    competitor = db.get(Competitor, competitor_id)
    if not competitor or competitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")

    snapshots = db.scalars(
        select(Snapshot)
        .where(Snapshot.competitor_id == competitor_id)
        .order_by(Snapshot.fetched_at.desc())
    ).all()

    return [
        {
            "id": str(s.id),
            "competitor_id": str(s.competitor_id),
            "source_type": s.source_type.value if hasattr(s.source_type, "value") else s.source_type,
            "content_hash": s.content_hash,
            "is_stale": s.is_stale,
            "fetched_at": s.fetched_at.isoformat(),
            "raw_content_preview": s.raw_content[:200] if s.raw_content else "",
        }
        for s in snapshots
    ]


@router.post("/ingest/{competitor_id}")
def ingest_snapshots_for_competitor(
    competitor_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Triggers snapshot scraping and ingestion for a competitor."""
    competitor = db.get(Competitor, competitor_id)
    if not competitor or competitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")

    try:
        results = ingest_competitor_urls(db, competitor_id)
        return {"message": "Ingestion completed", "results": results}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(exc)}",
        )
