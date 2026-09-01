"""Application settings อ่านจาก environment / .env ผ่าน pydantic-settings."""

from enum import StrEnum
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    """Environment ที่แอปกำลังรันอยู่."""

    LOCAL = "local"
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class LazadaSettings(BaseSettings):
    """Credential และ endpoint ของ Lazada Open Platform.

    ค่า base URL แยกตาม environment ผ่าน env var เพื่อให้สลับ sandbox <-> production
    ได้โดยไม่ต้องแก้โค้ด ตามข้อกำหนดใน STANDARDS section 2.7
    """

    model_config = SettingsConfigDict(
        env_prefix="LAZADA_", env_file=".env", extra="ignore"
    )

    app_key: str = ""
    app_secret: SecretStr = SecretStr("")
    api_base_url: str = "https://api.lazada.co.th/rest"
    auth_base_url: str = "https://auth.lazada.com/rest"
    authorize_url: str = "https://auth.lazada.com/oauth/authorize"
    redirect_uri: str = ""
    country: str = "TH"

    @property
    def is_configured(self) -> bool:
        """True เมื่อมี credential ครบพอที่จะเรียก API ได้จริง."""
        return bool(self.app_key and self.app_secret.get_secret_value())


class Settings(BaseSettings):
    """Setting ระดับแอป."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: AppEnv = AppEnv.LOCAL
    app_name: str = "streamora"
    log_level: str = "INFO"
    database_url: str = ""
    token_encryption_key: SecretStr = SecretStr("")

    @property
    def is_production(self) -> bool:
        """True เมื่อรันบน production."""
        return self.app_env is AppEnv.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    """คืน Settings แบบ cache ไว้ ใช้เป็น FastAPI dependency ได้."""
    return Settings()


@lru_cache
def get_lazada_settings() -> LazadaSettings:
    """คืน LazadaSettings แบบ cache ไว้ ใช้เป็น FastAPI dependency ได้."""
    return LazadaSettings()


MIN_SECRET_BYTES = 32


class ShopeeSettings(BaseSettings):
    """Credential และ endpoint ของ Shopee Open Platform."""

    model_config = SettingsConfigDict(
        env_prefix="SHOPEE_", env_file=".env", extra="ignore"
    )

    partner_id: str = ""
    partner_key: SecretStr = SecretStr("")
    api_base_url: str = "https://partner.test-stable.shopeemobile.com"
    redirect_uri: str = ""
    webhook_url: str = ""
    default_shop_id: str = ""

    @property
    def is_configured(self) -> bool:
        """True เมื่อมี credential ครบพอที่จะเรียก API ได้จริง."""
        return bool(self.partner_id and self.partner_key.get_secret_value())


class SecuritySettings(BaseSettings):
    """Secret สำหรับ session และ JWT.

    ``secret_key`` (session) กับ ``jwt_secret_key`` (ออก token) **ต้องคนละตัวกัน**
    ตาม PROJECT_RULES section 4.4
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    secret_key: SecretStr = SecretStr("")
    jwt_secret_key: SecretStr = SecretStr("")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    @property
    def secrets_are_distinct(self) -> bool:
        """True เมื่อ session secret กับ JWT secret ไม่ใช่ค่าเดียวกัน."""
        return (
            self.secret_key.get_secret_value() != self.jwt_secret_key.get_secret_value()
        )

    @property
    def secrets_are_strong(self) -> bool:
        """True เมื่อ secret ทั้งสองยาวพอสำหรับ HMAC-SHA256 (RFC 7518 3.2)."""
        return all(
            len(secret.get_secret_value().encode("utf-8")) >= MIN_SECRET_BYTES
            for secret in (self.secret_key, self.jwt_secret_key)
        )


class OAuthProviderSettings(BaseSettings):
    """Credential ของ identity provider สำหรับ login เข้าระบบเรา."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    github_client_id: str = ""
    github_client_secret: SecretStr = SecretStr("")
    oauth_redirect_base_url: str = ""

    def is_enabled(self, provider: str) -> bool:
        """True เมื่อ provider นั้นตั้ง credential ครบแล้ว."""
        client_id = getattr(self, f"{provider}_client_id", "")
        secret = getattr(self, f"{provider}_client_secret", None)
        return bool(client_id and secret and secret.get_secret_value())


@lru_cache
def get_shopee_settings() -> ShopeeSettings:
    """คืน ShopeeSettings แบบ cache ไว้."""
    return ShopeeSettings()


@lru_cache
def get_security_settings() -> SecuritySettings:
    """คืน SecuritySettings แบบ cache ไว้."""
    return SecuritySettings()


@lru_cache
def get_oauth_settings() -> OAuthProviderSettings:
    """คืน OAuthProviderSettings แบบ cache ไว้."""
    return OAuthProviderSettings()
