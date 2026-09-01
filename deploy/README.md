# Deploy

ปลายทาง: เครื่องเดียวกับที่รัน Caddy อยู่แล้ว (`119.59.103.87`)
โดเมน: `streamora.thana-wan.duckdns.org` (DuckDNS wildcard ชี้มาให้แล้ว ไม่ต้องตั้งอะไรเพิ่ม)

## ก่อน deploy — ตรวจ 5 ข้อ

1. `APP_ENV=production` ใน `.env` (จะบังคับ `https_only` ของ session cookie
   และปิด `/docs` อัตโนมัติ)
2. `SECRET_KEY` กับ `JWT_SECRET_KEY` **คนละค่า** และยาว >= 32 bytes
   — ถ้าไม่ผ่าน แอปจะไม่ยอม start (ตั้งใจให้พังตั้งแต่ต้น ดีกว่าไปพังทีหลัง)
3. `TOKEN_ENCRYPTION_KEY` ต้องเป็นค่าเดียวกับตอนเข้ารหัส token เดิม
   **ถ้าเปลี่ยน token ที่เก็บไว้จะถอดไม่ออก ทุกร้านต้อง authorize ใหม่หมด**
4. `DATABASE_URL` ชี้ Postgres ของ production
5. อัปเดต Callback URL ใน Lazada console เป็น
   `https://streamora.thana-wan.duckdns.org/api/v1/connections/lazada/callback`

## ขั้นตอน — Docker (แนะนำ)

ไม่ต้องลง Python หรือ uv บนเครื่อง server เลย

```bash
# copy โค้ด + .env ขึ้นไปที่ /srv/streamora แล้ว
cd /srv/streamora
docker compose -f docker-compose.prod.yml up -d --build

# migration รันเองอัตโนมัติตอน container start (deploy/entrypoint.sh)
docker compose -f docker-compose.prod.yml logs -f api
```

จากนั้นเพิ่ม block จาก `deploy/Caddyfile.snippet` เข้า Caddyfile

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

**สิ่งที่ compose จัดการให้แล้ว**

| | |
|---|---|
| migrate ตอน start | `entrypoint.sh` รอ DB พร้อม -> `alembic upgrade head` -> ค่อยเปิดรับ request ถ้า migrate พังจะหยุดเลย ไม่ปล่อยแอปขึ้นมาพังทีหลัง |
| ผูกเฉพาะ localhost | api map ที่ `127.0.0.1:8000` เท่านั้น ออกเน็ตตรงไม่ได้ ต้องผ่าน Caddy |
| db ไม่เปิดออก host | เข้าถึงได้จากใน network ของ compose เท่านั้น |
| non-root | container รันด้วย uid 10001 |
| restart | `unless-stopped` ทั้งสอง service |
| healthcheck | ยิง `/api/v1/health` ทุก 30 วิ |
| log rotation | json-file 10MB x 3 ไฟล์ |

`POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` ตั้งใน `.env` ได้
(ไม่ตั้ง = `streamora` ทั้งหมด — **production ต้องตั้งรหัสผ่านจริง**)

## ทางเลือก — systemd (ถ้าไม่อยากใช้ Docker)

```bash
sudo useradd -r -s /usr/sbin/nologin -d /srv/streamora streamora
cd /srv/streamora && uv sync --frozen --no-dev && uv run alembic upgrade head
sudo cp deploy/streamora.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now streamora
```

## ตรวจหลัง deploy

```bash
curl https://streamora.thana-wan.duckdns.org/api/v1/health
# ต้องได้ {"status":"ok","app":"streamora","env":"production"}

curl -s -o /dev/null -w "%{http_code}\n" https://streamora.thana-wan.duckdns.org/docs
# ต้องได้ 404 — production ต้องไม่เปิด docs

curl -s -o /dev/null -w "%{http_code}\n" https://streamora.thana-wan.duckdns.org/api/v1/shops
# ต้องได้ 401 — endpoint ที่ต้องล็อกอินต้องไม่เปิดโล่ง
```

## ข้อควรระวัง

- **Rate limiter เป็น in-memory** ถ้ารันหลาย instance counter จะแยกกัน
  ต้องย้ายไป Redis ก่อน scale
- **Token refresh worker** เปิดด้วย `TOKEN_REFRESH_WORKER_ENABLED=true`
  แต่ถ้ารันหลาย instance จะ refresh ซ้อนกัน — เปิดแค่ instance เดียว
  หรือย้ายไปเป็น cron/job แยก
- `.env` บนเครื่อง server ต้อง `chmod 600` และเจ้าของเป็น user `streamora`
