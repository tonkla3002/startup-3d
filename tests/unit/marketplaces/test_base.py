"""ตรวจ contract กลางของ marketplace layer."""

from datetime import UTC, datetime

from app.marketplaces.base import Platform, ShopCredentials, TokenBundle


class TestTokenBundle:
    def test_repr_does_not_leak_access_token(self):
        """token ห้ามหลุดผ่าน repr เพราะ repr โผล่ใน log/traceback ได้ง่าย."""
        # Arrange
        bundle = TokenBundle(
            access_token="leaked-token-123",
            refresh_token="leaked-refresh-456",
            expires_at=datetime(2026, 9, 8, tzinfo=UTC),
            refresh_expires_at=datetime(2026, 10, 1, tzinfo=UTC),
            account_id="seller-1",
        )
        # Act
        rendered = repr(bundle)
        # Assert
        assert "leaked-token-123" not in rendered
        assert "leaked-refresh-456" not in rendered
        assert "seller-1" in rendered


class TestShopCredentials:
    def test_credentials_carry_platform_and_account(self):
        creds = ShopCredentials(
            platform=Platform.LAZADA, account_id="seller-1", access_token="t"
        )
        assert creds.platform is Platform.LAZADA
        assert creds.platform.value == "lazada"
