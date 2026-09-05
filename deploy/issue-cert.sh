#!/bin/bash
# ออก/ต่ออายุ TLS cert ของ streamora แล้วส่งขึ้น VPS
#
# ทำไมต้องทำแบบนี้: VPS ถูกบล็อก inbound จากต่างประเทศ (Let's Encrypt ตรวจไม่ได้)
# และ outbound ไป duckdns.org ก็ไม่ได้ จึงทำ DNS-01 บนเครื่อง dev แทน
# แล้วก๊อปไฟล์ cert ขึ้นไปให้ Caddy ใช้
#
#   ./deploy/issue-cert.sh
#
# ต้องมี DuckDNS token (https://www.duckdns.org หลัง login)
# ตั้งล่วงหน้าได้:  export DUCKDNS_TOKEN=xxxx

set -euo pipefail

DOMAIN="streamora.thana-wan.duckdns.org"
EMAIL="thanakornwannatong.tonkla@gmail.com"
VPS="tonkla@119.59.103.87"
REMOTE_DIR="/opt/streamora/certs"
LEGO_DIR="$(cd "$(dirname "$0")" && pwd)/certs"
CERT="$LEGO_DIR/certificates/$DOMAIN.crt"
KEY="$LEGO_DIR/certificates/$DOMAIN.key"

if [ -z "${DUCKDNS_TOKEN:-}" ]; then
  read -rsp "DuckDNS token (ไม่แสดงตอนพิมพ์): " DUCKDNS_TOKEN
  echo
fi
export DUCKDNS_TOKEN

echo "[1/4] ขอ cert ผ่าน DNS-01 (DuckDNS)"
# lego 5.x: flag ทุกตัวอยู่หลัง `run` และไม่มี subcommand `renew` แล้ว
# `run` จะต่ออายุให้เองถ้ามี cert เดิมอยู่และใกล้หมดอายุ
lego run \
  --accept-tos \
  --email "$EMAIL" \
  --dns duckdns \
  --domains "$DOMAIN" \
  --path "$LEGO_DIR"

echo "[2/4] ส่งขึ้น VPS"
ssh "$VPS" "mkdir -p $REMOTE_DIR"
scp -q "$CERT" "$VPS:$REMOTE_DIR/cert.pem"
scp -q "$KEY"  "$VPS:$REMOTE_DIR/key.pem"
ssh "$VPS" "chmod 755 $REMOTE_DIR && chmod 644 $REMOTE_DIR/cert.pem $REMOTE_DIR/key.pem"

echo "[3/4] reload Caddy (อาจถามรหัสผ่าน sudo)"
ssh -t "$VPS" "sudo systemctl reload caddy" || {
  echo "  reload ไม่สำเร็จ — รัน 'sudo systemctl reload caddy' บน VPS เอง"
}

echo "[4/4] ตรวจผล"
openssl x509 -noout -subject -enddate -in "$CERT"
echo
curl -s -o /dev/null -w "https://$DOMAIN/api/v1/health -> HTTP %{http_code}\n" \
     --max-time 15 "https://$DOMAIN/api/v1/health" || true
