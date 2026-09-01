"""Integration test ของ endpoint ออเดอร์."""

import pytest

from app.dependencies import get_client_factory, get_token_cipher


@pytest.fixture
async def orders_client(
    api_client,
    cipher,
    user_factory,
    auth_headers,
    order_client_factory,
    normalized_order_factory,
):
    """client พร้อม JWT + marketplace client ปลอมที่คืนออเดอร์ 1 รายการ."""
    app = api_client._transport.app
    fake = order_client_factory(orders=[normalized_order_factory()])
    app.dependency_overrides[get_client_factory] = lambda: (lambda platform: fake)
    app.dependency_overrides[get_token_cipher] = lambda: cipher
    user = await user_factory(email="ops@example.com")
    api_client.headers.update(auth_headers(user))
    return api_client


class TestSyncOrders:
    async def test_sync_stores_orders(self, orders_client, shop_factory):
        # Arrange
        shop = await shop_factory()
        # Act
        response = await orders_client.post(f"/api/v1/shops/{shop.id}/sync/orders")
        # Assert
        assert response.status_code == 200
        assert response.json() == {"fetched": 1, "created": 1, "updated": 0}

    async def test_sync_unknown_shop_returns_404(self, orders_client):
        response = await orders_client.post("/api/v1/shops/999999/sync/orders")
        assert response.status_code == 404

    async def test_sync_requires_login(self, api_client, shop_factory):
        shop = await shop_factory()
        response = await api_client.post(f"/api/v1/shops/{shop.id}/sync/orders")
        assert response.status_code == 401


class TestListOrders:
    async def test_list_returns_synced_orders(self, orders_client, shop_factory):
        # Arrange
        shop = await shop_factory()
        await orders_client.post(f"/api/v1/shops/{shop.id}/sync/orders")
        # Act
        response = await orders_client.get(f"/api/v1/shops/{shop.id}/orders")
        # Assert
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["external_id"] == "217864843"
        assert body["items"][0]["status"] == "pending"

    async def test_list_empty_when_never_synced(self, orders_client, shop_factory):
        shop = await shop_factory()
        response = await orders_client.get(f"/api/v1/shops/{shop.id}/orders")
        assert response.json() == {"items": [], "total": 0}

    async def test_list_unknown_shop_returns_404(self, orders_client):
        assert (
            await orders_client.get("/api/v1/shops/999999/orders")
        ).status_code == 404

    async def test_list_rejects_invalid_limit(self, orders_client, shop_factory):
        shop = await shop_factory()
        response = await orders_client.get(f"/api/v1/shops/{shop.id}/orders?limit=0")
        assert response.status_code == 422

    async def test_orders_never_expose_tokens(self, orders_client, shop_factory):
        shop = await shop_factory(access_token="at-secret")
        await orders_client.post(f"/api/v1/shops/{shop.id}/sync/orders")
        response = await orders_client.get(f"/api/v1/shops/{shop.id}/orders")
        assert "at-secret" not in response.text
