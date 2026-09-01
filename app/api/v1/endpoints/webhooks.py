"""รับ push event จาก marketplace.

หลักการตาม STANDARDS section 3.2:
* อ่าน **raw body** ก่อน parse JSON (signature คำนวณจาก raw bytes)
* verify signature ก่อนประมวลผลเสมอ ไม่ผ่าน = 401
* ตอบ 200 ให้เร็วที่สุด — ตอนนี้แค่บันทึก event ส่วนงานประมวลผลจริงจะย้ายไป
  background task/queue ใน milestone ถัดไป
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.core.rate_limit import webhook_rate_limit
from app.dependencies import Client, DbSession
from app.marketplaces.base import Platform
from app.schemas.webhook import WebhookAck
from app.services.webhook_service import WebhookService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"],
    dependencies=[Depends(webhook_rate_limit)],
)

# ⚠️ ต้องยืนยันชื่อ header กับ docs ทางการของแต่ละเจ้าก่อน go-live
SIGNATURE_HEADER = "x-lazada-signature"


def _extract_event(payload: dict[str, Any]) -> tuple[str, str]:
    """ดึง event id กับ event type ออกจาก payload.

    Raises:
        HTTPException: 422 เมื่อ payload ไม่มี field ที่จำเป็น
    """
    event_id = payload.get("message_id") or payload.get("event_id")
    event_type = payload.get("message_type") or payload.get("event_type")
    if not event_id or not event_type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="payload ขาด message_id หรือ message_type",
        )
    return str(event_id), str(event_type)


@router.post("/{platform}", response_model=WebhookAck)
async def receive_webhook(
    platform: Platform,
    request: Request,
    db: DbSession,
    client: Client,
    signature: str = Header(default="", alias=SIGNATURE_HEADER),
) -> WebhookAck:
    """รับ event จาก marketplace.

    Raises:
        HTTPException: 401 เมื่อ signature ไม่ถูกต้อง, 422 เมื่อ payload ผิดรูป
    """
    raw_body = await request.body()

    if not client.verify_webhook(raw_body, signature):
        logger.warning("webhook signature ไม่ถูกต้อง platform=%s", platform.value)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="signature ไม่ถูกต้อง"
        )

    try:
        payload: dict[str, Any] = await request.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="body ไม่ใช่ JSON"
        ) from exc

    event_id, event_type = _extract_event(payload)
    result = await WebhookService(db).ingest(platform, event_id, event_type, payload)
    return WebhookAck(received=True, duplicate=result.duplicate)
