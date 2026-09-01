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

## ขั้นตอน

```bash
# บนเครื่อง server
sudo useradd -r -s /usr/sbin/nologin -d /srv/streamora streamora
sudo mkdir -p /srv/streamora && sudo chown streamora:streamora /srv/streamora

# copy โค้ด + .env ขึ้นไป แล้ว
cd /srv/streamora
uv sync --frozen --no-dev
uv run alembic upgrade head

sudo cp deploy/streamora.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now streamora

# เพิ่ม block จาก deploy/Caddyfile.snippet เข้า Caddyfile แล้ว
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
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
