import uuid
from typing import Annotated, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.dependencies.auth import get_current_user, get_current_user_or_api_key
from app.models.user import User
from app.models.competitor import Competitor
from app.models.snapshot import Snapshot
from app.models.price_change import PriceChange
from app.models.sentiment_score import SentimentScore

router = APIRouter(prefix="/competitors", tags=["competitors"])


class CompetitorCreate(BaseModel):
    name: str
    pricing_url: Optional[str] = None
    review_urls: Optional[List[str]] = []
    news_keywords: Optional[List[str]] = []


@router.get("/")
def list_competitors(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user_or_api_key)],
):
    """Lists all competitors for the current authenticated user."""
    competitors = db.scalars(
        select(Competitor)
        .where(Competitor.user_id == current_user.id)
        .order_by(Competitor.created_at.desc())
    ).all()

    results = []
    for c in competitors:
        snap_count = db.scalar(
            select(func.count(Snapshot.id)).where(Snapshot.competitor_id == c.id)
        ) or 0
        price_change_count = db.scalar(
            select(func.count(PriceChange.id)).where(PriceChange.competitor_id == c.id)
        ) or 0
        avg_sentiment = db.scalar(
            select(func.avg(SentimentScore.score)).where(SentimentScore.competitor_id == c.id)
        )

        results.append({
            "id": str(c.id),
            "name": c.name,
            "pricing_url": c.pricing_url,
            "review_urls": c.review_urls or [],
            "news_keywords": c.news_keywords or [],
            "snapshot_count": snap_count,
            "price_change_count": price_change_count,
            "avg_sentiment": round(float(avg_sentiment), 3) if avg_sentiment is not None else None,
            "created_at": c.created_at.isoformat(),
        })

    return results


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_competitor(
    payload: CompetitorCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Creates a new competitor record."""
    competitor = Competitor(
        user_id=current_user.id,
        name=payload.name,
        pricing_url=payload.pricing_url,
        review_urls=payload.review_urls,
        news_keywords=payload.news_keywords,
    )
    db.add(competitor)
    db.commit()
    db.refresh(competitor)

    return {
        "id": str(competitor.id),
        "name": competitor.name,
        "pricing_url": competitor.pricing_url,
        "created_at": competitor.created_at.isoformat(),
    }


@router.get("/{competitor_id}")
def get_competitor_details(
    competitor_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Returns details for a single competitor."""
    competitor = db.get(Competitor, competitor_id)
    if not competitor or competitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")

    return {
        "id": str(competitor.id),
        "name": competitor.name,
        "pricing_url": competitor.pricing_url,
        "review_urls": competitor.review_urls or [],
        "news_keywords": competitor.news_keywords or [],
        "created_at": competitor.created_at.isoformat(),
    }


@router.delete("/{competitor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_competitor(
    competitor_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Deletes a competitor and all related data (snapshots, price changes,
    sentiment scores, agent runs, reports) via cascade.
    """
    competitor = db.get(Competitor, competitor_id)
    if not competitor or competitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")

    db.delete(competitor)
    db.commit()
    return None


@router.get("/{competitor_id}/price-history")
def get_price_history(
    competitor_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Returns historical price changes for Recharts.
    Includes `is_baseline` boolean to visually distinguish initial baseline price entries
    (where old_price is null) from genuine detected price adjustments.
    """
    competitor = db.get(Competitor, competitor_id)
    if not competitor or competitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")

    changes = db.scalars(
        select(PriceChange)
        .where(PriceChange.competitor_id == competitor_id)
        .order_by(PriceChange.detected_at.asc())
    ).all()

    return [
        {
            "id": str(pc.id),
            "tier_name": pc.tier_name or "General",
            "old_price": float(pc.old_price) if pc.old_price is not None else None,
            "new_price": float(pc.new_price) if pc.new_price is not None else 0.0,
            "is_baseline": pc.old_price is None,
            "detected_at": pc.detected_at.isoformat(),
            "formatted_date": pc.detected_at.strftime("%b %d, %H:%M"),
        }
        for pc in changes
    ]


@router.get("/{competitor_id}/sentiment-history")
def get_sentiment_history(
    competitor_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Returns historical sentiment scores for Recharts."""
    competitor = db.get(Competitor, competitor_id)
    if not competitor or competitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")

    scores = db.scalars(
        select(SentimentScore)
        .where(SentimentScore.competitor_id == competitor_id)
        .order_by(SentimentScore.scored_at.asc())
    ).all()

    return [
        {
            "id": str(ss.id),
            "score": ss.score,
            "source_type": ss.source_type,
            "topics": ss.topics or [],
            "scored_at": ss.scored_at.isoformat(),
            "formatted_date": ss.scored_at.strftime("%b %d, %H:%M"),
        }
        for ss in scores
    ]
