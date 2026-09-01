"""Schema ของการ login."""

from pydantic import BaseModel, ConfigDict, EmailStr


class TokenOut(BaseModel):
    """JWT ที่ออกให้ client หลัง login สำเร็จ."""

    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    """ข้อมูลผู้ใช้ — ไม่มี hashed_password อยู่ใน response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None = None
    is_active: bool
