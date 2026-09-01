"""ตรวจ registry ของ platform."""

import httpx
import pytest

from app.marketplaces.base import Platform
from app.marketplaces.lazada.client import LazadaClient
from app.marketplaces.registry import SUPPORTED_PLATFORMS, build_client
from app.marketplaces.shopee.client import ShopeeClient


class TestRegistry:
    @pytest.mark.parametrize(
        ("platform", "expected"),
        [(Platform.LAZADA, LazadaClient), (Platform.SHOPEE, ShopeeClient)],
    )
    def test_build_client_returns_right_type(self, platform, expected):
        assert isinstance(build_client(platform, httpx.AsyncClient()), expected)

    def test_unsupported_platform_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            build_client(Platform.TIKTOK, httpx.AsyncClient())

    def test_supported_platforms(self):
        assert {Platform.LAZADA, Platform.SHOPEE} == SUPPORTED_PLATFORMS


class TestProtocolConformance:
    @pytest.mark.parametrize("platform", [Platform.LAZADA, Platform.SHOPEE])
    def test_every_client_implements_full_contract(self, platform):
        """ทุก client ต้องมีเมธอดครบตาม MarketplaceClient protocol."""
        client = build_client(platform, httpx.AsyncClient())
        for method in (
            "build_authorize_url",
            "exchange_code",
            "refresh_token",
            "fetch_orders",
            "verify_webhook",
        ):
            assert callable(getattr(client, method)), f"{platform} ขาด {method}"
        assert client.platform is platform


class TestIsConfigured:
    def test_lazada_is_configured_in_test_env(self):
        """conftest ตั้ง LAZADA_APP_KEY/SECRET ไว้ให้แล้ว."""
        from app.marketplaces.registry import is_configured

        assert is_configured(Platform.LAZADA) is True

    def test_shopee_without_credentials_is_not_configured(self):
        from app.marketplaces.registry import is_configured

        assert is_configured(Platform.SHOPEE) is False

    def test_unimplemented_platform_is_not_configured(self):
        from app.marketplaces.registry import is_configured

        assert is_configured(Platform.TIKTOK) is False
