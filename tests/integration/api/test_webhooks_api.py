"""Integration test ของ webhook receiver."""

import pytest

from app.dependencies import get_marketplace_client
from tests.conftest import FakeMarketplaceClient

PAYLOAD = {"message_id": "evt-1", "message_type": "order_status_update", "data": {}}


def _override(api_client, client):
    api_client._transport.app.dependency_overrides[get_marketplace_client] = (
        lambda: client
    )
    return api_client


@pytest.fixture
def webhook_client(api_client, fake_client):
    return _override(api_client, fake_client)


class TestWebhookSignature:
    async def test_valid_signature_is_accepted(self, webhook_client):
        # Act
        response = await webhook_client.post("/api/v1/webhooks/lazada", json=PAYLOAD)
        # Assert
        assert response.status_code == 200
        assert response.json() == {"received": True, "duplicate": False}

    async def test_invalid_signature_returns_401(self, api_client):
        # Arrange
        client = _override(api_client, FakeMarketplaceClient(signature_valid=False))
        # Act
        response = await client.post("/api/v1/webhooks/lazada", json=PAYLOAD)
        # Assert
        assert response.status_code == 401

    async def test_invalid_signature_does_not_store_event(self, api_client, db_session):
        # Arrange
        client = _override(api_client, FakeMarketplaceClient(signature_valid=False))
        await client.post("/api/v1/webhooks/lazada", json=PAYLOAD)
        # Assert
        from app.marketplaces.base import Platform
        from app.repositories.webhook_event_repository import WebhookEventRepository

        assert (
            await WebhookEventRepository(db_session).get(Platform.LAZADA, "evt-1")
            is None
        )


class TestWebhookIdempotency:
    async def test_duplicate_event_is_reported_and_not_reprocessed(
        self, webhook_client
    ):
        # Arrange
        await webhook_client.post("/api/v1/webhooks/lazada", json=PAYLOAD)
        # Act
        second = await webhook_client.post("/api/v1/webhooks/lazada", json=PAYLOAD)
        # Assert
        assert second.status_code == 200
        assert second.json()["duplicate"] is True


class TestWebhookPayloadValidation:
    async def test_missing_message_id_returns_422(self, webhook_client):
        response = await webhook_client.post(
            "/api/v1/webhooks/lazada", json={"message_type": "x"}
        )
        assert response.status_code == 422

    async def test_non_json_body_returns_422(self, webhook_client):
        response = await webhook_client.post(
            "/api/v1/webhooks/lazada",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 422

    async def test_accepts_event_id_alias(self, webhook_client):
        """รองรับทั้ง message_id (Lazada) และ event_id (เจ้าอื่น)."""
        response = await webhook_client.post(
            "/api/v1/webhooks/lazada",
            json={"event_id": "evt-9", "event_type": "order_update"},
        )
        assert response.status_code == 200
