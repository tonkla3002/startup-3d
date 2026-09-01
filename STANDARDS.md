# Streamora — FastAPI Project Standards & Rules

> **โปรเจกต์:** Streamora — backend integration layer เชื่อม marketplace Open Platform
> (Lazada → Shopee → TikTok Shop) เข้ากับระบบภายใน
> **อ่านไฟล์นี้ก่อนเริ่มงานทุกครั้ง** — ทั้งตอนขึ้นโปรเจกต์ใหม่ และก่อนเขียน/แก้โค้ดทุกครั้ง

---

## 0. Checklist ก่อนเริ่มโค้ด (ต้องอ่านทุกครั้ง)

### 0.1 ทั่วไป
- [ ] อ่าน section "Coding Standard" ให้ครบก่อนเขียนโค้ด
- [ ] ทุกฟังก์ชัน/เมธอดใหม่ **ต้องมี type hint ครบ** (parameter + return)
- [ ] ทุกฟังก์ชัน/เมธอดใหม่ **ต้องมี pytest test case คู่กันเสมอ** ห้าม merge โค้ดที่ไม่มี test
- [ ] รัน `ruff check .` และ `black --check .` ก่อน commit
- [ ] รัน `pytest --cov` แล้ว coverage ต้องไม่ต่ำกว่า threshold ที่กำหนด (ดู section 4.4)
- [ ] เช็คว่า endpoint ใหม่มี Pydantic schema (request/response) ครบ ไม่ใช้ `dict` ลอย ๆ
- [ ] ไม่ commit secret / API key / `.env` ลง git
- [ ] เขียน docstring อธิบาย business logic ที่ซับซ้อน
- [ ] อัปเดต `CHANGELOG.md` ถ้ามีการเปลี่ยนแปลงที่กระทบ public API

### 0.2 เพิ่มเติมสำหรับงานที่แตะ Marketplace API (บังคับ)
- [ ] **ห้ามยิง API จริงของ Lazada/Shopee/TikTok ใน test** — mock ด้วย `respx` เสมอ
- [ ] ฟังก์ชัน signing ทุกตัวต้องมี **golden test** (timestamp คงที่ + secret ปลอม → sign ที่รู้ค่าแน่นอน)
- [ ] `app_secret` / `access_token` / `refresh_token` **ห้ามโผล่ใน log** ทุกระดับ (ดู section 8.3)
- [ ] ค่า `expires_in` ต้องอ่านจาก response จริง **ห้าม hardcode อายุ token** ในโค้ด
- [ ] endpoint ที่รับ webhook ต้อง verify signature ก่อนประมวลผลเสมอ และต้อง **idempotent**
- [ ] เพิ่ม platform ใหม่ = implement `MarketplaceClient` protocol ให้ครบ ห้ามแทรก `if platform == "lazada"` ใน service layer

---

## 1. โครงสร้างโปรเจกต์ (Project Structure)

```
streamora/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app entrypoint
│   ├── core/
│   │   ├── config.py                # Settings (pydantic-settings)
│   │   ├── security.py              # auth / jwt / hashing / token encryption
│   │   ├── logging.py               # logging config + secret redaction filter
│   │   └── exceptions.py            # custom exception ของแอป
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py            # รวม router ทั้งหมด
│   │       └── endpoints/
│   │           ├── health.py
│   │           ├── auth.py          # /auth/{platform}/authorize, /auth/{platform}/callback
│   │           ├── webhooks.py      # /webhooks/{platform}
│   │           ├── shops.py         # จัดการร้านที่ authorize แล้ว
│   │           └── sync.py          # trigger sync order/product
│   ├── marketplaces/                # ⭐ outbound integration layer (ดู section 1.2)
│   │   ├── __init__.py
│   │   ├── base.py                  # MarketplaceClient protocol + BaseHttpClient
│   │   ├── registry.py              # platform -> client factory
│   │   ├── errors.py                # MarketplaceError, RateLimitError, TokenExpiredError
│   │   ├── lazada/
│   │   │   ├── client.py            # LazadaClient
│   │   │   ├── signer.py            # HMAC-SHA256 signing (Lazada spec)
│   │   │   ├── oauth.py             # authorize URL / exchange code / refresh
│   │   │   ├── endpoints.py         # ค่าคงที่ api path เช่น "/orders/get"
│   │   │   └── schemas.py           # Pydantic model ของ payload ฝั่ง Lazada
│   │   ├── shopee/                  # โครงเดียวกับ lazada
│   │   └── tiktok/                  # โครงเดียวกับ lazada (+ shop_cipher)
│   ├── models/                      # SQLAlchemy / ORM models
│   ├── schemas/                     # Pydantic schemas (request/response ของ API เรา)
│   ├── services/                    # business logic layer
│   │   ├── oauth_service.py
│   │   ├── token_service.py         # refresh / rotate token
│   │   ├── webhook_service.py
│   │   └── order_sync_service.py
│   ├── repositories/                # data access layer (DB queries)
│   │   ├── shop_repository.py
│   │   └── token_repository.py
│   ├── workers/                     # background job (token refresh scheduler ฯลฯ)
│   ├── db/
│   │   ├── session.py
│   │   └── base.py
│   └── dependencies.py              # FastAPI Depends() shared
├── tests/
│   ├── conftest.py                  # fixtures กลาง
│   ├── unit/
│   │   ├── services/
│   │   ├── repositories/
│   │   └── marketplaces/            # ⭐ signing / oauth / client tests
│   ├── integration/
│   │   └── api/
│   ├── fixtures/
│   │   └── responses/               # JSON response ตัวอย่างจาก Lazada/Shopee
│   └── factories/                   # test data factories
├── alembic/                          # DB migrations
├── .env.example
├── .gitignore
├── pyproject.toml
├── requirements.txt / poetry.lock
├── Dockerfile
├── docker-compose.yml
├── CHANGELOG.md
└── README.md
```

