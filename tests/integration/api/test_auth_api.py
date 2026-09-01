"""Integration test ของการผูกร้าน marketplace (ต้องล็อกอินก่อน)."""

import pytest

from app.dependencies import get_marketplace_client, get_token_cipher
from app.marketplaces.base import Platform
from app.marketplaces.errors import MarketplaceError


@pytest.fixture
async def auth_client(api_client, fake_client, cipher, user_factory, auth_headers):
    """override client + cipher ให้ endpoint ใช้ของปลอม และแนบ JWT ให้ทุก request."""
    app = api_client._transport.app
    app.dependency_overrides[get_marketplace_client] = lambda: fake_client
    app.dependency_overrides[get_token_cipher] = lambda: cipher
    user = await user_factory(email="operator@example.com")
    api_client.headers.update(auth_headers(user))
    return api_client


class TestAuthorizeEndpoint:
    async def test_authorize_redirects_to_marketplace(self, auth_client):
        # Act
        response = await auth_client.get(
            "/api/v1/connections/lazada/authorize", follow_redirects=False
        )
        # Assert
        assert response.status_code == 307
        assert response.headers["location"].startswith(
            "https://auth.lazada.test/oauth/authorize"
        )

    async def test_authorize_unknown_platform_returns_422(self, auth_client):
        response = await auth_client.get("/api/v1/connections/facebook/authorize")
        assert response.status_code == 422


class TestCallbackEndpoint:
    async def test_callback_with_valid_state_authorizes_shop(self, auth_client):
        # Arrange
        redirect = await auth_client.get(
            "/api/v1/connections/lazada/authorize", follow_redirects=False
        )
        state = redirect.headers["location"].split("state=")[1]
        # Act
        response = await auth_client.get(
            "/api/v1/connections/lazada/callback",
            params={"code": "c-1", "state": state},
        )
        # Assert
        assert response.status_code == 200
        assert response.json() == {"status": "authorized", "account_id": "100392024"}

    async def test_callback_with_forged_state_returns_400(self, auth_client):
        response = await auth_client.get(
            "/api/v1/connections/lazada/callback",
            params={"code": "c", "state": "forged"},
        )
        assert response.status_code == 400

    async def test_callback_missing_code_returns_422(self, auth_client):
        response = await auth_client.get(
            "/api/v1/connections/lazada/callback", params={"state": "s"}
        )
        assert response.status_code == 422

    async def test_marketplace_error_returns_502(self, auth_client, fake_client):
        # Arrange
        redirect = await auth_client.get(
            "/api/v1/connections/lazada/authorize", follow_redirects=False
        )
        state = redirect.headers["location"].split("state=")[1]

        async def _boom(code: str):
            raise MarketplaceError("lazada", "IncompleteSignature", "bad sign")

        fake_client.exchange_code = _boom
        # Act
        response = await auth_client.get(
            "/api/v1/connections/lazada/callback", params={"code": "c", "state": state}
        )
        # Assert
        assert response.status_code == 502
        assert response.json()["detail"] == "bad sign"

    async def test_response_never_contains_tokens(self, auth_client):
        redirect = await auth_client.get(
            "/api/v1/connections/lazada/authorize", follow_redirects=False
        )
        state = redirect.headers["location"].split("state=")[1]
        response = await auth_client.get(
            "/api/v1/connections/lazada/callback",
            params={"code": "c-1", "state": state},
        )
        body = response.text
        assert "at-new" not in body
        assert "rt-new" not in body


class TestUnsupportedPlatform:
    async def test_shopee_not_implemented_returns_404(
        self, api_client, user_factory, auth_headers
    ):
        """platform ที่ยังไม่ implement ต้องตอบ 404 ไม่ใช่ 500."""
        user = await user_factory(email="op2@example.com")
        response = await api_client.get(
            "/api/v1/connections/shopee/authorize",
            headers=auth_headers(user),
            follow_redirects=False,
        )
        assert response.status_code == 404


class TestPlatformEnum:
    def test_all_platform_values_are_lowercase(self):
        assert [p.value for p in Platform] == ["lazada", "shopee", "tiktok"]
