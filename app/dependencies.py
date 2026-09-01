"""FastAPI dependency ที่ใช้ร่วมกันหลายที่."""

from collections.abc import AsyncIterator, Callable
from typing import Annotated

import httpx
from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import (
    OAuthProviderSettings,
    SecuritySettings,
    Settings,
    get_oauth_settings,
    get_security_settings,
    get_settings,
)
from app.core.oauth import build_oauth
from app.core.security import (
    InvalidAccessTokenError,
    TokenCipher,
    decode_access_token,
)
from app.db.session import get_db
from app.marketplaces.base import MarketplaceClient, Platform
from app.marketplaces.registry import build_client, is_configured
from app.models.user import User
from app.repositories.user_repository import UserRepository

DbSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
Security = Annotated[SecuritySettings, Depends(get_security_settings)]
OAuthSettings = Annotated[OAuthProviderSettings, Depends(get_oauth_settings)]

bearer_scheme = HTTPBearer(auto_error=False)


async def get_http_client(request: Request) -> AsyncIterator[httpx.AsyncClient]:
    """คืน httpx client ตัวเดียวที่สร้างไว้ตอน lifespan."""
    yield request.app.state.http_client


def get_token_cipher(settings: AppSettings) -> TokenCipher:
    """สร้าง TokenCipher จาก key ใน settings."""
    return TokenCipher(settings.token_encryption_key.get_secret_value())


def get_oauth_registry(request: Request) -> OAuth:
    """คืน Authlib registry ที่สร้างไว้ตอน lifespan."""
    registry: OAuth = request.app.state.oauth
    return registry


def _build_or_fail(platform: Platform, http: httpx.AsyncClient) -> MarketplaceClient:
    """สร้าง client พร้อมตรวจว่า platform นั้นพร้อมใช้งานจริง.

    Raises:
        HTTPException: 404 เมื่อยังไม่ implement, 503 เมื่อยังไม่ได้ตั้ง credential
    """
    try:
        client = build_client(platform, http)
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    if not is_configured(platform):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"ยังไม่ได้ตั้งค่า credential ของ {platform.value}",
        )
    return client


def get_marketplace_client(
    platform: Platform,
    http: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> MarketplaceClient:
    """สร้าง client ตาม platform ที่อยู่ใน path."""
    return _build_or_fail(platform, http)


async def get_current_user(
    db: DbSession,
    security: Security,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
) -> User:
    """ตรวจ JWT แล้วคืน user ที่ล็อกอินอยู่.

    Raises:
        HTTPException: 401 เมื่อไม่มี token / token ผิด / user ถูกปิดใช้งาน
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="ต้องล็อกอินก่อน",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    try:
        subject = decode_access_token(credentials.credentials, security)
    except InvalidAccessTokenError as exc:
        raise unauthorized from exc

    user = await UserRepository(db).get(int(subject))
    if user is None or not user.is_active:
        raise unauthorized
    return user


def get_client_factory(
    http: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> Callable[[Platform], MarketplaceClient]:
    """คืนฟังก์ชันสร้าง client ตาม platform.

    ใช้กับ endpoint ที่ไม่มี ``platform`` ใน path (เช่น sync ออเดอร์ของร้าน)
    ซึ่งต้องอ่าน platform จากตัวร้านแทน
    """

    def _factory(platform: Platform) -> MarketplaceClient:
        return _build_or_fail(platform, http)

    return _factory


HttpClient = Annotated[httpx.AsyncClient, Depends(get_http_client)]
Cipher = Annotated[TokenCipher, Depends(get_token_cipher)]
Client = Annotated[MarketplaceClient, Depends(get_marketplace_client)]
ClientFactory = Annotated[
    Callable[[Platform], MarketplaceClient], Depends(get_client_factory)
]
OAuthRegistry = Annotated[OAuth, Depends(get_oauth_registry)]
CurrentUser = Annotated[User, Depends(get_current_user)]

__all__ = [
    "AppSettings",
    "Cipher",
    "Client",
    "ClientFactory",
    "CurrentUser",
    "DbSession",
    "HttpClient",
    "OAuthRegistry",
    "OAuthSettings",
    "Security",
    "build_oauth",
    "get_client_factory",
    "get_current_user",
    "get_marketplace_client",
    "get_oauth_registry",
    "get_token_cipher",
]
