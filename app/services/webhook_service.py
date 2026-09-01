"""รับ event จาก marketplace แบบ idempotent."""

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import StreamoraError
from app.marketplaces.base import Platform
from app.repositories.webhook_event_repository import WebhookEventRepository

logger = logging.getLogger(__name__)


class InvalidWebhookSignatureError(StreamoraError):
    """Signature ของ webhook ไม่ถูกต้อง."""


@dataclass(frozen=True, slots=True)
class IngestResult:
    """ผลของการรับ event 1 ตัว.

    Attributes:
        event_id: id ของ event
        duplicate: True เมื่อเคยรับ event นี้แล้ว (ข้ามการประมวลผลซ้ำ)
    """

    event_id: str
    duplicate: bool


class WebhookService:
    """ตรวจ signature + กันประมวลผลซ้ำ."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.events = WebhookEventRepository(db)

    async def ingest(
        self,
        platform: Platform,
        event_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> IngestResult:
        """บันทึก event ถ้ายังไม่เคยรับ.

        Returns:
            IngestResult ที่บอกว่าเป็น event ซ้ำหรือไม่
        """
        existing = await self.events.get(platform, event_id)
        if existing is not None:
            logger.info(
                "webhook duplicate platform=%s event_id=%s", platform.value, event_id
            )
            return IngestResult(event_id=event_id, duplicate=True)

        self.events.add(
            platform=platform,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
        )
        await self.db.commit()
        logger.info(
            "webhook accepted platform=%s event_id=%s", platform.value, event_id
        )
        return IngestResult(event_id=event_id, duplicate=False)
