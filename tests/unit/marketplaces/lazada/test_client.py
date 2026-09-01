"""ตรวจ LazadaClient: retry, error mapping, normalize, webhook signature.

ทุก test mock ด้วย respx — **ไม่ยิง API จริง** ตาม STANDARDS 4.1
"""

import hashlib
import hmac
from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.marketplaces.base import Platform, ShopCredentials
from app.marketplaces.errors import (
    MarketplaceError,
    MarketplaceUnavailableError,
    RateLimitError,
    TokenExpiredError,
)

ORDERS_URL = "https://api.lazada.test/rest/orders/get"
TOKEN_CREATE_URL = "https://auth.lazada.test/rest/auth/token/create"
TOKEN_REFRESH_URL = "https://auth.lazada.test/rest/auth/token/refresh"

SINCE = datetime(2026, 9, 1, tzinfo=UTC)

TOKEN_OK = {
    "code": "0",
    "access_token": "at-1",
    "refresh_token": "rt-1",
    "expires_in": 604800,
    "refresh_expires_in": 2592000,
    "account_id": "100392024",
}

ORDERS_OK = {
    "code": "0",
    "data": {
        "count": 1,
        "orders": [
            {
                "order_id": 217864843,
                "order_number": "217864843",
                "statuses": ["pending"],
                "price": "1250.50",
                "currency": "THB",
                "created_at": "2026-09-01 10:30:00 +0700",
                "updated_at": "2026-09-01 11:00:00 +0700",
            }
        ],
    },
}


@pytest.fixture
def credentials() -> ShopCredentials:
    return ShopCredentials(
        platform=Platform.LAZADA, account_id="100392024", access_token="at-1"
    )


class TestExchangeCode:
    @respx.mock
    async def test_exchange_code_success_returns_bundle(self, lazada_client):
        # Arrange
        respx.get(TOKEN_CREATE_URL).mock(
            return_value=httpx.Response(200, json=TOKEN_OK)
        )
        # Act
        bundle = await lazada_client.exchange_code("auth-code")
        # Assert
        assert bundle.access_token == "at-1"
        assert bundle.account_id == "100392024"

    @respx.mock
    async def test_exchange_code_sends_signed_params(self, lazada_client):
        # Arrange
        route = respx.get(TOKEN_CREATE_URL).mock(
            return_value=httpx.Response(200, json=TOKEN_OK)
        )
        # Act
        await lazada_client.exchange_code("auth-code")
        # Assert
        params = route.calls.last.request.url.params
        assert params["app_key"] == "141659"
        assert params["sign_method"] == "sha256"
        assert params["code"] == "auth-code"
        assert len(params["sign"]) == 64
        assert "access_token" not in params

    @respx.mock
    async def test_exchange_code_business_error_raises_without_retry(
        self, lazada_client
    ):
        """4xx business error ห้าม retry — ต้องยิงครั้งเดียวเท่านั้น."""
        # Arrange
        route = respx.get(TOKEN_CREATE_URL).mock(
            return_value=httpx.Response(
                200, json={"code": "IncompleteSignature", "message": "bad sign"}
            )
        )
        # Act & Assert
        with pytest.raises(MarketplaceError) as exc_info:
            await lazada_client.exchange_code("auth-code")
        assert exc_info.value.code == "IncompleteSignature"
        assert route.call_count == 1


class TestRefreshToken:
    @respx.mock
    async def test_refresh_token_success(self, lazada_client):
        respx.get(TOKEN_REFRESH_URL).mock(
            return_value=httpx.Response(200, json={**TOKEN_OK, "access_token": "at-2"})
        )
        bundle = await lazada_client.refresh_token("rt-1")
        assert bundle.access_token == "at-2"

    @respx.mock
    async def test_refresh_token_invalid_refresh_token_raises(self, lazada_client):
        respx.get(TOKEN_REFRESH_URL).mock(
            return_value=httpx.Response(
                200, json={"code": "InvalidRefreshToken", "message": "expired"}
            )
        )
        with pytest.raises(MarketplaceError):
            await lazada_client.refresh_token("rt-old")


class TestFetchOrders:
    @respx.mock
    async def test_fetch_orders_normalizes_payload(self, lazada_client, credentials):
        # Arrange
        respx.get(ORDERS_URL).mock(return_value=httpx.Response(200, json=ORDERS_OK))
        # Act
        orders = await lazada_client.fetch_orders(credentials, since=SINCE, limit=10)
        # Assert
        assert len(orders) == 1
        order = orders[0]
        assert order.order_id == "217864843"
        assert order.status == "pending"
        assert str(order.total_amount) == "1250.50"
        assert order.currency == "THB"
        assert order.platform is Platform.LAZADA
        assert order.account_id == "100392024"

    @respx.mock
    async def test_fetch_orders_empty_list_returns_empty(
        self, lazada_client, credentials
    ):
        respx.get(ORDERS_URL).mock(
            return_value=httpx.Response(200, json={"code": "0", "data": {"orders": []}})
        )
        assert await lazada_client.fetch_orders(credentials, since=SINCE) == []

    @respx.mock
    async def test_fetch_orders_attaches_access_token(self, lazada_client, credentials):
        route = respx.get(ORDERS_URL).mock(
            return_value=httpx.Response(200, json=ORDERS_OK)
        )
        await lazada_client.fetch_orders(credentials, since=SINCE)
        assert route.calls.last.request.url.params["access_token"] == "at-1"

    @respx.mock
    async def test_fetch_orders_malformed_order_raises_marketplace_error(
        self, lazada_client, credentials
    ):
        """ออเดอร์ที่ field หายต้องได้ MarketplaceError ไม่ใช่ KeyError."""
        respx.get(ORDERS_URL).mock(
            return_value=httpx.Response(
                200, json={"code": "0", "data": {"orders": [{"statuses": ["pending"]}]}}
            )
        )
        with pytest.raises(MarketplaceError) as exc_info:
            await lazada_client.fetch_orders(credentials, since=SINCE)
        assert exc_info.value.code == "MalformedOrder"

    @respx.mock
    async def test_fetch_orders_unparsable_date_returns_none_not_crash(
        self, lazada_client, credentials
    ):
        payload = {
            "code": "0",
            "data": {
                "orders": [
                    {
                        "order_id": 1,
                        "statuses": ["shipped"],
                        "price": "10",
                        "created_at": "ไม่ใช่วันที่",
                    }
                ]
            },
        }
        respx.get(ORDERS_URL).mock(return_value=httpx.Response(200, json=payload))
        orders = await lazada_client.fetch_orders(credentials, since=SINCE)
        assert orders[0].created_at is None

    @respx.mock
    async def test_fetch_orders_without_status_defaults_to_unknown(
        self, lazada_client, credentials
    ):
        payload = {
            "code": "0",
            "data": {"orders": [{"order_id": 1, "statuses": [], "price": "10"}]},
        }
        respx.get(ORDERS_URL).mock(return_value=httpx.Response(200, json=payload))
        orders = await lazada_client.fetch_orders(credentials, since=SINCE)
        assert orders[0].status == "unknown"


