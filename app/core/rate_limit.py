"""Rate limiting สำหรับ endpoint ที่อ่อนไหว (PROJECT_RULES section 8).

เป็น in-memory sliding window — พอสำหรับ instance เดียว **ถ้าจะ scale หลาย
instance ต้องย้ายไป Redis** เพราะ counter ของแต่ละ process จะแยกกัน
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class SlidingWindowLimiter:
    """นับจำนวน request ต่อ key ในหน้าต่างเวลาที่กำหนด."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        """สร้าง limiter.

        Args:
            max_requests: จำนวน request สูงสุดในหนึ่งหน้าต่างเวลา
            window_seconds: ความยาวหน้าต่างเวลา (วินาที)
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, now: float | None = None) -> bool:
        """บันทึก 1 hit แล้วบอกว่ายังอยู่ในโควตาไหม.

        Returns:
            True เมื่อยังไม่เกินโควตา
        """
        moment = now if now is not None else time.monotonic()
        hits = self._hits[key]
        while hits and moment - hits[0] >= self.window_seconds:
            hits.popleft()

        if len(hits) >= self.max_requests:
            return False
        hits.append(moment)
        return True

    def reset(self) -> None:
        """ล้างสถิติทั้งหมด (ใช้ใน test)."""
        self._hits.clear()


class RateLimit:
    """FastAPI dependency ที่ปฏิเสธ request เมื่อยิงถี่เกินไป."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.limiter = SlidingWindowLimiter(max_requests, window_seconds)

    async def __call__(self, request: Request) -> None:
        """ตรวจโควตาตาม client IP.

        Raises:
            HTTPException: 429 เมื่อยิงเกินโควตา
        """
        client = request.client.host if request.client else "unknown"
        key = f"{client}:{request.url.path}"
        if not self.limiter.check(key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="ยิงถี่เกินไป ลองใหม่อีกครั้งภายหลัง",
                headers={"Retry-After": str(int(self.limiter.window_seconds))},
            )


login_rate_limit = RateLimit(max_requests=10, window_seconds=60)
webhook_rate_limit = RateLimit(max_requests=600, window_seconds=60)
