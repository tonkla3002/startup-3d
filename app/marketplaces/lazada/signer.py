"""Request signing ตามสเปกของ Lazada Open Platform.

จุดที่พลาดบ่อยและทำให้ได้ error "Invalid signature" เหมือนกันหมด:

* **timestamp ของ Lazada เป็น millisecond** (ของ Shopee เป็น second)
* **signature เป็น hex ตัวพิมพ์ใหญ่** (ของ Shopee เป็นตัวพิมพ์เล็ก)
* key ต้องถูก sort ก่อน concat และต้องตัด key ``sign`` ออกก่อนคำนวณเสมอ

ทั้งหมดนี้ถูกล็อกไว้ด้วย golden test ใน ``tests/unit/marketplaces/lazada/test_signer.py``
"""

import hashlib
import hmac
import time
from collections.abc import Mapping

from app.marketplaces.lazada.endpoints import SIGN_METHOD

SIGN_KEY = "sign"


def current_timestamp_ms() -> str:
    """คืน timestamp ปัจจุบันเป็น millisecond ในรูป string ตามที่ Lazada ต้องการ.

    Returns:
        Unix timestamp หน่วย millisecond เช่น ``"1755000000000"``
    """
    return str(int(time.time() * 1000))


def build_base_string(api_path: str, params: Mapping[str, str]) -> str:
    """ประกอบ base string ที่จะนำไปเข้ารหัส.

    สูตร: ``api_path + "".join(key + value for key, value in sorted(params))``
    โดยตัด key ``sign`` ออก (เผื่อมีค่าเก่าค้างอยู่ใน dict)

    Args:
        api_path: path ของ API เช่น ``"/orders/get"`` (ไม่รวม host)
        params: query/body params ทั้งหมด

    Returns:
        Base string ที่พร้อมนำไป HMAC
    """
    return api_path + "".join(
        f"{key}{value}" for key, value in sorted(params.items()) if key != SIGN_KEY
    )


def sign_request(api_path: str, params: Mapping[str, str], app_secret: str) -> str:
    """คำนวณ signature ตามสเปกของ Lazada Open Platform.

    Args:
        api_path: path ของ API เช่น ``"/orders/get"`` (ไม่รวม host)
        params: query/body params ทั้งหมด — key ``sign`` จะถูกตัดออกให้อัตโนมัติ
        app_secret: secret ของแอปจาก Open Platform console

    Returns:
        Signature เป็น hex string ตัวพิมพ์ใหญ่

    Reference:
        https://open.lazada.com/apps/doc/doc?nodeId=10450&docId=108069
    """
    payload = build_base_string(api_path, params)
    digest = hmac.new(
        app_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    )
    return digest.hexdigest().upper()


def build_signed_params(
    api_path: str,
    app_key: str,
    app_secret: str,
    timestamp: str,
    access_token: str | None = None,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """ประกอบ common params ครบชุดพร้อม signature สำหรับยิง 1 request.

    Args:
        api_path: path ของ API เช่น ``"/orders/get"``
        app_key: App Key จาก Open Platform console
        app_secret: App Secret จาก Open Platform console
        timestamp: timestamp หน่วย millisecond (ส่งเข้ามาเพื่อให้ test คุมค่าได้)
        access_token: token ของร้าน — เว้นว้างสำหรับ API ที่ไม่ต้อง authorize
        extra: params เฉพาะของ endpoint นั้น ๆ

    Returns:
        dict ที่พร้อมส่งเป็น query/body รวม key ``sign`` แล้ว
    """
    params: dict[str, str] = {
        "app_key": app_key,
        "timestamp": timestamp,
        "sign_method": SIGN_METHOD,
    }
    if access_token:
        params["access_token"] = access_token
    if extra:
        params.update(extra)

    params[SIGN_KEY] = sign_request(api_path, params, app_secret)
    return params
