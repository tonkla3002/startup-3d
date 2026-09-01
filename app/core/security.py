"""เข้ารหัส/ถอดรหัส token ของร้านค้าก่อนเก็บลง DB.

ใช้ **การเข้ารหัสแบบถอดกลับได้** (Fernet) ไม่ใช่ hash เพราะต้องเอา token
กลับมายิง API จริง ตาม STANDARDS section 8.2 — key อยู่ใน env/secret manager
ไม่เก็บไว้ใน DB เดียวกับ ciphertext
"""

from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken

from app.core.exceptions import StreamoraError


class TokenCipherError(StreamoraError):
    """ถอดรหัส token ไม่สำเร็จ (key ผิด หรือ ciphertext เสีย)."""


def generate_key() -> str:
    """สร้าง Fernet key ใหม่สำหรับใส่ใน ``TOKEN_ENCRYPTION_KEY``.

    Returns:
        Key แบบ urlsafe base64 พร้อมใส่ลง .env
    """
    return Fernet.generate_key().decode()


class TokenCipher:
    """หุ้ม Fernet ไว้ให้ layer อื่นเรียกใช้โดยไม่ต้องรู้จัก cryptography."""

    def __init__(self, key: str) -> None:
        """สร้าง cipher จาก key.

        Args:
            key: Fernet key แบบ urlsafe base64

        Raises:
            TokenCipherError: เมื่อ key ผิดรูปแบบ
        """
        try:
            self._fernet = Fernet(key.encode())
        except (ValueError, TypeError) as exc:
            raise TokenCipherError("TOKEN_ENCRYPTION_KEY ไม่ถูกต้อง") from exc

    def encrypt(self, plaintext: str) -> str:
        """เข้ารหัส token ก่อนเก็บลง DB."""
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """ถอดรหัส token ที่อ่านมาจาก DB.

        Raises:
            TokenCipherError: เมื่อ ciphertext เสียหรือถูกเข้ารหัสด้วย key อื่น
        """
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise TokenCipherError("ถอดรหัส token ไม่สำเร็จ") from exc


# --------------------------------------------------------------------------- #
# Password hashing และ JWT ของแอปเอง (PROJECT_RULES section 4)
# --------------------------------------------------------------------------- #

import bcrypt  # noqa: E402
import jwt  # noqa: E402

from app.core.config import SecuritySettings  # noqa: E402

BCRYPT_MAX_BYTES = 72


class InvalidAccessTokenError(StreamoraError):
    """JWT ที่ส่งมาไม่ถูกต้องหรือหมดอายุ."""


def hash_password(plain: str) -> str:
    """Hash password ด้วย bcrypt — ห้ามเก็บ plain text ตาม PROJECT_RULES section 8.

    Args:
        plain: รหัสผ่านที่ผู้ใช้กรอก

    Returns:
        Hash พร้อมเก็บลง DB
    """
    payload = plain.encode("utf-8")[:BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(payload, bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """ตรวจว่ารหัสผ่านตรงกับ hash หรือไม่."""
    try:
        return bcrypt.checkpw(
            plain.encode("utf-8")[:BCRYPT_MAX_BYTES], hashed.encode("utf-8")
        )
    except ValueError:
        return False


def create_access_token(
    subject: str, settings: SecuritySettings, now: datetime | None = None
) -> str:
    """ออก JWT ของแอปเราเอง.

    เราไม่ส่ง access token ของ provider ให้ client ตรง ๆ ตาม PROJECT_RULES 4.1

    Args:
        subject: user id ในรูป string
        settings: secret + algorithm + อายุ token
        now: เวลาอ้างอิง — ใส่เพื่อให้ test คุมค่าได้

    Returns:
        JWT ที่เซ็นแล้ว
    """
    issued_at = now or datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str, settings: SecuritySettings) -> str:
    """ตรวจลายเซ็น + อายุของ JWT แล้วคืน subject.

    Args:
        token: JWT จาก header Authorization
        settings: secret + algorithm

    Returns:
        ``sub`` ของ token (user id)

    Raises:
        InvalidAccessTokenError: เมื่อ token ผิด หมดอายุ หรือไม่มี ``sub``
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise InvalidAccessTokenError("access token ไม่ถูกต้องหรือหมดอายุ") from exc

    subject = payload.get("sub")
    if not subject:
        raise InvalidAccessTokenError("access token ไม่มี subject")
    return str(subject)
