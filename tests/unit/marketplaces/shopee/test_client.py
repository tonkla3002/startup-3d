"""ตรวจ ShopeeClient — mock ด้วย respx ไม่ยิงของจริง."""

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

ORDER_LIST_URL = "https://partner.shopee.test/api/v2/order/get_order_list"
TOKEN_URL = "https://partner.shopee.test/api/v2/auth/token/get"
REFRESH_URL = "https://partner.shopee.test/api/v2/auth/access_token/get"

SINCE = datetime(2026, 9, 1, tzinfo=UTC)

TOKEN_OK = {
    "error": "",
    "access_token": "at-1",
    "refresh_token": "rt-1",
    "expire_in": 14400,
    "shop_id": 210251695,
}

ORDERS_OK = {
    "error": "",
    "response": {
        "order_list": [
            {
                "order_sn": "220101ABCDEF",
                "order_status": "READY_TO_SHIP",
                "total_amount": "899.00",
                "currency": "THB",
                "create_time": 1756700000,
                "update_time": 1756800000,
            }
        ]
    },
}


@pytest.fixture
def credentials() -> ShopCredentials:
    return ShopCredentials(
        platform=Platform.SHOPEE, account_id="210251695", access_token="at-1"
    )


class TestAuthorizeUrl:
    def test_authorize_url_uses_redirect_param_and_is_signed(self, shopee_client):
        """Shopee ใช้ชื่อ param ว่า redirect ไม่ใช่ redirect_uri."""
        url = shopee_client.build_authorize_url("state-abc")
        assert url.startswith("https://partner.shopee.test/api/v2/shop/auth_partner?")
        assert "redirect=" in url
        assert "redirect_uri=" not in url
        assert "sign=" in url
        assert "state-abc" in url


class TestExchangeCode:
    @respx.mock
    async def test_exchange_code_returns_bundle(self, shopee_client):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=TOKEN_OK))
        bundle = await shopee_client.exchange_code("code-1")
        assert bundle.access_token == "at-1"
        assert bundle.account_id == "210251695"

    @respx.mock
    async def test_expiry_comes_from_expire_in(self, shopee_client):
        respx.post(TOKEN_URL).mock(
            return_value=httpx.Response(200, json={**TOKEN_OK, "expire_in": 60})
        )
        bundle = await shopee_client.exchange_code("code-1")
        delta = (bundle.expires_at - datetime.now(UTC)).total_seconds()
        assert 55 < delta <= 60

    @respx.mock
    async def test_missing_field_raises_marketplace_error(self, shopee_client):
        respx.post(TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"error": "", "access_token": "x"})
        )
        with pytest.raises(MarketplaceError) as exc_info:
            await shopee_client.exchange_code("code-1")
        assert exc_info.value.code == "MalformedResponse"

    @respx.mock
    async def test_refresh_token_returns_bundle(self, shopee_client):
        respx.post(REFRESH_URL).mock(
            return_value=httpx.Response(200, json={**TOKEN_OK, "access_token": "at-2"})
        )
        assert (await shopee_client.refresh_token("rt-1")).access_token == "at-2"


class TestFetchOrders:
    @respx.mock
    async def test_orders_are_normalized(self, shopee_client, credentials):
        # Arrange
        respx.get(ORDER_LIST_URL).mock(return_value=httpx.Response(200, json=ORDERS_OK))
        # Act
        orders = await shopee_client.fetch_orders(credentials, since=SINCE)
        # Assert
        order = orders[0]
        assert order.platform is Platform.SHOPEE
        assert order.order_id == "220101ABCDEF"
        assert order.status == "ready_to_ship"
        assert str(order.total_amount) == "899.00"
        assert order.created_at is not None

    @respx.mock
    async def test_shop_level_call_is_signed_with_token_and_shop_id(
        self, shopee_client, credentials
    ):
        route = respx.get(ORDER_LIST_URL).mock(
            return_value=httpx.Response(200, json=ORDERS_OK)
        )
        await shopee_client.fetch_orders(credentials, since=SINCE)
        params = route.calls.last.request.url.params
        assert params["access_token"] == "at-1"
        assert params["shop_id"] == "210251695"
        assert params["sign"].islower()

    @respx.mock
    async def test_empty_order_list(self, shopee_client, credentials):
        respx.get(ORDER_LIST_URL).mock(
            return_value=httpx.Response(200, json={"error": "", "response": {}})
        )
        assert await shopee_client.fetch_orders(credentials, since=SINCE) == []

    @respx.mock
    async def test_malformed_order_raises(self, shopee_client, credentials):
        respx.get(ORDER_LIST_URL).mock(
            return_value=httpx.Response(
                200, json={"error": "", "response": {"order_list": [{"x": 1}]}}
            )
        )
        with pytest.raises(MarketplaceError) as exc_info:
            await shopee_client.fetch_orders(credentials, since=SINCE)
        assert exc_info.value.code == "MalformedOrder"

    @respx.mock
    async def test_bad_epoch_becomes_none(self, shopee_client, credentials):
        payload = {
            "error": "",
            "response": {
                "order_list": [
                    {"order_sn": "X", "total_amount": "1", "create_time": "ไม่ใช่เวลา"}
                ]
            },
        }
        respx.get(ORDER_LIST_URL).mock(return_value=httpx.Response(200, json=payload))
        orders = await shopee_client.fetch_orders(credentials, since=SINCE)
        assert orders[0].created_at is None


