"""ผูกร้านค้าบน marketplace เข้าระบบ (ต้องล็อกอินก่อน).

path ใช้ ``/connections`` ไม่ใช่ ``/auth`` เพราะ ``/auth`` สงวนไว้ให้
social login ของผู้ใช้ระบบ (PROJECT_RULES section 4)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.dependencies import Cipher, Client, DbSession, get_current_user
from app.marketplaces.base import Platform
from app.marketplaces.errors import MarketplaceError
from app.services.oauth_service import InvalidOAuthStateError, OAuthService

router = APIRouter(
    prefix="/connections",
    tags=["connections"],
    dependencies=[Depends(get_current_user)],  # ทุก endpoint ต้องล็อกอินก่อน
)


@router.get("/{platform}/authorize", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
async def authorize(
    platform: Platform,
    db: DbSession,
    client: Client,
    cipher: Cipher,
) -> RedirectResponse:
    """เริ่ม OAuth flow — redirect ผู้ขายไปหน้าอนุญาตสิทธิ์ของ marketplace."""
    service = OAuthService(db=db, client=client, cipher=cipher)
    url = await service.start_authorization(platform)
    return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/{platform}/callback", status_code=status.HTTP_200_OK)
async def callback(
    platform: Platform,
    db: DbSession,
    client: Client,
    cipher: Cipher,
    code: str = Query(..., min_length=1),
    state: str = Query(..., min_length=1),
) -> dict[str, str]:
    """รับ code จาก marketplace แล้วแลกเป็น token.

    Raises:
        HTTPException: 400 เมื่อ state ไม่ถูกต้อง, 502 เมื่อ marketplace ตอบ error
    """
    service = OAuthService(db=db, client=client, cipher=cipher)
    try:
        shop = await service.complete_authorization(platform, code=code, state=state)
    except InvalidOAuthStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except MarketplaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message
        ) from exc

    return {"status": "authorized", "account_id": shop.account_id}