class TestRetryPolicy:
    @respx.mock
    async def test_http_429_retries_then_raises_rate_limit_error(
        self, lazada_client, credentials
    ):
        # Arrange
        route = respx.get(ORDERS_URL).mock(
            return_value=httpx.Response(429, json={"code": "ApiCallLimit"})
        )
        # Act & Assert
        with pytest.raises(RateLimitError):
            await lazada_client.fetch_orders(credentials, since=SINCE)
        assert route.call_count == 3

    @respx.mock
    async def test_rate_limit_code_in_200_body_is_detected(
        self, lazada_client, credentials
    ):
        """Lazada ตอบ 200 แม้จะ error — ต้องดู code ใน body ด้วย."""
        route = respx.get(ORDERS_URL).mock(
            return_value=httpx.Response(200, json={"code": "ApiCallLimit"})
        )
        with pytest.raises(RateLimitError):
            await lazada_client.fetch_orders(credentials, since=SINCE)
        assert route.call_count == 3

    @respx.mock
    async def test_recovers_on_second_attempt(self, lazada_client, credentials):
        # Arrange
        route = respx.get(ORDERS_URL).mock(
            side_effect=[
                httpx.Response(503, text="upstream down"),
                httpx.Response(200, json=ORDERS_OK),
            ]
        )
        # Act
        orders = await lazada_client.fetch_orders(credentials, since=SINCE)
        # Assert
        assert len(orders) == 1
        assert route.call_count == 2

    @respx.mock
    async def test_server_error_exhausts_retries_then_raises(
        self, lazada_client, credentials
    ):
        route = respx.get(ORDERS_URL).mock(
            return_value=httpx.Response(500, text="boom")
        )
        with pytest.raises(MarketplaceUnavailableError):
            await lazada_client.fetch_orders(credentials, since=SINCE)
        assert route.call_count == 3

    @respx.mock
    async def test_token_expired_is_not_retried(self, lazada_client, credentials):
        """token หมดอายุต้อง raise ทันทีให้ service ไป refresh ไม่ใช่ retry เปล่า ๆ."""
        route = respx.get(ORDERS_URL).mock(
            return_value=httpx.Response(
                200, json={"code": "IllegalAccessToken", "message": "expired"}
            )
        )
        with pytest.raises(TokenExpiredError):
            await lazada_client.fetch_orders(credentials, since=SINCE)
        assert route.call_count == 1

    @respx.mock
    async def test_non_json_response_raises_marketplace_error(
        self, lazada_client, credentials
    ):
        respx.get(ORDERS_URL).mock(return_value=httpx.Response(200, text="<html>502"))
        with pytest.raises(MarketplaceError) as exc_info:
            await lazada_client.fetch_orders(credentials, since=SINCE)
        assert exc_info.value.code == "MalformedResponse"


class TestVerifyWebhook:
    def test_valid_signature_passes(self, lazada_client, app_secret):
        # Arrange
        body = b'{"message_id":"m-1"}'
        signature = (
            hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest().upper()
        )
        # Act & Assert
        assert lazada_client.verify_webhook(body, signature) is True

    def test_signature_is_case_insensitive(self, lazada_client, app_secret):
        body = b'{"message_id":"m-1"}'
        lower = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
        assert lazada_client.verify_webhook(body, lower) is True

    def test_wrong_signature_fails(self, lazada_client):
        assert lazada_client.verify_webhook(b'{"a":1}', "DEADBEEF") is False

    def test_empty_signature_fails(self, lazada_client):
        assert lazada_client.verify_webhook(b'{"a":1}', "") is False

    def test_tampered_body_fails(self, lazada_client, app_secret):
        """เปลี่ยน body แม้ตัวเดียว signature เดิมต้องใช้ไม่ได้."""
        original = b'{"amount":100}'
        signature = (
            hmac.new(app_secret.encode(), original, hashlib.sha256).hexdigest().upper()
        )
        assert lazada_client.verify_webhook(b'{"amount":999}', signature) is False


class TestBuildAuthorizeUrlOnClient:
    def test_client_builds_authorize_url_from_settings(self, lazada_client):
        url = lazada_client.build_authorize_url("state-123")
        assert url.startswith("https://auth.lazada.test/oauth/authorize?")
        assert "state=state-123" in url
        assert "client_id=141659" in url
