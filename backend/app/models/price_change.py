import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PriceChange(Base):
    __tablename__ = "price_changes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    competitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("competitors.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_before_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("snapshots.id", ondelete="SET NULL"), nullable=True
    )
    snapshot_after_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("snapshots.id", ondelete="SET NULL"), nullable=True
    )
    tier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    old_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    new_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    competitor = relationship("Competitor", back_populates="price_changes")
    snapshot_before = relationship("Snapshot", foreign_keys=[snapshot_before_id])
    snapshot_after = relationship("Snapshot", foreign_keys=[snapshot_after_id])
