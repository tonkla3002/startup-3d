"""ตรวจ WebhookEventRepository กับ Postgres จริง (JSONB behavior ต่างจาก mock)."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.marketplaces.base import Platform
from app.repositories.webhook_event_repository import WebhookEventRepository


class TestWebhookEventRepository:
    async def test_add_then_get_returns_event(self, db_session):
        # Arrange
        repo = WebhookEventRepository(db_session)
        repo.add(Platform.LAZADA, "evt-1", "order_status_update", {"order_id": 1})
        await db_session.commit()
        # Act
        found = await repo.get(Platform.LAZADA, "evt-1")
        # Assert
        assert found is not None
        assert found.payload == {"order_id": 1}

    async def test_get_returns_none_for_unknown_event(self, db_session):
        repo = WebhookEventRepository(db_session)
        assert await repo.get(Platform.LAZADA, "never-seen") is None

    async def test_duplicate_event_id_violates_unique_constraint(self, db_session):
        """constraint ระดับ DB คือด่านสุดท้ายกัน event ซ้ำ แม้ race กัน."""
        # Arrange
        repo = WebhookEventRepository(db_session)
        repo.add(Platform.LAZADA, "evt-dup", "type", {})
        await db_session.commit()
        # Act & Assert
        repo.add(Platform.LAZADA, "evt-dup", "type", {})
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()
