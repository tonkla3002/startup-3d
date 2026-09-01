"""API path ของ Shopee Open Platform."""

from typing import Final

TOKEN_CREATE: Final = "/api/v2/auth/token/get"
TOKEN_REFRESH: Final = "/api/v2/auth/access_token/get"
AUTH_PARTNER: Final = "/api/v2/shop/auth_partner"
ORDER_LIST: Final = "/api/v2/order/get_order_list"
ORDER_DETAIL: Final = "/api/v2/order/get_order_detail"

SUCCESS_CODE: Final = ""
