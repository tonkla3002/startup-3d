"""Exception ของ marketplace layer — ทุก error จากภายนอกต้องถูกแปลงมาเป็นตัวใดตัวหนึ่งนี้.

ตาราง mapping อยู่ใน STANDARDS section 2.6
"""

from app.core.exceptions import StreamoraError


class MarketplaceError(StreamoraError):
    """Business error จาก marketplace — ห้าม retry.

    Attributes:
        platform: ชื่อ platform เช่น "lazada"
        code: error code ที่ marketplace ตอบมา
        message: ข้อความอธิบาย error
    """

    def __init__(self, platform: str, code: str, message: str) -> None:
        self.platform = platform
        self.code = code
        self.message = message
        super().__init__(f"[{platform}] {code}: {message}")


class RateLimitError(MarketplaceError):
    """โดน rate limit — retry ได้ด้วย exponential backoff."""


class TokenExpiredError(MarketplaceError):
    """Access token หมดอายุ — ต้อง refresh แล้ว retry คำขอเดิม 1 ครั้ง."""


class MarketplaceUnavailableError(MarketplaceError):
    """5xx / timeout / connect error — retry ได้."""
