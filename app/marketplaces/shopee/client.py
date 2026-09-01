"""HTTP client ของ Shopee Open Platform v2.

โครงเหมือน LazadaClient แต่ต่างที่วิธีเซ็น, รูปแบบ error และชื่อ field
— service layer ไม่ต้องรู้เรื่องพวกนี้เลย
"""

import asyncio
import hashlib
import hmac
import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import ShopeeSettings
from app.marketplaces.base import Platform, ShopCredentials, TokenBundle
from app.marketplaces.errors import (
    MarketplaceError,
    MarketplaceUnavailableError,
    RateLimitError,
    TokenExpiredError,
)
from app.marketplaces.schemas import NormalizedOrder
from app.marketplaces.shopee import endpoints
from app.marketplaces.shopee.signer import build_common_params, current_timestamp_s

logger = logging.getLogger(__name__)

PLATFORM = "shopee"

RATE_LIMIT_CODES = frozenset({"error_rate_limit", "error_too_many_request"})
TOKEN_ERROR_CODES = frozenset(
    {"error_auth", "error_token", "invalid_access_token", "error_permission"}
)

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = 0.5

# อายุ token ที่ Shopee ตอบมาในหน่วยวินาที — ใช้ค่านี้เฉพาะตอน response ไม่ระบุ
FALLBACK_REFRESH_TTL = timedelta(days=30)


