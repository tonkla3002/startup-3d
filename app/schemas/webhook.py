"""Schema ของ webhook."""

from pydantic import BaseModel


class WebhookAck(BaseModel):
    """Response ที่ตอบกลับ marketplace ทันทีหลังรับ event."""

    received: bool
    duplicate: bool
