"""HTTP client ของ Lazada Open Platform.

หน้าที่: แนบ common params + signature, ยิง request, แปลง error ภายนอกเป็น
exception ของเรา, retry ตามนโยบายใน STANDARDS section 2.6 และ normalize response

⚠️ Lazada ตอบ HTTP 200 แม้จะ error — ต้องเช็ค field ``code`` ใน body เสมอ
"""

import asyncio
import hashlib
import hmac
import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.core.config import LazadaSettings
from app.marketplaces.base import Platform, ShopCredentials, TokenBundle
from app.marketplaces.errors import (
    MarketplaceError,
    MarketplaceUnavailableError,
    RateLimitError,
    TokenExpiredError,
)
from app.marketplaces.lazada import endpoints
from app.marketplaces.lazada.oauth import (
    PLATFORM,
    build_authorize_url,
    parse_token_response,
)
from app.marketplaces.lazada.signer import build_signed_params, current_timestamp_ms
from app.marketplaces.schemas import NormalizedOrder

logger = logging.getLogger(__name__)

RATE_LIMIT_CODES = frozenset(
    {"ApiCallLimit", "Api.Throttled", "ApiInvokeLimit", "TooManyRequests"}
)
TOKEN_ERROR_CODES = frozenset(
    {
        "IllegalAccessToken",
        "InvalidAccessToken",
        "AccessTokenExpired",
        "MissingAccessToken",
        "InvalidToken",
    }
)

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = 0.5


