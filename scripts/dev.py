"""CLI ช่วยทดสอบ Lazada OAuth ด้วยมือ ระหว่างที่ยังไม่ได้ deploy.

ใช้เมื่อ Callback URL ชี้ไปเครื่องอื่น — Lazada redirect ผ่าน browser ทำให้
``code`` โผล่ใน address bar เสมอ copy มายิงเข้า localhost เองได้

    uv run python scripts/dev.py token
    uv run python scripts/dev.py authorize
    uv run python scripts/dev.py exchange --code ... --state ...
"""

import argparse
import asyncio

import httpx

from app.core.config import (
    get_lazada_settings,
    get_security_settings,
    get_settings,
)
from app.core.security import TokenCipher
from app.db.session import AsyncSessionLocal
from app.marketplaces.base import Platform
from app.marketplaces.lazada.client import LazadaClient
from app.services.dev_tools import (
    finish_manual_authorization,
    issue_dev_token,
    start_manual_authorization,
)


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    async with AsyncSessionLocal() as db:
        if args.command == "token":
            token = await issue_dev_token(
                db, get_security_settings(), settings.is_production
            )
            print("\nAuthorization: Bearer " + token + "\n")
            return

        cipher = TokenCipher(settings.token_encryption_key.get_secret_value())
        async with httpx.AsyncClient(timeout=30.0) as http:
            client = LazadaClient(http=http, settings=get_lazada_settings())
            if args.command == "authorize":
                url = await start_manual_authorization(
                    db, client, cipher, Platform.LAZADA
                )
                print("\nเปิด URL นี้ใน browser แล้วกดอนุญาต:\n")
                print(url)
                print(
                    "\nหลัง redirect ให้ copy ค่า code กับ state จาก address bar "
                    "มารันคำสั่ง exchange\n"
                )
            else:
                account_id = await finish_manual_authorization(
                    db, client, cipher, Platform.LAZADA, args.code, args.state
                )
                print(f"\nผูกร้านสำเร็จ account_id={account_id}\n")


def main() -> None:
    """Entrypoint ของ CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("token", help="ออก JWT สำหรับ dev user")
    sub.add_parser("authorize", help="สร้าง authorize URL ของ Lazada")
    exchange = sub.add_parser("exchange", help="แลก code เป็น token")
    exchange.add_argument("--code", required=True)
    exchange.add_argument("--state", required=True)
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
