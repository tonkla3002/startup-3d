"""ตรวจ WebhookService — idempotency."""

from app.marketplaces.base import Platform
from app.services.webhook_service import WebhookService

PAYLOAD = {"message_id": "evt-1", "message_type": "order_status_update"}


class TestIngest:
    async def test_first_event_is_accepted(self, db_session):
        # Act
        result = await WebhookService(db_session).ingest(
            Platform.LAZADA, "evt-1", "order_status_update", PAYLOAD
        )
        # Assert
        assert result.duplicate is False

    async def test_same_event_twice_is_marked_duplicate(self, db_session):
        """marketplace ส่งซ้ำได้ — ครั้งที่สองต้องไม่ประมวลผลใหม่."""
        # Arrange
        service = WebhookService(db_session)
        await service.ingest(Platform.LAZADA, "evt-1", "type", PAYLOAD)
        # Act
        second = await service.ingest(Platform.LAZADA, "evt-1", "type", PAYLOAD)
        # Assert
        assert second.duplicate is True

    async def test_same_event_id_on_different_platform_is_not_duplicate(
        self, db_session
    ):
        service = WebhookService(db_session)
        await service.ingest(Platform.LAZADA, "evt-1", "type", PAYLOAD)
        other = await service.ingest(Platform.SHOPEE, "evt-1", "type", PAYLOAD)
        assert other.duplicate is False
