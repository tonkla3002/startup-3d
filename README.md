# Streamora

Backend integration layer เชื่อม marketplace Open Platform (Lazada → Shopee → TikTok Shop)
เข้ากับระบบภายใน — sync order / product / inventory

> **อ่าน [STANDARDS.md](./STANDARDS.md) ก่อนเขียนโค้ดทุกครั้ง**

## สถานะ

| Platform | สถานะ | หมายเหตุ |
|---|---|---|
| Lazada | 🟡 App สร้างแล้ว (Testing) | App **Miot**, App Key `141659`, Seller In-house APP |
| Shopee | 🟡 โค้ดพร้อม | client + test ครบแล้ว รอ credential (profile ยังติด step 2) |
| TikTok Shop | ⬜ ยังไม่เริ่ม | |

## ความคืบหน้า (ตาม STANDARDS section 9.1)

- [x] 1. Bootstrap โครงสร้าง + config + CI
- [x] 2. `lazada/signer.py` + golden test
- [x] 3. `lazada/oauth.py` + `/auth/lazada/callback` (state กัน CSRF, ใช้ได้ครั้งเดียว)
- [x] 4. Token storage + encryption (Fernet) + auto-refresh
- [x] 5. `LazadaClient.fetch_orders` + normalize + retry/error mapping
- [x] 6. Webhook receiver (verify signature + idempotent)
- [x] 7. Auth ของผู้ใช้ระบบ: social login (Google/GitHub) + JWT + ป้องกัน endpoint
- [x] 8. เพิ่ม Shopee — แก้แค่ `config.py` + `registry.py` ไม่แตะ `services/` เลย
- [x] 9. Background worker refresh token + rate limiting
- [x] 10. เก็บออเดอร์ลง DB + endpoint sync/list
- [ ] 11. Deploy ขึ้น `streamora.thana-wan.duckdns.org` (config พร้อมแล้วใน `deploy/`)
- [ ] 12. TikTok Shop

**ยังทำไม่ได้จนกว่าจะมี credential จริง:** authorize กับ sandbox ของ Lazada จริง
(ต้องมี App Secret + ตั้ง Callback URL ใน console)

## เริ่มใช้งาน

ต้องมี [uv](https://docs.astral.sh/uv/) ติดตั้งไว้ก่อน

```bash
uv sync --group dev          # ติดตั้ง dependencies
cp .env.example .env         # แล้วเติมค่าจริง (ห้าม commit .env)

# สร้าง key สำหรับเข้ารหัส token แล้วใส่ใน TOKEN_ENCRYPTION_KEY
uv run python -c "from app.core.security import generate_key; print(generate_key())"

docker compose up -d db      # Postgres
uv run alembic upgrade head  # สร้างตาราง
uv run fastapi dev app/main.py    # fastapi-cli ตาม PROJECT_RULES 1.1
```

เปิด <http://localhost:8000/docs> เพื่อดู API docs และ <http://localhost:8000/api/v1/health> เพื่อเช็คสถานะ

## รัน test

```bash
uv run pytest                            # ทั้งหมด + coverage gate 80%
uv run pytest -m "not sandbox"           # แบบที่ CI รัน (ไม่ยิงของจริง)
uv run pytest tests/unit -q              # เฉพาะ unit test
```

**ต้องมี Docker รันอยู่** — test ที่แตะ DB ใช้ Postgres จริงผ่าน testcontainers
ตาม PROJECT_RULES 5.2b (ห้าม mock SQLAlchemy session) ถ้าไม่มี Docker test กลุ่มนั้นจะถูก skip

## Migration

```bash
uv run alembic revision --autogenerate -m "อธิบายการเปลี่ยนแปลง"
uv run alembic upgrade head
```

ตรวจไฟล์ที่ autogenerate ด้วยมือทุกครั้งก่อน commit (PROJECT_RULES 2.5b)

## ตรวจคุณภาพโค้ดก่อน commit

```bash
uv run ruff check . && uv run black --check . && uv run mypy app && uv run pytest
```

## Callback URL ตอน dev

Lazada ต้องการ HTTPS callback ที่ตรงกับที่ตั้งไว้ใน console เป๊ะ ระหว่าง dev ใช้ tunnel:

```bash
ngrok http 8000
```

แล้วเอา URL ที่ได้ไปใส่ทั้งใน `.env` (`LAZADA_REDIRECT_URI`) และในหน้า App ของ Lazada console

## Endpoint

| Endpoint | ต้องล็อกอิน | หน้าที่ |
|---|---|---|
| `GET /api/v1/health` | ไม่ | liveness |
| `GET /api/v1/auth/{provider}/login` | ไม่ | social login (google, github) |
| `GET /api/v1/auth/{provider}/callback` | ไม่ | รับ callback แล้วออก JWT ของแอป |
| `GET /api/v1/auth/me` | **ใช่** | ข้อมูลผู้ใช้ปัจจุบัน |
| `GET /api/v1/connections/{platform}/authorize` | **ใช่** | เริ่มผูกร้าน marketplace |
| `GET /api/v1/connections/{platform}/callback` | **ใช่** | รับ code จาก marketplace |
| `GET /api/v1/shops` | **ใช่** | รายการร้านที่ผูกไว้ |
| `GET /api/v1/shops/{id}/orders` | **ใช่** | ออเดอร์ที่ sync เก็บไว้ |
| `POST /api/v1/shops/{id}/sync/orders` | **ใช่** | สั่งดึงออเดอร์จาก marketplace |
| `POST /api/v1/webhooks/{platform}` | ไม่ (verify signature แทน) | รับ push event |

> `/auth/*` = login ของ **ผู้ใช้ระบบเรา**, `/connections/*` = ผูก **ร้านค้าบน marketplace**
> คนละเรื่องกัน ตั้ง path แยกเพื่อไม่ให้ชนกัน

## Deploy

ดู [deploy/README.md](./deploy/README.md) — Caddyfile snippet + systemd unit พร้อมแล้ว
ปลายทางคือ `streamora.thana-wan.duckdns.org` (DuckDNS wildcard ชี้ไปเครื่องเดิมที่รัน Caddy อยู่แล้ว
โปรเจกต์อื่นบนเครื่องนั้นไม่กระทบเพราะ Caddy แยกด้วย Host header)

## โครงสร้าง

ดู [STANDARDS.md](./STANDARDS.md) section 1 — สรุปสั้น ๆ:

- `app/api/` รับ HTTP → `app/services/` business logic → `app/repositories/` DB
- `app/marketplaces/` คุย API ภายนอก (sign / OAuth / retry) — ห้ามแตะ DB ห้ามรู้จัก FastAPI
