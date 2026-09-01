"""Event ที่รับมาจาก marketplace — ใช้ทำ idempotency."""

from datetime import datetime

from sqlalchemy import DateTime, Enum, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.marketplaces.base import Platform
from app.models.base import Base, TimestampMixin


class WebhookEvent(Base, TimestampMixin):
    """บันทึก event ที่เคยรับแล้ว กันประมวลผลซ้ำเมื่อ marketplace ส่งซ้ำ."""

    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("platform", "event_id", name="uq_webhook_events_platform"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, name="platform_enum", native_enum=False, length=16),
        nullable=False,
    )
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