### 1.1 หลักการแบ่ง layer

| Layer | หน้าที่ | ห้ามทำ |
|---|---|---|
| `endpoints/` | รับ request, validate, เรียก service, return response | ห้ามมี business logic หรือ query DB ตรง ๆ |
| `services/` | business logic ทั้งหมด | ห้ามรู้จัก HTTP (request/response object), ห้ามเซ็น signature เอง |
| `repositories/` | เข้าถึง DB เท่านั้น | ห้ามมี business logic |
| `marketplaces/` | คุยกับ API ภายนอก: sign, ยิง HTTP, map error, parse response | ห้ามแตะ DB, ห้ามรู้จัก FastAPI |
| `schemas/` | นิยามรูปแบบข้อมูล input/output | ห้ามมี logic การคำนวณ |

### 1.2 กฎของ `marketplaces/` (layer ที่เพิ่มมาสำหรับโปรเจกต์นี้)

`marketplaces/` คือ **outbound gateway** — เป็นพี่น้องกับ `repositories/` (ตัวหนึ่งคุยกับ DB อีกตัวคุยกับ API ภายนอก)
service layer เรียกทั้งสองตัวได้ แต่ทั้งสองตัวห้ามเรียก service กลับ

- ทุก platform ต้อง implement `MarketplaceClient` protocol เดียวกัน — service layer ต้องเขียนโค้ดครั้งเดียวใช้ได้ทุกเจ้า
- client **ห้ามอ่าน DB เอง** — token ถูกส่งเข้ามาเป็น parameter โดย service เสมอ
- client รับ `httpx.AsyncClient` ผ่าน constructor (inject) เพื่อให้ mock ง่ายใน test
- error จากภายนอกต้องแปลงเป็น exception ของเราเสมอ (`RateLimitError`, `TokenExpiredError`, `MarketplaceError`)
  ห้ามปล่อย `httpx.HTTPStatusError` ทะลุขึ้นไปถึง service

```python
# app/marketplaces/base.py
from typing import Protocol

class MarketplaceClient(Protocol):
    platform: str

    def build_authorize_url(self, state: str) -> str: ...
    async def exchange_code(self, code: str) -> TokenBundle: ...
    async def refresh_token(self, refresh_token: str) -> TokenBundle: ...
    async def fetch_orders(
        self, credentials: ShopCredentials, since: datetime, limit: int = 100
    ) -> list[NormalizedOrder]: ...
    def verify_webhook(self, raw_body: bytes, headers: Mapping[str, str]) -> bool: ...
```

---

## 2. Coding Standard

### 2.1 Style & Formatting
- ใช้ **Black** จัด format, **Ruff** สำหรับ lint (แทน flake8+isort+pyupgrade)
- Line length: 88 (ตาม Black default) หรือกำหนด 100 ให้ตรงกันทั้งทีม
- ใช้ `pre-commit` hook รัน black/ruff/mypy อัตโนมัติก่อน commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.x
    hooks: [{id: black}]
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.x
    hooks: [{id: ruff, args: [--fix]}]
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.x
    hooks: [{id: mypy}]
  - repo: https://github.com/Yelp/detect-secrets      # ⭐ กัน app_secret หลุด
    rev: v1.x
    hooks: [{id: detect-secrets}]
```

### 2.2 Type Hints
- **บังคับ** ใส่ type hint ทุกฟังก์ชัน (parameter + return type) — เปิด `mypy --strict` หรืออย่างน้อย `disallow_untyped_defs = true`
- ใช้ Pydantic model แทน `dict[str, Any]` เสมอเมื่อรับ/ส่งข้อมูลผ่าน API
- **response จาก marketplace ก็ต้อง parse เข้า Pydantic เช่นกัน** ห้ามส่ง raw dict ต่อขึ้นไปยัง service

```python
# ❌ ห้าม
def get_user(id):
    ...

