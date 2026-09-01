"""Integration test ของ /shops (ต้องล็อกอินก่อน)."""

import pytest


@pytest.fixture
async def shops_client(api_client, user_factory, auth_headers):
    """client ที่แนบ JWT ให้ทุก request."""
    user = await user_factory(email="viewer@example.com")
    api_client.headers.update(auth_headers(user))
    return api_client


class TestListShops:
    async def test_returns_empty_list_when_no_shops(self, shops_client):
        response = await shops_client.get("/api/v1/shops")
        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0}

    async def test_returns_active_shops(self, shops_client, shop_factory):
        # Arrange
        await shop_factory(account_id="100392024")
        # Act
        response = await shops_client.get("/api/v1/shops")
        # Assert
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["account_id"] == "100392024"

    async def test_response_never_exposes_tokens(self, shops_client, shop_factory):
        """กฎเหล็ก STANDARDS 8.2 — token ห้ามออกทาง API ของเรา."""
        # Arrange
        await shop_factory(access_token="at-secret", refresh_token="rt-secret")
        # Act
        response = await shops_client.get("/api/v1/shops")
        # Assert
        assert "at-secret" not in response.text
        assert "token" not in response.text.lower()

    async def test_filters_by_platform(self, shops_client, shop_factory):
        from app.marketplaces.base import Platform

        await shop_factory(account_id="lz", platform=Platform.LAZADA)
        await shop_factory(account_id="sp", platform=Platform.SHOPEE)
        response = await shops_client.get(
            "/api/v1/shops", params={"platform": "shopee"}
        )
        assert [item["account_id"] for item in response.json()["items"]] == ["sp"]
