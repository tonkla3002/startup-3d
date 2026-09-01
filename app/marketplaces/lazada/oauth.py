"""OAuth flow ของ Lazada Open Platform.

Flow: redirect ผู้ขายไป authorize → Lazada เรียก callback พร้อม ``code``
→ แลก code เป็น token → เก็บ token → refresh ก่อนหมดอายุ
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from app.marketplaces.base import TokenBundle
from app.marketplaces.errors import MarketplaceError
from app.marketplaces.lazada.endpoints import SUCCESS_CODE

PLATFORM = "lazada"


def build_authorize_url(
    authorize_url: str, app_key: str, redirect_uri: str, state: str
) -> str:
    """สร้าง URL ให้ผู้ขายกดอนุญาตสิทธิ์.

    Args:
        authorize_url: base URL ของหน้า authorize
        app_key: App Key จาก console
        redirect_uri: callback URL ที่ลงทะเบียนไว้ใน console (ต้องตรงเป๊ะ)
        state: ค่าสุ่มกัน CSRF ที่จะตรวจตอน callback

    Returns:
        URL เต็มพร้อม query string
    """
    query = urlencode(
        {
            "response_type": "code",
            "force_auth": "true",
            "redirect_uri": redirect_uri,
            "client_id": app_key,
            "state": state,
        }
    )
    return f"{authorize_url}?{query}"


def _require(payload: dict[str, Any], key: str) -> Any:
    """ดึง field ที่ต้องมีจาก payload ไม่งั้น raise MarketplaceError.

    Raises:
        MarketplaceError: เมื่อ field หายไป — กันไม่ให้ KeyError หลุดขึ้น service
    """
    if key not in payload:
        raise MarketplaceError(
            PLATFORM, "MalformedResponse", f"response ขาด field '{key}'"
        )
    return payload[key]


def parse_token_response(
    payload: dict[str, Any], now: datetime | None = None
) -> TokenBundle:
    """แปลง response ของ token API เป็น TokenBundle.

    อายุ token คำนวณจาก ``expires_in`` / ``refresh_expires_in`` ที่ Lazada ตอบมาจริง
    **ห้าม hardcode** ตาม STANDARDS section 0.2

    Args:
        payload: body ที่ Lazada ตอบกลับมา (parse json แล้ว)
        now: เวลาอ้างอิง — ใส่เพื่อให้ test คุมค่าได้

    Returns:
        TokenBundle ที่คำนวณเวลาหมดอายุแล้ว

    Raises:
        MarketplaceError: เมื่อ ``code`` ไม่ใช่ "0" หรือ field ที่จำเป็นหายไป
    """
    code = str(payload.get("code", ""))
    if code != SUCCESS_CODE:
        raise MarketplaceError(
            PLATFORM, code or "UnknownError", str(payload.get("message", ""))
        )

    reference = now or datetime.now(UTC)
    return TokenBundle(
        access_token=_require(payload, "access_token"),
        refresh_token=_require(payload, "refresh_token"),
        expires_at=reference + timedelta(seconds=int(_require(payload, "expires_in"))),
        refresh_expires_at=reference
        + timedelta(seconds=int(_require(payload, "refresh_expires_in"))),
        account_id=str(_require(payload, "account_id")),
    )
