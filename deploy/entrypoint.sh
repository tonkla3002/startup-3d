#!/bin/sh
# รัน migration ให้เสร็จก่อนค่อยเปิดรับ request
# ถ้า migrate พังต้องหยุดเลย ไม่ใช่ปล่อยแอปขึ้นแล้วไปพังตอน query
set -e

echo "[entrypoint] รอ database..."
until python -c "
import asyncio, os, sys
from sqlalchemy.ext.asyncio import create_async_engine

async def ping():
    engine = create_async_engine(os.environ['DATABASE_URL'])
    async with engine.connect():
        pass
    await engine.dispose()

try:
    asyncio.run(ping())
except Exception:
    sys.exit(1)
"; do
  echo "[entrypoint] database ยังไม่พร้อม รอต่อ..."
  sleep 2
done

echo "[entrypoint] รัน alembic upgrade head"
alembic upgrade head

echo "[entrypoint] เริ่มเซิร์ฟเวอร์"
exec "$@"