class ShopeeClient:
    """Client สำหรับเรียก Shopee Open Platform API."""

    platform = Platform.SHOPEE

    def __init__(
        self,
        http: httpx.AsyncClient,
        settings: ShopeeSettings,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        """สร้าง client (พารามิเตอร์ความหมายเดียวกับ LazadaClient)."""
        self._http = http
        self._settings = settings
        self._max_attempts = max_attempts
        self._backoff = backoff_seconds
        self._sleep = sleep or asyncio.sleep

    @property
    def _partner_key(self) -> str:
        return self._settings.partner_key.get_secret_value()

    def build_authorize_url(self, state: str) -> str:
        """สร้าง URL ให้ผู้ขายกดอนุญาตสิทธิ์.

        Shopee ใช้ ``redirect`` เป็นชื่อ param (ไม่ใช่ ``redirect_uri``)
        และต้องเซ็น path ``/api/v2/shop/auth_partner`` ด้วย
        """
        timestamp = current_timestamp_s()
        params = build_common_params(
            partner_id=self._settings.partner_id,
            partner_key=self._partner_key,
            api_path=endpoints.AUTH_PARTNER,
            timestamp=timestamp,
        )
        params["redirect"] = f"{self._settings.redirect_uri}?state={state}"
        return (
            f"{self._settings.api_base_url}{endpoints.AUTH_PARTNER}?{urlencode(params)}"
        )

    async def exchange_code(self, code: str) -> TokenBundle:
        """แลก code เป็น token (Shopee ส่ง shop_id มาพร้อม callback)."""
        payload = await self._request(
            api_path=endpoints.TOKEN_CREATE,
            body={
                "code": code,
                "partner_id": int(self._settings.partner_id),
                "shop_id": int(self._settings.default_shop_id or 0),
            },
        )
        return self._parse_token(payload)

    async def refresh_token(self, refresh_token: str) -> TokenBundle:
        """ต่ออายุ access token."""
        payload = await self._request(
            api_path=endpoints.TOKEN_REFRESH,
            body={
                "refresh_token": refresh_token,
                "partner_id": int(self._settings.partner_id),
                "shop_id": int(self._settings.default_shop_id or 0),
            },
        )
        return self._parse_token(payload)

    async def fetch_orders(
        self, credentials: ShopCredentials, since: datetime, limit: int = 100
    ) -> list[NormalizedOrder]:
        """ดึงออเดอร์ที่อัปเดตหลังเวลาที่กำหนด."""
        payload = await self._request(
            api_path=endpoints.ORDER_LIST,
            credentials=credentials,
            query={
                "time_range_field": "create_time",
                "time_from": str(int(since.timestamp())),
                "time_to": str(int(datetime.now(UTC).timestamp())),
                "page_size": str(limit),
            },
        )
        raw_orders = payload.get("response", {}).get("order_list", [])
        return [
            self._normalize_order(order, credentials.account_id) for order in raw_orders
        ]

    def verify_webhook(self, raw_body: bytes, signature: str) -> bool:
        """ตรวจ signature ของ push message จาก Shopee.

        Shopee เซ็น ``url + "|" + raw_body`` ด้วย partner_key แล้วส่งมาใน
        header ``Authorization`` — ⚠️ ต้องยืนยัน URL ที่ใช้เซ็นกับ docs ก่อน go-live
        """
        base = f"{self._settings.webhook_url}|".encode() + raw_body
        expected = hmac.new(
            self._partner_key.encode("utf-8"), base, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature.strip().lower())

    async def _request(
        self,
        api_path: str,
        credentials: ShopCredentials | None = None,
        query: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """ยิง 1 request พร้อม sign + retry + แปลง error."""
        last_error: MarketplaceError | None = None

        for attempt in range(1, self._max_attempts + 1):
            params = build_common_params(
                partner_id=self._settings.partner_id,
                partner_key=self._partner_key,
                api_path=api_path,
                timestamp=current_timestamp_s(),
                access_token=credentials.access_token if credentials else None,
                shop_id=credentials.account_id if credentials else None,
            )
            if query:
                params.update(query)

            url = f"{self._settings.api_base_url}{api_path}"
            try:
                response = (
                    await self._http.post(url, params=params, json=dict(body))
                    if body is not None
                    else await self._http.get(url, params=params)
                )
                payload = self._parse(api_path, response)
            except (RateLimitError, MarketplaceUnavailableError) as error:
                last_error = error
                if attempt == self._max_attempts:
                    break
                await self._sleep(self._backoff * 2 ** (attempt - 1))
                continue

            logger.info("shopee call ok path=%s attempt=%s", api_path, attempt)
            return payload

        assert last_error is not None
        raise last_error

    def _parse(self, api_path: str, response: httpx.Response) -> dict[str, Any]:
        """ตรวจ response แล้วแปลง error เป็น exception ของเรา.

        Shopee ใช้ field ``error`` (string ว่าง = สำเร็จ) ต่างจาก Lazada ที่ใช้ ``code``
        """
        if response.status_code >= 500:
            raise MarketplaceUnavailableError(
                PLATFORM, str(response.status_code), f"upstream error at {api_path}"
            )

        try:
            payload: dict[str, Any] = response.json()
        except ValueError as exc:
            raise MarketplaceError(
                PLATFORM, "MalformedResponse", f"response ไม่ใช่ JSON ที่ {api_path}"
            ) from exc

        error = str(payload.get("error", ""))
        message = str(payload.get("message", ""))

        if response.status_code == 429 or error in RATE_LIMIT_CODES:
            raise RateLimitError(PLATFORM, error or "429", message or "rate limited")
        if error in TOKEN_ERROR_CODES:
            raise TokenExpiredError(PLATFORM, error, message or "token expired")
        if error != endpoints.SUCCESS_CODE:
            raise MarketplaceError(PLATFORM, error, message)

        return payload

    def _parse_token(self, payload: Mapping[str, Any]) -> TokenBundle:
        """แปลง response ของ token API เป็น TokenBundle.

        Raises:
            MarketplaceError: เมื่อ field ที่จำเป็นหายไป
        """
        now = datetime.now(UTC)
        try:
            expires_in = int(payload["expire_in"])
            return TokenBundle(
                access_token=str(payload["access_token"]),
                refresh_token=str(payload["refresh_token"]),
                expires_at=now + timedelta(seconds=expires_in),
                refresh_expires_at=now + FALLBACK_REFRESH_TTL,
                account_id=str(payload.get("shop_id", self._settings.default_shop_id)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise MarketplaceError(
                PLATFORM, "MalformedResponse", f"response ขาด field: {exc}"
            ) from exc

    def _normalize_order(
        self, raw: Mapping[str, Any], account_id: str
    ) -> NormalizedOrder:
        """แปลงออเดอร์ดิบของ Shopee เป็น NormalizedOrder."""
        try:
            created = raw.get("create_time")
            updated = raw.get("update_time")
            return NormalizedOrder(
                platform=Platform.SHOPEE,
                account_id=account_id,
                order_id=str(raw["order_sn"]),
                order_number=str(raw["order_sn"]),
                status=str(raw.get("order_status", "unknown")).lower(),
                total_amount=Decimal(str(raw.get("total_amount", "0"))),
                currency=str(raw.get("currency", "THB")),
                created_at=self._from_epoch(created),
                updated_at=self._from_epoch(updated),
            )
        except (KeyError, TypeError, InvalidOperation) as exc:
            raise MarketplaceError(
                PLATFORM, "MalformedOrder", f"แปลงออเดอร์ไม่สำเร็จ: {exc}"
            ) from exc

    @staticmethod
    def _from_epoch(value: Any) -> datetime | None:
        """Shopee ส่งเวลาเป็น unix timestamp — คืน None ถ้าอ่านไม่ออก."""
        if value in (None, "", 0):
            return None
        try:
            return datetime.fromtimestamp(int(value), tz=UTC)
        except (TypeError, ValueError, OSError):
            return None