class LazadaClient:
    """Client สำหรับเรียก Lazada Open Platform API.

    Client ตัวนี้ **ไม่แตะ DB** — token ถูกส่งเข้ามาทาง ``ShopCredentials`` เสมอ
    """

    platform = Platform.LAZADA

    def __init__(
        self,
        http: httpx.AsyncClient,
        settings: LazadaSettings,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        """สร้าง client.

        Args:
            http: AsyncClient ที่ inject เข้ามา (ใช้ตัวเดียวทั้งแอป)
            settings: credential + base URL ของ Lazada
            max_attempts: จำนวนครั้งสูงสุดที่ยอมยิงซ้ำเมื่อเจอ error ที่ retry ได้
            backoff_seconds: ระยะหน่วงตั้งต้นของ exponential backoff
            sleep: ฟังก์ชันหน่วงเวลา — inject ใน test เพื่อไม่ให้ test ช้า
        """
        self._http = http
        self._settings = settings
        self._max_attempts = max_attempts
        self._backoff = backoff_seconds
        self._sleep = sleep or asyncio.sleep

    @property
    def _app_secret(self) -> str:
        return self._settings.app_secret.get_secret_value()

    def build_authorize_url(self, state: str) -> str:
        """สร้าง URL ให้ผู้ขายกดอนุญาตสิทธิ์."""
        return build_authorize_url(
            authorize_url=self._settings.authorize_url,
            app_key=self._settings.app_key,
            redirect_uri=self._settings.redirect_uri,
            state=state,
        )

    async def exchange_code(self, code: str) -> TokenBundle:
        """แลก authorization code เป็น token."""
        payload = await self._request(
            api_path=endpoints.TOKEN_CREATE,
            base_url=self._settings.auth_base_url,
            extra={"code": code},
        )
        return parse_token_response(payload)

    async def refresh_token(self, refresh_token: str) -> TokenBundle:
        """ต่ออายุ access token."""
        payload = await self._request(
            api_path=endpoints.TOKEN_REFRESH,
            base_url=self._settings.auth_base_url,
            extra={"refresh_token": refresh_token},
        )
        return parse_token_response(payload)

    async def fetch_orders(
        self, credentials: ShopCredentials, since: datetime, limit: int = 100
    ) -> list[NormalizedOrder]:
        """ดึงออเดอร์ที่สร้างหลังเวลาที่กำหนด.

        Args:
            credentials: token ของร้าน (service เป็นคนอ่านจาก DB มาให้)
            since: ดึงเฉพาะออเดอร์ที่สร้างหลังเวลานี้
            limit: จำนวนสูงสุดต่อหน้า

        Returns:
            รายการออเดอร์ที่ normalize แล้ว
        """
        payload = await self._request(
            api_path=endpoints.ORDERS_GET,
            base_url=self._settings.api_base_url,
            access_token=credentials.access_token,
            extra={"created_after": since.isoformat(), "limit": str(limit)},
        )
        raw_orders = payload.get("data", {}).get("orders", [])
        return [
            self._normalize_order(order, credentials.account_id) for order in raw_orders
        ]

    def verify_webhook(self, raw_body: bytes, signature: str) -> bool:
        """ตรวจ signature ของ push message จาก Lazada.

        คำนวณ HMAC-SHA256 ของ **raw body** ด้วย app_secret แล้วเทียบด้วย
        ``hmac.compare_digest`` เพื่อกัน timing attack

        ⚠️ ชื่อ header ที่ Lazada ใช้ส่ง signature มา ต้องยืนยันกับ docs ทางการ
        ก่อน go-live — ดู ``app/api/v1/endpoints/webhooks.py``

        Args:
            raw_body: body ดิบก่อน parse JSON
            signature: ค่า signature ที่ได้จาก header

        Returns:
            True เมื่อ signature ถูกต้อง
        """
        expected = hmac.new(
            self._app_secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected.upper(), signature.strip().upper())

    async def _request(
        self,
        api_path: str,
        base_url: str,
        access_token: str | None = None,
        extra: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """ยิง 1 request พร้อม sign + retry + แปลง error.

        Raises:
            RateLimitError: โดน rate limit จนครบจำนวน retry
            TokenExpiredError: token หมดอายุ
            MarketplaceUnavailableError: 5xx / timeout
            MarketplaceError: business error อื่น ๆ
        """
        last_error: MarketplaceError | None = None

        for attempt in range(1, self._max_attempts + 1):
            params = build_signed_params(
                api_path=api_path,
                app_key=self._settings.app_key,
                app_secret=self._app_secret,
                timestamp=current_timestamp_ms(),
                access_token=access_token,
                extra=extra,
            )
            try:
                response = await self._http.get(f"{base_url}{api_path}", params=params)
                payload = self._parse(api_path, response)
            except (RateLimitError, MarketplaceUnavailableError) as error:
                last_error = error
                if attempt == self._max_attempts:
                    break
                await self._sleep(self._backoff * 2 ** (attempt - 1))
                continue

            logger.info(
                "lazada call ok path=%s attempt=%s status=%s",
                api_path,
                attempt,
                response.status_code,
            )
            return payload

        assert last_error is not None
        raise last_error

    def _parse(self, api_path: str, response: httpx.Response) -> dict[str, Any]:
        """ตรวจ response แล้วแปลง error เป็น exception ของเรา."""
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

        code = str(payload.get("code", ""))
        message = str(payload.get("message", ""))

        if response.status_code == 429 or code in RATE_LIMIT_CODES:
            raise RateLimitError(PLATFORM, code or "429", message or "rate limited")
        if code in TOKEN_ERROR_CODES:
            raise TokenExpiredError(PLATFORM, code, message or "token expired")
        if code != endpoints.SUCCESS_CODE:
            raise MarketplaceError(PLATFORM, code or "UnknownError", message)

        return payload

    def _normalize_order(
        self, raw: Mapping[str, Any], account_id: str
    ) -> NormalizedOrder:
        """แปลงออเดอร์ดิบของ Lazada เป็น NormalizedOrder.

        Raises:
            MarketplaceError: เมื่อ field ที่จำเป็นหายไปหรือรูปแบบผิด
        """
        try:
            statuses = raw.get("statuses") or []
            return NormalizedOrder(
                platform=Platform.LAZADA,
                account_id=account_id,
                order_id=str(raw["order_id"]),
                order_number=(
                    str(raw["order_number"]) if raw.get("order_number") else None
                ),
                status=str(statuses[0]) if statuses else "unknown",
                total_amount=Decimal(str(raw.get("price", "0"))),
                currency=str(raw.get("currency", "THB")),
                created_at=self._parse_datetime(raw.get("created_at")),
                updated_at=self._parse_datetime(raw.get("updated_at")),
            )
        except (KeyError, TypeError, InvalidOperation) as exc:
            raise MarketplaceError(
                PLATFORM, "MalformedOrder", f"แปลงออเดอร์ไม่สำเร็จ: {exc}"
            ) from exc

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """แปลงเวลาจาก Lazada — คืน None ถ้าอ่านไม่ออก แทนที่จะพังทั้งออเดอร์."""
        if not value:
            return None
        text = str(value).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(text, fmt)
            except ValueError:
                continue
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