class TestErrorMapping:
    @respx.mock
    async def test_error_field_in_200_body_is_detected(
        self, shopee_client, credentials
    ):
        """Shopee ใช้ field error (ว่าง = สำเร็จ) ไม่ใช่ code แบบ Lazada."""
        respx.get(ORDER_LIST_URL).mock(
            return_value=httpx.Response(
                200, json={"error": "error_param", "message": "param ผิด"}
            )
        )
        with pytest.raises(MarketplaceError) as exc_info:
            await shopee_client.fetch_orders(credentials, since=SINCE)
        assert exc_info.value.code == "error_param"

    @respx.mock
    async def test_rate_limit_retries_then_raises(self, shopee_client, credentials):
        route = respx.get(ORDER_LIST_URL).mock(
            return_value=httpx.Response(200, json={"error": "error_rate_limit"})
        )
        with pytest.raises(RateLimitError):
            await shopee_client.fetch_orders(credentials, since=SINCE)
        assert route.call_count == 3

    @respx.mock
    async def test_token_error_is_not_retried(self, shopee_client, credentials):
        route = respx.get(ORDER_LIST_URL).mock(
            return_value=httpx.Response(200, json={"error": "error_auth"})
        )
        with pytest.raises(TokenExpiredError):
            await shopee_client.fetch_orders(credentials, since=SINCE)
        assert route.call_count == 1

    @respx.mock
    async def test_server_error_retries(self, shopee_client, credentials):
        route = respx.get(ORDER_LIST_URL).mock(return_value=httpx.Response(502))
        with pytest.raises(MarketplaceUnavailableError):
            await shopee_client.fetch_orders(credentials, since=SINCE)
        assert route.call_count == 3

    @respx.mock
    async def test_recovers_after_transient_failure(self, shopee_client, credentials):
        route = respx.get(ORDER_LIST_URL).mock(
            side_effect=[httpx.Response(503), httpx.Response(200, json=ORDERS_OK)]
        )
        assert len(await shopee_client.fetch_orders(credentials, since=SINCE)) == 1
        assert route.call_count == 2

    @respx.mock
    async def test_non_json_raises(self, shopee_client, credentials):
        respx.get(ORDER_LIST_URL).mock(return_value=httpx.Response(200, text="<html>"))
        with pytest.raises(MarketplaceError):
            await shopee_client.fetch_orders(credentials, since=SINCE)


class TestVerifyWebhook:
    def test_valid_signature_passes(self, shopee_client, shopee_settings):
        body = b'{"code":3,"data":{}}'
        base = f"{shopee_settings.webhook_url}|".encode() + body
        signature = hmac.new(
            shopee_settings.partner_key.get_secret_value().encode(),
            base,
            hashlib.sha256,
        ).hexdigest()
        assert shopee_client.verify_webhook(body, signature) is True

    def test_tampered_body_fails(self, shopee_client, shopee_settings):
        body = b'{"amount":1}'
        base = f"{shopee_settings.webhook_url}|".encode() + body
        signature = hmac.new(
            shopee_settings.partner_key.get_secret_value().encode(),
            base,
            hashlib.sha256,
        ).hexdigest()
        assert shopee_client.verify_webhook(b'{"amount":999}', signature) is False

    def test_empty_signature_fails(self, shopee_client):
        assert shopee_client.verify_webhook(b"{}", "") is False