async def fetch_orders(self, token):
    return (await self._client.get(...)).json()["data"]["orders"]   # dict ลอย

# ✅ ต้องเป็นแบบนี้
def get_user(user_id: int) -> UserOut | None:
    ...

async def fetch_orders(
    self, credentials: ShopCredentials, since: datetime, limit: int = 100
) -> list[NormalizedOrder]:
    ...
```

### 2.3 Naming Convention
- ไฟล์/module: `snake_case.py`
- Class: `PascalCase`
- Function/variable: `snake_case`
- Constant: `UPPER_SNAKE_CASE`
- Pydantic schema: `UserCreate`, `UserOut`, `UserUpdate` (ต่อท้ายด้วย action/ทิศทาง ไม่ใช้ชื่อซ้ำกับ ORM model)
- **Schema ฝั่ง marketplace:** ขึ้นต้นด้วยชื่อ platform เสมอ — `LazadaOrderRaw`, `ShopeeOrderRaw`
  ส่วน model กลางที่ normalize แล้วใช้ prefix `Normalized` — `NormalizedOrder`, `NormalizedProduct`
- **Client class:** `<Platform>Client` — `LazadaClient`, `ShopeeClient`, `TikTokClient`

### 2.4 Async
- endpoint ที่เรียก I/O (DB, HTTP call ภายนอก) ต้องเป็น `async def` และใช้ driver ที่ support async (เช่น `asyncpg`, `httpx.AsyncClient`)
- ห้ามเรียกโค้ด blocking (เช่น `requests`, `time.sleep`) ใน `async def` ตรง ๆ — ใช้ `run_in_threadpool` ถ้าจำเป็น
- **ใช้ `httpx.AsyncClient` ตัวเดียวตลอด lifetime ของแอป** (สร้างใน lifespan handler แล้ว inject)
  ห้ามสร้าง client ใหม่ทุก request — เสีย connection pool และทำให้ mock ยาก
- Webhook endpoint ต้อง **ตอบ 200 ให้เร็วที่สุด** แล้วโยนงานหนักเข้า background task/queue
  (marketplace ส่วนใหญ่ retry ถ้าเราตอบช้าเกิน timeout)

### 2.5 Dependency Injection
- ใช้ `Depends()` สำหรับ DB session, current user, config, **marketplace client** แทนการสร้าง object เองในฟังก์ชัน — ทำให้ mock/test ง่าย

```python
# app/dependencies.py
def get_marketplace_client(
    platform: Platform,
    http: Annotated[httpx.AsyncClient, Depends(get_http_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MarketplaceClient:
    return CLIENT_REGISTRY[platform](http=http, settings=settings)
```

### 2.6 Error Handling
- สร้าง custom exception class ของแอปเอง (เช่น `UserNotFoundError`) แล้วจับด้วย `@app.exception_handler`
- ห้าม `except Exception: pass` แบบเงียบ ๆ ต้อง log เสมอ
- ตอบ error response เป็นรูปแบบเดียวกันทั้งระบบ (เช่น `{"detail": "...", "code": "..."}`)
- **Marketplace error mapping (บังคับ):**

| อาการจากภายนอก | Exception ของเรา | การจัดการ |
|---|---|---|
| HTTP 429 / error code rate limit | `RateLimitError` | retry แบบ exponential backoff + jitter (สูงสุด 3 ครั้ง) |
| token หมดอายุ / invalid | `TokenExpiredError` | refresh token แล้ว retry คำขอเดิม 1 ครั้ง |
| 5xx / timeout / connect error | `MarketplaceUnavailableError` | retry ได้ ถ้ายังไม่ผ่านให้ raise ขึ้น |
| 4xx อื่น ๆ (business error) | `MarketplaceError` (มี `code`, `message`) | **ห้าม retry** log แล้ว raise |

> ⚠️ **สำคัญ:** Lazada/Shopee ตอบ HTTP 200 แม้จะ error — ต้องเช็ค field `code` ใน body เสมอ
> ห้ามใช้ `response.raise_for_status()` เป็นเงื่อนไขเดียวในการตัดสินว่าสำเร็จ

### 2.7 Config & Secrets
- ใช้ `pydantic-settings` อ่านค่าจาก `.env`
- ห้าม hardcode secret/URL/credential ในโค้ด
- ต้องมี `.env.example` ที่ระบุ key ทั้งหมด (ไม่มีค่าจริง)
- **`app_secret` ต้องประกาศเป็น `SecretStr`** ไม่ใช่ `str` เพื่อกันหลุดตอน repr/log
- host ของแต่ละ environment ต้องมาจาก config เท่านั้น (สลับ sandbox ↔ production ได้โดยไม่แก้โค้ด)

```python
# app/core/config.py
from pydantic import SecretStr, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

class LazadaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LAZADA_")

    app_key: str
    app_secret: SecretStr
    api_base_url: HttpUrl = "https://api.lazada.co.th/rest"   # gateway ราย country
    auth_base_url: HttpUrl = "https://auth.lazada.com/rest"   # token create/refresh
    authorize_url: HttpUrl = "https://auth.lazada.com/oauth/authorize"
    redirect_uri: HttpUrl
    country: str = "TH"
```

### 2.8 Logging
- ใช้ `logging` module มาตรฐาน (ไม่ใช้ `print`)
- Log ระดับ: `DEBUG` (dev only), `INFO` (flow หลัก), `WARNING`, `ERROR` (พร้อม stack trace)
- **ทุก outbound call ต้อง log:** platform, api path, shop id, duration (ms), response code
  **ห้าม log:** `sign`, `app_secret`, `access_token`, `refresh_token`, `code` จาก OAuth callback
- ใส่ `logging.Filter` ตัว redact ค่าที่ match pattern เหล่านี้ใน `app/core/logging.py` เป็น safety net อีกชั้น
- ใช้ `request_id` / `correlation_id` ผูกทุก log ของ request เดียวกัน

### 2.9 Docstring
- ทุก public function/class ที่มี business logic ต้องมี docstring (Google หรือ NumPy style) อธิบาย: ทำอะไร, parameter, return, exception ที่อาจ raise
- **ฟังก์ชัน signing ต้องมี docstring อ้างอิงสูตรจาก docs ทางการ + ลิงก์หน้า docs**
  เพราะแต่ละเจ้าสูตรต่างกันเล็กน้อย ถ้าไม่เขียนไว้จะ debug ยากมากตอนเจอ error "Invalid signature"

---

## 3. API Design Standard

- REST resource naming: พหูพจน์ + kebab/lower (`/users`, `/users/{user_id}/orders`)
- ใช้ HTTP status code ให้ถูกความหมาย (`201` created, `204` no content, `404` not found, `422` validation error ฯลฯ)
- ทุก endpoint ต้องกำหนด `response_model` ชัดเจน
- Versioning: ใส่ prefix `/api/v1/...`
- ใช้ `status_code=` ระบุใน decorator แทนการ return code เอง
- Pagination มาตรฐาน: `limit`, `offset` หรือ cursor-based พร้อม response wrapper (`items`, `total`, `page`)

### 3.1 Endpoint ที่ต้องมีในโปรเจกต์นี้

| Endpoint | Method | หน้าที่ |
|---|---|---|
| `/api/v1/auth/{platform}/authorize` | GET | สร้าง authorize URL + `state` แล้ว redirect ผู้ขายไป |
| `/api/v1/auth/{platform}/callback` | GET | รับ `code` + `state` แลก token แล้วบันทึกร้าน |
| `/api/v1/webhooks/{platform}` | POST | รับ push event (ต้อง verify signature) |
| `/api/v1/shops` | GET | รายการร้านที่ authorize แล้ว + สถานะ token |
| `/api/v1/shops/{shop_id}/sync/orders` | POST | trigger sync order แบบ manual |
| `/health` , `/health/ready` | GET | liveness / readiness |

### 3.2 กฎเฉพาะของ OAuth callback & webhook
- **`state` บังคับ** — สุ่มค่า เก็บลง store พร้อม TTL ตรวจตอน callback ป้องกัน CSRF ห้ามข้าม
- Callback URL ต้องเป็น **HTTPS** เท่านั้น (dev ใช้ ngrok/cloudflared) และต้องตรงกับที่ตั้งไว้ใน Console เป๊ะ
- Webhook endpoint:
  - อ่าน **raw body** ก่อน parse JSON (signature คำนวณจาก raw bytes)
  - verify signature → ถ้าไม่ผ่านตอบ `401` และ log เป็น `WARNING`
  - ตอบ `200` ทันทีหลัง enqueue ห้ามรอ business logic เสร็จ
  - **idempotent** — เก็บ event id ที่เคยประมวลผลแล้ว ถ้าซ้ำให้ข้าม (marketplace ส่งซ้ำได้)

---

## 4. Testing Standard (บังคับ)

### 4.1 กฎเหล็ก
> **ทุกฟังก์ชัน (service, repository, marketplace client, utility) และทุก endpoint ต้องมี pytest test case อย่างน้อย 1 กรณี happy path + 1 กรณี edge/error case**
> โค้ดที่ไม่มี test ห้าม merge เข้า main/develop
> **ห้าม test ยิง API จริงของ Lazada/Shopee/TikTok เด็ดขาด** — ทั้งเปลือง quota, ผลไม่ deterministic, และ CI จะพังเวลา sandbox ล่ม

### 4.2 โครงสร้าง test
- โครงสร้าง `tests/` ต้อง mirror โครงสร้าง `app/` (เช่น `app/services/user_service.py` → `tests/unit/services/test_user_service.py`)
- แยก **unit test** (mock DB/external call, เร็ว) กับ **integration test** (เรียก DB จริง/test container, endpoint จริงผ่าน `TestClient`)
- เก็บ JSON response ตัวอย่างจริงจาก sandbox ไว้ใน `tests/fixtures/responses/lazada/orders_get_success.json`
  แล้วใช้เป็น input ของ mock — ได้ test ที่สมจริงโดยไม่ต้องยิงจริง (**ลบ token/ข้อมูลลูกค้าออกก่อน commit**)

### 4.3 เขียน test อย่างไร
- ใช้ pattern **Arrange – Act – Assert**
- ชื่อ test function: `test_<หน้าที่>_<เงื่อนไข>_<ผลลัพธ์ที่คาดหวัง>` เช่น `test_create_user_with_duplicate_email_raises_conflict`
- ใช้ `pytest.fixture` ใน `conftest.py` สำหรับของที่ใช้ร่วมกัน (DB session, test client, sample data)
- ใช้ `pytest.mark.parametrize` แทนการ copy-paste test case คล้ายกัน
- Mock external service ด้วย `respx` (สำหรับ httpx) / `pytest-mock`
- Freeze เวลาด้วย `freezegun` หรือ inject `clock` เข้าไป — จำเป็นเพราะ signature ผูกกับ `timestamp`
- ทดสอบ FastAPI endpoint ด้วย `httpx.AsyncClient` + `ASGITransport`

```python
# tests/unit/services/test_user_service.py
import pytest
from app.services.user_service import create_user
from app.schemas.user import UserCreate

class TestCreateUser:
    async def test_create_user_success_returns_user(self, db_session, user_factory):
        # Arrange
        payload = UserCreate(email="test@example.com", password="Str0ngPass!")
        # Act
        result = await create_user(db_session, payload)
        # Assert
        assert result.email == "test@example.com"
        assert result.id is not None

    async def test_create_user_duplicate_email_raises_error(self, db_session, user_factory):
        # Arrange
        await user_factory(email="dup@example.com")
        payload = UserCreate(email="dup@example.com", password="Str0ngPass!")
        # Act & Assert
        with pytest.raises(DuplicateEmailError):
            await create_user(db_session, payload)
```

```python
# tests/integration/api/test_users_api.py
import pytest

class TestUsersAPI:
    async def test_get_user_not_found_returns_404(self, client):
        response = await client.get("/api/v1/users/999999")
        assert response.status_code == 404
        assert response.json()["detail"] == "User not found"
```

### 4.3.1 Test ที่ marketplace layer ต้องมี (บังคับครบทุกข้อ)

**A. Signing — golden test**
ล็อก `app_secret` ปลอมกับ `timestamp` คงที่ แล้ว assert ค่า sign แบบตัวต่อตัว
ถ้ามีใครแก้ลำดับ sort หรือ encoding ทีหลัง test ตัวนี้จะพังทันที

```python
# tests/unit/marketplaces/lazada/test_signer.py
from app.marketplaces.lazada.signer import sign_request

class TestLazadaSigner:
    def test_sign_request_with_known_params_returns_expected_signature(self):
        # Arrange
        params = {
            "app_key": "141659",
            "timestamp": "1755000000000",
            "sign_method": "sha256",
            "access_token": "dummy-token",
        }
        # Act
        signature = sign_request(
            api_path="/orders/get", params=params, app_secret="test-secret"
        )
        # Assert — ค่านี้คำนวณมือครั้งเดียวแล้วล็อกไว้ ห้ามแก้โดยไม่มีเหตุผล
        assert signature == "EXPECTED_UPPERCASE_HEX_HERE"
        assert signature.isupper()

    def test_sign_request_ignores_sign_key_if_present(self):
        params = {"app_key": "141659", "timestamp": "1755000000000", "sign": "stale"}
        with_sign = sign_request("/orders/get", params, "test-secret")
        params.pop("sign")
        without_sign = sign_request("/orders/get", params, "test-secret")
        assert with_sign == without_sign

    def test_sign_request_is_order_independent(self):
        """key ต้องถูก sort ก่อน concat — สลับลำดับ dict แล้วผลต้องเท่าเดิม"""
        a = {"b": "2", "a": "1"}
        b = {"a": "1", "b": "2"}
        assert sign_request("/x", a, "s") == sign_request("/x", b, "s")
```

**B. OAuth flow**
- `build_authorize_url` ประกอบ query string ครบ (`client_id`, `redirect_uri`, `response_type=code`, `state`)
- `exchange_code` success → คืน `TokenBundle` ที่ field ครบ
- `exchange_code` เจอ error code จาก body (HTTP 200 แต่ `code != "0"`) → raise `MarketplaceError`
- `refresh_token` success → token ใหม่ถูกเขียนทับ, `expires_at` ถูกคำนวณจาก `expires_in` ที่ตอบมาจริง

**C. Client / retry**
- ตอบ 429 → retry ตามจำนวนครั้งที่กำหนด แล้ว raise `RateLimitError` (assert จำนวนครั้งที่ยิงจริงด้วย `respx`)
- ตอบ token expired → เรียก refresh 1 ครั้ง แล้ว retry คำขอเดิมสำเร็จ
- response body เพี้ยน/field หาย → raise `MarketplaceError` ไม่ใช่ `KeyError`

**D. Webhook**
- signature ถูกต้อง → `200` และ event ถูก enqueue
- signature ผิด → `401` และ **ไม่มี** การ enqueue
- ส่ง event id เดิมซ้ำ → ประมวลผลครั้งเดียว (idempotency)

**E. Redaction**
- log ที่ออกมาจาก flow ทั้งหมด **ต้องไม่มี** `app_secret` / `access_token` — assert ด้วย `caplog`

```python
# tests/unit/marketplaces/test_client_retry.py
import httpx, pytest, respx
from app.marketplaces.errors import RateLimitError

class TestLazadaClientRetry:
    @respx.mock
    async def test_fetch_orders_rate_limited_retries_then_raises(self, lazada_client, credentials):
        # Arrange
        route = respx.get(url__startswith="https://api.lazada.co.th/rest/orders/get").mock(
            return_value=httpx.Response(429, json={"code": "ApiCallLimit"})
        )
        # Act & Assert
        with pytest.raises(RateLimitError):
            await lazada_client.fetch_orders(credentials, since=..., limit=10)
        assert route.call_count == 3        # 1 ครั้งแรก + retry 2
```

### 4.4 Coverage
- ตั้ง minimum coverage ที่ **80%** และเช็คใน CI
- **`app/marketplaces/` ต้อง >= 90%** เพราะเป็นจุดที่ debug ยากที่สุดตอน production และ mock ได้ง่ายที่สุด
- รันด้วย: `pytest --cov=app --cov-report=term-missing --cov-fail-under=80`

### 4.5 ตั้งค่า pytest

```ini
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-ra -q --cov=app --cov-report=term-missing --cov-fail-under=80"
markers = [
    "sandbox: ยิง sandbox จริง — ไม่รันใน CI (deselect ด้วย -m 'not sandbox')",
]

[tool.coverage.run]
omit = ["*/tests/*", "*/migrations/*"]
```

> **ข้อยกเว้นเดียว** ที่อนุญาตให้ยิงของจริงคือ test ที่ mark `@pytest.mark.sandbox`
> ต้องยิง **sandbox เท่านั้น** ห้ามยิง production, ต้องข้ามอัตโนมัติถ้าไม่มี credential ใน env,
> และ CI ต้องรันด้วย `-m "not sandbox"` เสมอ

### 4.6 Dependency สำหรับ test

```
pytest
pytest-asyncio
pytest-cov
pytest-mock
httpx
respx              # mock httpx — ใช้แทนการยิง marketplace API จริง
freezegun          # freeze timestamp สำหรับ test signature
faker              # สำหรับสร้าง test data
factory-boy        # สำหรับ test data factories (optional)
```

---

## 5. Git Workflow

- Branch naming: `feature/<ชื่อ>`, `fix/<ชื่อ>`, `chore/<ชื่อ>`
- Commit message: Conventional Commits — `feat:`, `fix:`, `test:`, `refactor:`, `docs:`, `chore:`
- ก่อนเปิด PR: ต้องผ่าน lint + type check + test ทั้งหมด (local หรือ CI)
- PR checklist ขั้นต่ำ:
  - [ ] มี test ครอบคลุม
  - [ ] ไม่มี secret หลุด (รวมถึง fixture JSON ที่ก๊อปมาจาก sandbox — ต้อง scrub token/PII ออก)
  - [ ] อัปเดต docs/README ถ้าจำเป็น
  - [ ] ถ้าแตะ signing/OAuth — ระบุใน PR ว่าทดสอบกับ sandbox ของเจ้าไหนแล้วบ้าง

---

## 6. CI/CD Checklist (ตัวอย่าง GitHub Actions)

รันตามลำดับทุก push/PR:
1. `ruff check .`
2. `black --check .`
3. `mypy app`
4. `pytest --cov=app --cov-fail-under=80 -m "not sandbox"`
5. `detect-secrets scan --baseline .secrets.baseline`
6. Build Docker image (ถ้ามี)

---

## 7. Marketplace Integration Reference

> ⚠️ ตัวเลขและ path ในตารางนี้เป็นสรุปเพื่อวางโครง — **ยืนยันกับ docs ทางการทุกครั้งก่อน implement**
> และ **อย่า hardcode อายุ token** ให้อ่านจาก `expires_in` / `refresh_expires_in` ใน response จริง

### 7.1 สถานะปัจจุบันของโปรเจกต์

| Platform | สถานะ | หมายเหตุ |
|---|---|---|
| **Lazada** | ✅ App สร้างแล้ว | App: **Miot**, App Key `141659`, category **Seller In-house APP**, status **Testing** |
| **Shopee** | ⏸ ค้าง | ติด step 2 "Fill in Seller Identification Details" ปุ่ม Next กดไม่ได้ ยังไม่ได้ยื่น profile |
| **TikTok Shop** | ⬜ ยังไม่เริ่ม | |

Console: <https://isvconsole.lazada.com/apps/console/apps>

### 7.2 เปรียบเทียบ 3 แพลตฟอร์ม

| | Lazada | Shopee | TikTok Shop |
|---|---|---|---|
| Credential | `app_key` + `app_secret` | `partner_id` + `partner_key` | `app_key` + `app_secret` |
| Gateway | `api.lazada.co.th/rest` (แยกราย country) | `partner.shopeemobile.com` | `open-api.tiktokglobalshop.com` |
| Sandbox | test account ใน console | `partner.test-stable.shopeemobile.com` | Development Shop + generate test token |
| Sign | HMAC-SHA256 → **hex ตัวใหญ่** | HMAC-SHA256 → **hex ตัวเล็ก** | HMAC-SHA256 |
| Base string | `api_path` + `k1v1k2v2...` (sort ตาม key) | `partner_id + path + timestamp [+ access_token + shop_id]` | path + sorted params (ไม่รวมบาง key) |
| ตัวระบุร้าน | `seller_id` | `shop_id` | `shop_cipher` |
| Timestamp | **millisecond** | **second** | second |

> จุดพลาดที่เจอบ่อยที่สุด: **หน่วยของ timestamp** (ms vs s) กับ **ตัวพิมพ์ของ hex** (upper vs lower)
> ทั้งสองอย่างทำให้ได้ error "Invalid signature" เหมือนกันหมด — ให้ golden test ใน 4.3.1 A จับไว้

### 7.3 Lazada — สิ่งที่ต้อง implement ก่อน (milestone แรก)

1. `signer.py` — HMAC-SHA256, sort key, concat `api_path + k+v...`, hexdigest **uppercase**, ตัด key `sign` ออกก่อนคำนวณ
2. `oauth.py` — สร้าง authorize URL, `POST /auth/token/create` (แลก code), `POST /auth/token/refresh`
3. `client.py` — แนบ common params (`app_key`, `timestamp` เป็น ms, `sign_method=sha256`, `access_token`, `sign`) ทุก call
4. เช็ค `code` ใน response body ทุกครั้ง (`"0"` = สำเร็จ) ไม่ใช่ดูแค่ HTTP status
5. เก็บ token ต่อร้านลง DB (เข้ารหัสตาม 8.2) + worker refresh ก่อนหมดอายุ

```python
# app/marketplaces/lazada/signer.py
import hashlib
import hmac
from collections.abc import Mapping

def sign_request(api_path: str, params: Mapping[str, str], app_secret: str) -> str:
    """คำนวณ signature ตามสเปกของ Lazada Open Platform.

    สูตร: base = api_path + "".join(key + value for key, value in sorted(params))
    แล้ว HMAC-SHA256 ด้วย app_secret คืนค่าเป็น hex ตัวพิมพ์ใหญ่

    Args:
        api_path: path ของ API เช่น "/orders/get" (ไม่รวม host)
        params: query/body params ทั้งหมด **ไม่รวม** key `sign`
        app_secret: secret ของแอปจาก Open Platform console

    Returns:
        Signature เป็น hex string ตัวพิมพ์ใหญ่

    Reference:
        https://open.lazada.com/apps/doc/doc?nodeId=10450&docId=108069
    """
    payload = api_path + "".join(
        f"{key}{value}" for key, value in sorted(params.items()) if key != "sign"
    )
    return hmac.new(
        app_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest().upper()
```

### 7.4 `.env.example`

```dotenv
# --- App ---
APP_ENV=local                       # local | sandbox | production
LOG_LEVEL=INFO
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/streamora
TOKEN_ENCRYPTION_KEY=               # Fernet key สำหรับเข้ารหัส token ใน DB

# --- Lazada (App: Miot) ---
LAZADA_APP_KEY=
LAZADA_APP_SECRET=
LAZADA_API_BASE_URL=https://api.lazada.co.th/rest
LAZADA_AUTH_BASE_URL=https://auth.lazada.com/rest
LAZADA_AUTHORIZE_URL=https://auth.lazada.com/oauth/authorize
LAZADA_REDIRECT_URI=https://<ngrok-domain>/api/v1/auth/lazada/callback
LAZADA_COUNTRY=TH

# --- Shopee (ยังไม่ได้ credential) ---
SHOPEE_PARTNER_ID=
SHOPEE_PARTNER_KEY=
SHOPEE_API_BASE_URL=https://partner.test-stable.shopeemobile.com
SHOPEE_REDIRECT_URI=

# --- TikTok Shop (ยังไม่เริ่ม) ---
TIKTOK_APP_KEY=
TIKTOK_APP_SECRET=
TIKTOK_API_BASE_URL=https://open-api.tiktokglobalshop.com
TIKTOK_REDIRECT_URI=
```

---

## 8. Security Checklist

### 8.1 ทั่วไป
- Validate/sanitize input ทุกจุดผ่าน Pydantic (ห้าม trust input จาก client)
- ใช้ `passlib`/`bcrypt` hash password ห้ามเก็บ plain text
- เปิด CORS เฉพาะ origin ที่จำเป็น ห้ามใช้ `*` ใน production
- Rate limiting สำหรับ endpoint sensitive (login, register, callback)

### 8.2 Token & Credential ของร้านค้า (เพิ่มสำหรับโปรเจกต์นี้)
- `access_token` / `refresh_token` ของผู้ขาย **ต้องเข้ารหัสก่อนเก็บลง DB** (Fernet / KMS)
  ไม่ใช่ hash เพราะต้องถอดกลับมาใช้ได้ — key อยู่ใน env/secret manager ไม่อยู่ใน DB
- ห้ามส่ง token กลับออกทาง API ของเราเด็ดขาด (`/shops` ตอบแค่สถานะกับ `expires_at`)
- token คนละร้านต้องแยกกันสนิท — ทุก query ต้องมี `shop_id` เป็นเงื่อนไข กัน cross-tenant leak
- refresh ต้องกัน race — ใช้ lock/`SELECT ... FOR UPDATE` ไม่งั้น refresh พร้อมกันหลาย request จะทำให้ token ก่อนหน้าใช้ไม่ได้
- เก็บ audit log ทุกครั้งที่มีการ authorize / revoke ร้าน

### 8.3 สิ่งที่ห้าม log เด็ดขาด
`app_secret`, `partner_key`, `sign`, `access_token`, `refresh_token`, OAuth `code`,
ข้อมูลลูกค้าเต็ม (ชื่อ-ที่อยู่-เบอร์โทรจาก order payload) — ถ้าจำเป็นต้อง log ให้ mask เหลือ 4 ตัวท้าย

### 8.4 Webhook
- verify signature จาก raw body ทุกครั้งก่อนประมวลผล
- ใช้ `hmac.compare_digest` เปรียบเทียบ signature (กัน timing attack) ห้ามใช้ `==`
- reject request ที่ timestamp เก่าเกิน 5 นาที (กัน replay)

---

## 9. เมื่อขึ้นโปรเจกต์ใหม่ (Bootstrap Steps)

1. สร้างโครงสร้างตาม section 1
2. ตั้งค่า `pyproject.toml` (dependencies, pytest, black, ruff, mypy config)
3. ตั้งค่า `pre-commit` และรัน `pre-commit install`
4. สร้าง `.env.example` (ตาม 7.4) + `app/core/config.py`
5. เขียน `tests/conftest.py` (fixture: db session, test client, `respx` mock, `lazada_client`, `credentials`)
6. Setup CI pipeline (section 6)
7. เขียน README อธิบายวิธีรันโปรเจกต์ + วิธีรัน test + วิธีตั้ง ngrok สำหรับ callback URL
8. **กลับมาอ่าน checklist ใน section 0 ทุกครั้งก่อนเริ่มเขียนฟีเจอร์ใหม่**

### 9.1 ลำดับงานที่แนะนำสำหรับ Streamora (Lazada ก่อน)

| # | งาน | Definition of Done |
|---|---|---|
| 1 | Bootstrap โครงสร้าง + config + CI | `pytest` ผ่าน, CI เขียว, `/health` ตอบ 200 |
| 2 | `lazada/signer.py` | golden test ครบ 3 เคสใน 4.3.1 A ผ่าน |
| 3 | `lazada/oauth.py` + `/auth/lazada/callback` | test OAuth ครบ (4.3.1 B) + authorize sandbox ผ่านจริง 1 รอบ |
| 4 | Token storage + encryption + refresh worker | token เข้ารหัสใน DB, test refresh + race ผ่าน |
| 5 | `LazadaClient.fetch_orders` + normalize | test retry/error mapping (4.3.1 C) ผ่าน |
| 6 | Webhook receiver | test signature + idempotency (4.3.1 D) ผ่าน |
| 7 | ทำ Shopee ซ้ำ โดย**ไม่แก้** service layer | ถ้าต้องแก้ service = abstraction ผิด ให้กลับไปแก้ `base.py` |

> **เกณฑ์ตัดสินว่า abstraction ถูก:** ตอนเพิ่ม Shopee (ข้อ 7) ถ้าต้องแตะไฟล์ใน `app/services/`
> แปลว่า `MarketplaceClient` protocol ออกแบบไว้ไม่ดีพอ — แก้ที่ layer นั้น อย่าแก้ด้วย `if platform ==`
