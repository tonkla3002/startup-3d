"""FastAPI application entrypoint."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import httpx
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.router import api_router
from app.core.config import get_oauth_settings, get_security_settings, get_settings
from app.core.logging import configure_logging
from app.core.oauth import build_oauth
from app.core.security import TokenCipher
from app.db.session import AsyncSessionLocal
from app.workers.token_refresh import run_forever

API_V1_PREFIX = "/api/v1"

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """สร้าง resource ที่ใช้ร่วมกันทั้งแอป.

    * ``httpx.AsyncClient`` ตัวเดียวใช้ตลอด lifetime (STANDARDS 2.4)
    * Authlib registry ของ social login provider
    """
    settings = get_settings()
    configure_logging(settings.log_level)

    app.state.oauth = build_oauth(get_oauth_settings())
    async with httpx.AsyncClient(timeout=30.0) as client:
        app.state.http_client = client

        worker: asyncio.Task[None] | None = None
        if settings.token_refresh_worker_enabled:
            cipher = TokenCipher(settings.token_encryption_key.get_secret_value())
            worker = asyncio.create_task(run_forever(AsyncSessionLocal, client, cipher))
            logger.info("token refresh worker เริ่มทำงาน")

        try:
            yield
        finally:
            if worker is not None:
                worker.cancel()
                with suppress(asyncio.CancelledError):
                    await worker


def create_app() -> FastAPI:
    """ประกอบ FastAPI application.

    Returns:
        FastAPI instance ที่ติด middleware, router และ lifespan เรียบร้อย
    """
    settings = get_settings()
    security = get_security_settings()

    if settings.is_production:
        if not security.secrets_are_distinct:
            raise RuntimeError(
                "SECRET_KEY กับ JWT_SECRET_KEY ต้องคนละค่ากัน (PROJECT_RULES 4.4)"
            )
        if not security.secrets_are_strong:
            raise RuntimeError(
                "SECRET_KEY และ JWT_SECRET_KEY ต้องยาวอย่างน้อย 32 bytes (RFC 7518 3.2)"
            )

    application = FastAPI(
        title="Streamora",
        description=(
            "Backend integration layer connecting marketplace Open Platforms "
            "(Lazada, Shopee, TikTok Shop) with internal systems."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
    )

    # Authlib เก็บ state/nonce/PKCE ไว้ใน session ระหว่าง redirect (PROJECT_RULES 4.4)
    application.add_middleware(
        SessionMiddleware,
        secret_key=security.secret_key.get_secret_value() or "dev-only-session-secret",
        https_only=settings.is_production,
        same_site="lax",
    )

    application.include_router(api_router, prefix=API_V1_PREFIX)
    return application


app = create_app()
