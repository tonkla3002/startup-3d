"""Integration test ของ social login.

**ไม่ยิง Google/GitHub จริง** — mock ที่ระดับ Authlib client ตาม PROJECT_RULES 4.6
"""

import pytest
from authlib.integrations.base_client import OAuthError

from app.dependencies import get_oauth_registry
from tests.conftest import FakeOAuthClient, FakeOAuthRegistry

GOOGLE_TOKEN = {
    "access_token": "provider-token",
    "userinfo": {
        "sub": "g-123",
        "email": "user@example.com",
        "email_verified": True,
        "name": "Test User",
    },
}


def _use(api_client, client):
    api_client._transport.app.dependency_overrides[get_oauth_registry] = (
        lambda: FakeOAuthRegistry(client)
    )
    return api_client


@pytest.fixture
def google_client(api_client):
    return _use(api_client, FakeOAuthClient(token=GOOGLE_TOKEN))


class TestOAuthLogin:
    async def test_login_redirects_to_provider(self, google_client):
        response = await google_client.get(
            "/api/v1/auth/google/login", follow_redirects=False
        )
        assert response.status_code == 307
        assert response.headers["location"].startswith("https://provider.test/consent")

    async def test_unsupported_provider_returns_404(self, google_client):
        response = await google_client.get("/api/v1/auth/facebook/login")
        assert response.status_code == 404

    async def test_unconfigured_provider_returns_503(self, api_client):
        client = _use(api_client, None)
        response = await client.get("/api/v1/auth/google/login")
        assert response.status_code == 503


class TestOAuthCallback:
    async def test_callback_creates_user_and_returns_jwt(self, google_client):
        # Act
        response = await google_client.get("/api/v1/auth/google/callback")
        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]

    async def test_callback_does_not_return_provider_token(self, google_client):
        """ห้ามส่ง access token ของ provider ให้ frontend (PROJECT_RULES 4.1)."""
        response = await google_client.get("/api/v1/auth/google/callback")
        assert "provider-token" not in response.text

    async def test_existing_user_logs_in_without_duplicate(
        self, google_client, db_session, user_factory
    ):
        # Arrange
        existing = await user_factory(
            email="user@example.com", provider="google", provider_user_id="g-123"
        )
        # Act
        response = await google_client.get("/api/v1/auth/google/callback")
        # Assert
        from app.core.config import SecuritySettings
        from app.core.security import decode_access_token

        settings = SecuritySettings()
        subject = decode_access_token(response.json()["access_token"], settings)
        assert subject == str(existing.id)

    async def test_unverified_email_returns_403(self, api_client):
        # Arrange
        token = {
            "userinfo": {
                "sub": "g-9",
                "email": "x@example.com",
                "email_verified": False,
            }
        }
        client = _use(api_client, FakeOAuthClient(token=token))
        # Act
        response = await client.get("/api/v1/auth/google/callback")
        # Assert
        assert response.status_code == 403

    async def test_inactive_user_returns_403(self, api_client, user_factory):
        # Arrange
        await user_factory(
            email="user@example.com",
            is_active=False,
            provider="google",
            provider_user_id="g-123",
        )
        client = _use(api_client, FakeOAuthClient(token=GOOGLE_TOKEN))
        # Act
        response = await client.get("/api/v1/auth/google/callback")
        # Assert
        assert response.status_code == 403

    async def test_provider_error_returns_400(self, api_client):
        # Arrange
        error = OAuthError(error="access_denied", description="user ปฏิเสธ")
        client = _use(api_client, FakeOAuthClient(error=error))
        # Act
        response = await client.get("/api/v1/auth/google/callback")
        # Assert
        assert response.status_code == 400


class TestGithubCallback:
    async def test_github_uses_primary_verified_email(self, api_client):
        # Arrange — GitHub ไม่ใช่ OIDC ต้องเรียก /user และ /user/emails แยก
        client = _use(
            api_client,
            FakeOAuthClient(
                token={"access_token": "t"},
                github_user={"id": 4242, "name": "GH User"},
                github_emails=[
                    {"email": "second@example.com", "primary": False, "verified": True},
                    {"email": "primary@example.com", "primary": True, "verified": True},
                ],
            ),
        )
        # Act
        response = await client.get("/api/v1/auth/github/callback")
        # Assert
        assert response.status_code == 200

    async def test_github_without_verified_email_returns_403(self, api_client):
        client = _use(
            api_client,
            FakeOAuthClient(
                token={"access_token": "t"},
                github_user={"id": 4242},
                github_emails=[
                    {"email": "a@example.com", "primary": True, "verified": False}
                ],
            ),
        )
        response = await client.get("/api/v1/auth/github/callback")
        assert response.status_code == 403


class TestReadMe:
    async def test_me_returns_current_user(
        self, api_client, user_factory, auth_headers
    ):
        # Arrange
        user = await user_factory(email="me@example.com")
        # Act
        response = await api_client.get("/api/v1/auth/me", headers=auth_headers(user))
        # Assert
        assert response.status_code == 200
        assert response.json()["email"] == "me@example.com"

    async def test_me_without_token_returns_401(self, api_client):
        assert (await api_client.get("/api/v1/auth/me")).status_code == 401

    async def test_me_never_exposes_password_hash(
        self, api_client, user_factory, auth_headers
    ):
        user = await user_factory()
        response = await api_client.get("/api/v1/auth/me", headers=auth_headers(user))
        assert "password" not in response.text.lower()
