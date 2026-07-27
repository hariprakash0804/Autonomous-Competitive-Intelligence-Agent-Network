import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, ARRAY, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Competitor(Base):
    __tablename__ = "competitors"
    __table_args__ = (
        UniqueConstraint("user_id", "domain", name="uq_user_competitor_domain"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    pricing_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    review_urls: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    news_keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user = relationship("User", back_populates="competitors")
    snapshots = relationship("Snapshot", back_populates="competitor", cascade="all, delete-orphan")
    price_changes = relationship("PriceChange", back_populates="competitor", cascade="all, delete-orphan")
    sentiment_scores = relationship("SentimentScore", back_populates="competitor", cascade="all, delete-orphan")
    agent_runs = relationship("AgentRun", back_populates="competitor", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="competitor", cascade="all, delete-orphan")
