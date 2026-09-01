"""API path ของ Lazada Open Platform — รวมไว้ที่เดียวกันหมด ห้ามพิมพ์ string ลอยในโค้ด."""

from typing import Final

TOKEN_CREATE: Final = "/auth/token/create"
TOKEN_REFRESH: Final = "/auth/token/refresh"
ORDERS_GET: Final = "/orders/get"
ORDER_ITEMS_GET: Final = "/order/items/get"
PRODUCTS_GET: Final = "/products/get"
SELLER_GET: Final = "/seller/get"

SIGN_METHOD: Final = "sha256"
SUCCESS_CODE: Final = "0"
