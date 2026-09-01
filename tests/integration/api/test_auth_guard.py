"""ตรวจว่า endpoint ที่ต้องล็อกอินถูกป้องกันจริง."""

import pytest

PROTECTED = [
    ("get", "/api/v1/shops"),
    ("get", "/api/v1/connections/lazada/authorize"),
    ("get", "/api/v1/connections/lazada/callback?code=c&state=s"),
]


class TestProtectedEndpoints:
    @pytest.mark.parametrize(("method", "path"), PROTECTED)
    async def test_requires_token(self, api_client, method, path):
        response = await getattr(api_client, method)(path, follow_redirects=False)
        assert response.status_code == 401

    @pytest.mark.parametrize(("method", "path"), PROTECTED)
    async def test_rejects_garbage_token(self, api_client, method, path):
        response = await getattr(api_client, method)(
            path,
            headers={"Authorization": "Bearer not.a.jwt"},
            follow_redirects=False,
        )
        assert response.status_code == 401

    async def test_token_of_deactivated_user_is_rejected(
        self, api_client, user_factory, auth_headers
    ):
        """ปิดบัญชีแล้ว token เดิมต้องใช้ไม่ได้ทันที."""
        user = await user_factory(is_active=False)
        response = await api_client.get("/api/v1/shops", headers=auth_headers(user))
        assert response.status_code == 401


class TestPublicEndpoints:
    async def test_health_is_public(self, api_client):
        assert (await api_client.get("/api/v1/health")).status_code == 200

    async def test_webhook_is_public(self, api_client, fake_client):
        """marketplace เรียก webhook เอง — ต้องไม่บังคับ JWT แต่ verify signature แทน."""
        from app.dependencies import get_marketplace_client

        api_client._transport.app.dependency_overrides[get_marketplace_client] = (
            lambda: fake_client
        )
        response = await api_client.post(
            "/api/v1/webhooks/lazada",
            json={"message_id": "evt-public", "message_type": "t"},
        )
        assert response.status_code == 200
