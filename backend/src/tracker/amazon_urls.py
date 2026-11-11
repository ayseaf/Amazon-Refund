from __future__ import annotations

import re
from urllib.parse import urlsplit

ORDER_ID_RE = re.compile(r"^\d{3}-\d{7}-\d{7}$")
ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")

SIGN_IN_URL = (
    "https://www.amazon.com/ap/signin"
    "?openid.return_to=https%3A%2F%2Fwww.amazon.com%2Fyour-orders%2Forders%3FtimeFilter%3Dlast30"
)
ORDER_HISTORY_URL = "https://www.amazon.com/your-orders/orders?timeFilter=last30"

_ALLOWED_PREFIXES = (
    "/ap/signin",
    "/your-orders",
    "/gp/your-account/order-details",
    "/gp/css/order-history",
    "/dp/",
    "/gp/product/",
)

_BLOCKED = (
    "/gp/buy",
    "/checkout",
    "/gp/css/returns",
    "/spr/returns",
    "return-request",
    "/gp/cart",
    "place-order",
    "/messages",
)


class ReadOnlyViolation(ValueError):
    """A navigation that would do more than read an order or a product page."""


def require_read_only(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != "https" or (parts.hostname or "").lower() != "www.amazon.com":
        raise ReadOnlyViolation("Only https://www.amazon.com pages can be opened.")
    path = parts.path or "/"
    lowered = path.lower()
    if any(piece in lowered for piece in _BLOCKED):
        raise ReadOnlyViolation("That Amazon page is not a read-only order or product page.")
    if any(lowered == prefix or lowered.startswith(prefix) for prefix in _ALLOWED_PREFIXES):
        return url
    raise ReadOnlyViolation("That Amazon page is not on the read-only list.")


def order_detail_url(order_id: str) -> str:
    if not ORDER_ID_RE.fullmatch(order_id):
        raise ReadOnlyViolation("Unexpected order id")
    return require_read_only(
        f"https://www.amazon.com/gp/your-account/order-details?orderID={order_id}"
    )


def product_url(asin: str) -> str:
    if not ASIN_RE.fullmatch(asin):
        raise ReadOnlyViolation("Unexpected ASIN")
    return require_read_only(f"https://www.amazon.com/dp/{asin}")


def absolute_amazon(path: str) -> str:
    if path.startswith("https://"):
        return require_read_only(path)
    if not path.startswith("/"):
        raise ReadOnlyViolation("Unexpected link")
    return require_read_only(f"https://www.amazon.com{path}")
