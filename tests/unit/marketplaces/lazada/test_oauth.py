"""ตรวจ OAuth flow ของ Lazada."""

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest

from app.marketplaces.errors import MarketplaceError
from app.marketplaces.lazada.oauth import build_authorize_url, parse_token_response

NOW = datetime(2026, 9, 1, tzinfo=UTC)

VALID_PAYLOAD = {
    "code": "0",
    "access_token": "50000600a1b2c3",
    "refresh_token": "50001700d4e5f6",
    "expires_in": 604800,
    "refresh_expires_in": 2592000,
    "account_id": "100392024",
    "country": "th",
}


class TestBuildAuthorizeUrl:
    def test_authorize_url_contains_required_query_params(self):
        # Act
        url = build_authorize_url(
            authorize_url="https://auth.lazada.test/oauth/authorize",
            app_key="141659",
            redirect_uri="https://test.local/callback",
            state="random-state",
        )
        # Assert
        query = parse_qs(urlparse(url).query)
        assert query["response_type"] == ["code"]
        assert query["client_id"] == ["141659"]
        assert query["redirect_uri"] == ["https://test.local/callback"]
        assert query["state"] == ["random-state"]

    def test_authorize_url_keeps_base_url(self):
        url = build_authorize_url(
            "https://auth.lazada.test/oauth/authorize", "141659", "https://x/cb", "s"
        )
        assert url.startswith("https://auth.lazada.test/oauth/authorize?")


class TestParseTokenResponse:
    def test_valid_payload_returns_token_bundle(self):
        # Act
        bundle = parse_token_response(VALID_PAYLOAD, now=NOW)
        # Assert
        assert bundle.access_token == "50000600a1b2c3"
        assert bundle.account_id == "100392024"

    def test_expiry_is_computed_from_expires_in_not_hardcoded(self):
        """อายุ token ต้องมาจาก response จริง ตาม STANDARDS 0.2."""
        # Arrange
        payload = {**VALID_PAYLOAD, "expires_in": 100, "refresh_expires_in": 200}
        # Act
        bundle = parse_token_response(payload, now=NOW)
        # Assert
        assert (bundle.expires_at - NOW).total_seconds() == 100
        assert (bundle.refresh_expires_at - NOW).total_seconds() == 200

    def test_error_code_raises_marketplace_error(self):
        # Arrange
        payload = {"code": "IncompleteSignature", "message": "sign ผิด"}
        # Act & Assert
        with pytest.raises(MarketplaceError) as exc_info:
            parse_token_response(payload, now=NOW)
        assert exc_info.value.code == "IncompleteSignature"

    @pytest.mark.parametrize(
        "missing", ["access_token", "refresh_token", "expires_in", "account_id"]
    )
    def test_missing_field_raises_marketplace_error_not_key_error(self, missing):
        """field หายต้องได้ MarketplaceError ไม่ใช่ KeyError ทะลุขึ้น service."""
        # Arrange
        payload = {key: value for key, value in VALID_PAYLOAD.items() if key != missing}
        # Act & Assert
        with pytest.raises(MarketplaceError) as exc_info:
            parse_token_response(payload, now=NOW)
        assert exc_info.value.code == "MalformedResponse"

    def test_missing_code_field_is_treated_as_error(self):
        with pytest.raises(MarketplaceError):
            parse_token_response({"access_token": "x"}, now=NOW)
