"""Social login เข้าระบบ Streamora (คนละเรื่องกับการผูกร้าน marketplace)."""

import logging
from typing import Any

from authlib.integrations.base_client import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from starlette.responses import RedirectResponse

from app.core.oauth import GITHUB, GOOGLE, SUPPORTED_PROVIDERS
from app.core.rate_limit import login_rate_limit
from app.dependencies import CurrentUser, DbSession, OAuthRegistry, Security
from app.schemas.auth import TokenOut, UserOut
from app.services.auth_service import (
    AuthService,
    InactiveUserError,
    UnverifiedEmailError,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    dependencies=[Depends(login_rate_limit)],  # PROJECT_RULES section 8
)


def _get_client(oauth: OAuthRegistry, provider: str) -> Any:
    """ดึง Authlib client ของ provider.

    Raises:
        HTTPException: 404 เมื่อ provider ไม่รองรับหรือยังไม่ได้ตั้ง credential
    """
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ไม่รองรับ provider: {provider}",
        )
    client = oauth.create_client(provider)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"ยังไม่ได้ตั้งค่า credential ของ {provider}",
        )
    return client


async def _extract_profile(
    client: Any, provider: str, token: dict[str, Any]
) -> dict[str, Any]:
    """ดึง profile จาก provider ให้อยู่ในรูปเดียวกัน.

    GitHub ไม่ใช่ OIDC จึงต้องเรียก API แยกและอ่าน ``email`` กับสถานะยืนยันเอง
    """
    if provider == GOOGLE:
        info = token.get("userinfo") or await client.userinfo(token=token)
        return {
            "provider_user_id": str(info["sub"]),
            "email": info.get("email"),
            "email_verified": bool(info.get("email_verified")),
            "full_name": info.get("name"),
        }

    response = await client.get("user", token=token)
    info = response.json()
    emails_response = await client.get("user/emails", token=token)
    emails = emails_response.json() if emails_response.status_code == 200 else []
    primary = next(
        (item for item in emails if item.get("primary") and item.get("verified")), None
    )
    return {
        "provider_user_id": str(info["id"]),
        "email": primary["email"] if primary else None,
        "email_verified": primary is not None,
        "full_name": info.get("name"),
    }


@router.get("/{provider}/login")
async def oauth_login(
    provider: str, request: Request, oauth: OAuthRegistry
) -> RedirectResponse:
    """เริ่ม social login — redirect ไปหน้า consent ของ provider."""
    client = _get_client(oauth, provider)
    redirect_uri = str(request.url_for("oauth_callback", provider=provider))
    result: RedirectResponse = await client.authorize_redirect(request, redirect_uri)
    return result


@router.get("/{provider}/callback", name="oauth_callback", response_model=TokenOut)
async def oauth_callback(
    provider: str,
    request: Request,
    db: DbSession,
    oauth: OAuthRegistry,
    security: Security,
) -> TokenOut:
    """รับ callback จาก provider แล้วออก JWT ของแอปเรา.

    ``authorize_access_token`` ตรวจ ``state``/PKCE และ validate ``id_token``
    (signature + aud/iss/exp) ให้อัตโนมัติ — ห้าม bypass

    Raises:
        HTTPException: 400 เมื่อ provider ตอบ error, 403 เมื่ออีเมลไม่ยืนยัน/บัญชีถูกปิด
    """
    client = _get_client(oauth, provider)
    try:
        token = await client.authorize_access_token(request)
    except OAuthError as exc:
        logger.warning("oauth callback ล้มเหลว provider=%s", provider)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc.description or exc)
        ) from exc

    profile = await _extract_profile(client, provider, token)
    service = AuthService(db=db, settings=security)
    try:
        user = await service.login_or_create_user(provider=provider, **profile)
    except UnverifiedEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc

    return TokenOut(access_token=service.issue_access_token(user))


@router.get("/me", response_model=UserOut)
async def read_me(user: CurrentUser) -> UserOut:
    """คืนข้อมูลผู้ใช้ที่ล็อกอินอยู่."""
    return UserOut.model_validate(user)


__all__ = ["GITHUB", "GOOGLE", "router"]
