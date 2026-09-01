"""Data access ของ webhook_events."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.marketplaces.base import Platform
from app.models.webhook_event import WebhookEvent


class WebhookEventRepository:
    """Query ที่เกี่ยวกับ webhook event ทั้งหมดอยู่ที่นี่."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, platform: Platform, event_id: str) -> WebhookEvent | None:
        """หา event ที่เคยรับไว้แล้ว."""
        result = await self.db.execute(
            select(WebhookEvent).where(
                WebhookEvent.platform == platform,
                WebhookEvent.event_id == event_id,
            )
        )
        return result.scalar_one_or_none()

    def add(
        self,
        platform: Platform,
        event_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> WebhookEvent:
        """บันทึก event ใหม่เข้า session (commit ที่ service)."""
        event = WebhookEvent(
            platform=platform,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
        )
        self.db.add(event)
        return event
