import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Text, Boolean, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SourceType(str, enum.Enum):
    PRICING = "pricing"
    REVIEW = "review"
    NEWS = "news"


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    competitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("competitors.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[SourceType] = mapped_column(
        SAEnum(SourceType, name="source_type_enum", create_constraint=True),
        nullable=False,
    )
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    competitor = relationship("Competitor", back_populates="snapshots")
    sentiment_scores = relationship("SentimentScore", back_populates="snapshot", cascade="all, delete-orphan")
