"""Request signing ตามสเปกของ Shopee Open Platform v2.

ต่างจาก Lazada 3 จุดที่ทำให้พลาดบ่อย:

* **timestamp เป็น second** (Lazada เป็น millisecond)
* **signature เป็น hex ตัวพิมพ์เล็ก** (Lazada เป็นตัวพิมพ์ใหญ่)
* base string **ไม่ได้ sort key** แต่ต่อกันตามลำดับที่กำหนดตายตัว และต่างกัน
  ตามประเภท API (public / shop-level / merchant-level)

ทั้งหมดถูกล็อกด้วย golden test ใน ``tests/unit/marketplaces/shopee/test_signer.py``
"""

import hashlib
import hmac
import time


def current_timestamp_s() -> str:
    """คืน timestamp ปัจจุบันเป็น second ตามที่ Shopee ต้องการ."""
    return str(int(time.time()))


def build_base_string(
    partner_id: str,
    api_path: str,
    timestamp: str,
    access_token: str | None = None,
    shop_id: str | None = None,
) -> str:
    """ประกอบ base string ตามประเภทของ API.

    * public API: ``partner_id + path + timestamp``
    * shop-level API: ``partner_id + path + timestamp + access_token + shop_id``

    Args:
        partner_id: Partner ID จาก console
        api_path: path เช่น ``"/api/v2/order/get_order_list"``
        timestamp: timestamp หน่วย second
        access_token: token ของร้าน (เฉพาะ shop-level API)
        shop_id: shop id (เฉพาะ shop-level API)

    Returns:
        Base string ที่พร้อมนำไป HMAC
    """
    base = f"{partner_id}{api_path}{timestamp}"
    if access_token and shop_id:
        base += f"{access_token}{shop_id}"
    return base


def sign_request(
    partner_id: str,
    partner_key: str,
    api_path: str,
    timestamp: str,
    access_token: str | None = None,
    shop_id: str | None = None,
) -> str:
    """คำนวณ signature ตามสเปกของ Shopee.

    Returns:
        Signature เป็น hex string **ตัวพิมพ์เล็ก**

    Reference:
        https://open.shopee.com/documents?module=87&type=2&id=58
    """
    base = build_base_string(partner_id, api_path, timestamp, access_token, shop_id)
    return hmac.new(
        partner_key.encode("utf-8"), base.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def build_common_params(
    partner_id: str,
    partner_key: str,
    api_path: str,
    timestamp: str,
    access_token: str | None = None,
    shop_id: str | None = None,
) -> dict[str, str]:
    """ประกอบ query params ครบชุดพร้อม signature สำหรับ 1 request."""
    params: dict[str, str] = {
        "partner_id": partner_id,
        "timestamp": timestamp,
        "sign": sign_request(
            partner_id, partner_key, api_path, timestamp, access_token, shop_id
        ),
    }
    if access_token and shop_id:
        params["access_token"] = access_token
        params["shop_id"] = shop_id
    return params
