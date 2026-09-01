# Changelog

รูปแบบตาม [Keep a Changelog](https://keepachangelog.com/) และ [Semantic Versioning](https://semver.org/)

## [Unreleased]

### Added
- Bootstrap โครงสร้างโปรเจกต์ FastAPI ตาม STANDARDS.md (layered: api / services / repositories / marketplaces)
- `app/core/config.py` — settings ผ่าน pydantic-settings, `app_secret` เป็น `SecretStr`
- `app/core/logging.py` — `RedactSecretsFilter` ปิดบัง secret ใน log อัตโนมัติ
- `app/marketplaces/base.py` — `MarketplaceClient` protocol, `TokenBundle`, `ShopCredentials`
- `app/marketplaces/errors.py` — error hierarchy สำหรับ mapping error จากภายนอก
- `app/marketplaces/lazada/signer.py` — HMAC-SHA256 signing ของ Lazada พร้อม golden test
- `GET /api/v1/health` — liveness probe
- CI pipeline: ruff / black / mypy / pytest (coverage gate 80%)
- `app/core/security.py` — `TokenCipher` เข้ารหัส token ของร้านค้าด้วย Fernet ก่อนเก็บลง DB
- ORM models: `marketplace_shops`, `oauth_states`, `webhook_events` (SQLAlchemy 2.0 style + naming convention)
- Alembic migration แรก (`alembic init -t async` + autogenerate, ตรวจ diff แล้ว, downgrade ใช้งานได้จริง)
- Repository layer: `ShopRepository`, `OAuthStateRepository`, `WebhookEventRepository`
- `app/marketplaces/lazada/oauth.py` — authorize URL + parse token response (อายุ token มาจาก `expires_in` จริง)
- `app/marketplaces/lazada/client.py` — signed request, retry + backoff, error mapping, normalize order, verify webhook
- `app/marketplaces/registry.py` — platform → client factory (Shopee/TikTok ยังไม่ implement → 404)
- Services: `OAuthService` (state กัน CSRF ใช้ครั้งเดียว), `TokenService` (auto-refresh), `WebhookService` (idempotent)
- Endpoints: `GET /auth/{platform}/authorize`, `GET /auth/{platform}/callback`, `GET /shops`, `POST /webhooks/{platform}`
- DB test ใช้ Postgres จริงผ่าน testcontainers + rollback ทุก test ตาม PROJECT_RULES 5.2b

### Changed
- ใช้ `fastapi-cli` (`fastapi dev` / `fastapi run`) แทน `uvicorn` ตรง ๆ ตาม PROJECT_RULES 1.1

### Added (auth ของผู้ใช้ระบบ — PROJECT_RULES section 4)
- `app/core/oauth.py` — Authlib registry (Google OIDC + GitHub) พร้อม PKCE
- `app/core/security.py` — bcrypt password hashing + ออก/ตรวจ JWT ของแอปเอง
- Models `users` (hashed_password nullable) + `oauth_accounts` (unique provider+provider_user_id, FK CASCADE)
- `UserRepository`, `AuthService` (login idempotent, ปฏิเสธอีเมลที่ provider ไม่ยืนยัน, ปฏิเสธบัญชีปิด)
- Endpoints `GET /auth/{provider}/login`, `GET /auth/{provider}/callback`, `GET /auth/me`
- `SessionMiddleware` สำหรับให้ Authlib เก็บ state/nonce/PKCE (`https_only` ใน production)
- `get_current_user` dependency — `/shops` และ `/connections/*` ต้องมี JWT แล้ว
- Guard ตอน startup: production ต้องมี SECRET_KEY กับ JWT_SECRET_KEY คนละค่า และยาว >= 32 bytes

### Changed
- ย้าย endpoint ผูกร้าน marketplace จาก `/auth/{platform}/*` → `/connections/{platform}/*`
  เพราะ path ชนกับ social login
- `alembic/script.py.mako` ใช้ syntax ใหม่ (`str | None`) เพื่อให้ migration ที่ generate ผ่าน lint เอง
- ตั้ง `concurrency = ["thread", "greenlet"]` ใน coverage — SQLAlchemy async รันผ่าน greenlet
  ทำให้ coverage รายงานบรรทัดหลัง `await` ผิดว่าไม่ถูกรัน

### Added (รอบที่ 3)
- ตาราง `orders` + `OrderRepository` + `OrderSyncService` (upsert, refresh token แล้ว retry)
- `POST /shops/{id}/sync/orders`, `GET /shops/{id}/orders`
- Shopee client เต็มรูปแบบ (signer/oauth/orders/webhook) + golden test
- `app/workers/token_refresh.py` — worker ต่ออายุ token อัตโนมัติ
- `app/core/rate_limit.py` — sliding window limiter ที่ `/auth` และ `/webhooks`
- `deploy/` — Caddyfile snippet, systemd unit, checklist ก่อน/หลัง deploy
- `scripts/dev.py` — CLI ออก JWT และแลก OAuth code ด้วยมือระหว่าง dev

### Changed
- `MarketplaceClient` protocol ครบแล้ว (เพิ่ม `fetch_orders`, `verify_webhook`)
- Postgres ใน docker-compose ย้ายไป port 55432 (5432 บนเครื่อง dev ถูก cluster อื่นใช้)

### Added (อีเมล)
- `EmailSettings` (env prefix `SMTP_`) — password เป็น `SecretStr`
- `app/services/email_service.py` — ส่งอีเมลด้วย `aiosmtplib` (async ตามกฎ 2.4
  เพราะ `smtplib` มาตรฐานเป็น blocking) แปลง SMTP error เป็น `EmailSendError`
- เพิ่ม `password`/`smtp_password` เข้า redaction filter ของ logging
