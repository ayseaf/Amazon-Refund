"""Price, deadline, and scheduler rules. No network access."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)(\S+)"),
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)(\S+)"),
    re.compile(r"(?i)(password\s*[:=]\s*)(\S+)"),
    re.compile(r"(?i)(token\s*[:=]\s*)(\S+)"),
    re.compile(r"(?i)(secret\s*[:=]\s*)(\S+)"),
)

DEFAULT_SETTINGS: dict[str, int | bool] = {
    "monitoring_interval_minutes": 60,
    "notify_min_savings_cents": 500,
    "notify_price_decreases": True,
    "notify_return_deadlines": True,
    "notify_price_check_failures": True,
    "notify_refund_status": True,
    "notify_unmonitorable": True,
    "desktop_notifications": False,
    "email_notifications": False,
    "telegram_notifications": False,
    "restocking_fee_cents": 0,
    "return_shipping_cents": 0,
}

REFUND_POLICY = (
    "Amazon does not generally guarantee a post-purchase price adjustment. "
    "A lower price is not a refund. This application will not submit a request, "
    "a return, or a repurchase."
)

RETURNS_FORMULA = (
    "Estimate = comparable savings − restocking fee − return shipping. "
    "Both fees come from settings and default to zero. Nothing is submitted."
)

DASHBOARD_DISCLAIMER = (
    "Figures are estimates from labeled sample data or from a price check you run. "
    "Amazon does not generally guarantee a post-purchase price match, and this "
    "application will not submit a refund or a return."
)


def format_usd(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    amount = abs(cents)
    return f"{sign}${amount // 100:,}.{amount % 100:02d}"


def comparable_savings(
    *,
    quantity: int,
    unit_price_cents: int,
    purchase_shipping_cents: int,
    purchase_tax_cents: int,
    current_unit_cents: int,
    current_shipping_cents: int,
    current_tax_cents: int,
    current_coupon_cents: int,
) -> int:
    """Positive means the current equivalent total is lower than the amount paid."""
    paid = unit_price_cents * quantity + purchase_shipping_cents + purchase_tax_cents
    current = (
        current_unit_cents * quantity
        + current_shipping_cents
        + current_tax_cents
        - current_coupon_cents
    )
    return paid - current


def repurchase_estimate(
    savings: int | None,
    *,
    eligible: bool,
    comparable: bool,
    restocking_cents: int,
    return_shipping_cents: int,
) -> int | None:
    if savings is None or not eligible or not comparable:
        return None
    return savings - restocking_cents - return_shipping_cents


def offer_equivalence(
    purchase_seller: str,
    purchase_condition: str,
    current_seller: str,
    current_condition: str,
) -> tuple[bool, str]:
    if current_seller != purchase_seller:
        return (
            False,
            "Seller differs from the purchase, so this is not treated as the same offer.",
        )
    if current_condition != purchase_condition:
        return (
            False,
            "Condition differs from the purchase, so this is not treated as the same offer.",
        )
    return (
        True,
        "Seller and condition match the purchase. Shipping, tax, and any coupon are included.",
    )


def difference_label(checked: bool, comparable: bool, savings: int | None, reason: str) -> str:
    if not checked:
        return "Not checked"
    if not comparable:
        return reason
    if savings is None:
        return "No comparable price"
    if savings > 0:
        return f"Lower by {format_usd(savings)}"
    if savings < 0:
        return f"Higher by {format_usd(-savings)}"
    return "Unchanged"


def stamp_word(checked: bool, comparable: bool, savings: int | None) -> str:
    if not checked:
        return "Not checked"
    if not comparable or savings is None:
        return "Other offer"
    if savings > 0:
        return "Lower"
    if savings < 0:
        return "Higher"
    return "Unchanged"


def stamp_form(checked: bool, comparable: bool, savings: int | None, threshold: int) -> str:
    if not checked:
        return "dashed"
    if comparable and savings is not None and savings > 0 and savings >= threshold:
        return "double"
    return "solid"


def deadline_window(deadline: date, today: date) -> str | None:
    days = (deadline - today).days
    if days < 0:
        return "past"
    if days <= 1:
        return "1"
    if days <= 3:
        return "3"
    if days <= 7:
        return "7"
    return None


def redact(text: str) -> str:
    cleaned = text
    for pattern in _SECRET_PATTERNS:
        cleaned = pattern.sub(r"\1[redacted]", cleaned)
    return cleaned


@dataclass(frozen=True)
class RunDecision:
    start: bool
    reason: str


def decide_run(
    now: datetime,
    last_started: datetime | None,
    interval: timedelta,
    in_progress: bool,
) -> RunDecision:
    """Decide whether a scheduled check may start. Phase 1 does not start one."""
    if in_progress:
        return RunDecision(False, "already_running")
    if last_started is None:
        return RunDecision(True, "no_previous")
    if now - last_started < interval:
        return RunDecision(False, "interval_not_elapsed")
    return RunDecision(True, "due")


SAMPLE_ORDERS: list[dict] = [
    {
        "amazon_order_id": "SAMPLE-1001",
        "purchased_days_ago": 12,
        "shipping_cents": 0,
        "tax_cents": 240,
        "items": [
            {
                "asin": "SAMPLED01",
                "title": "Sample: Enamel kettle, 1 liter",
                "quantity": 1,
                "unit_price_cents": 4299,
                "item_shipping_cents": 0,
                "item_tax_cents": 240,
                "seller": "Sample Outlet",
                "condition": "New",
                "variation_note": "",
                "return_eligible": True,
                "return_deadline_in_days": 18,
                "current_unit_cents": 3099,
                "current_shipping_cents": 0,
                "current_tax_cents": 180,
                "current_coupon_cents": 0,
                "current_seller": "Sample Outlet",
                "current_condition": "New",
            }
        ],
    },
    {
        "amazon_order_id": "SAMPLE-1002",
        "purchased_days_ago": 20,
        "shipping_cents": 0,
        "tax_cents": 0,
        "items": [
            {
                "asin": "SAMPLED02",
                "title": "Sample: Braided HDMI cable, 2 meters",
                "quantity": 1,
                "unit_price_cents": 1499,
                "item_shipping_cents": 0,
                "item_tax_cents": 0,
                "seller": "Sample Outlet",
                "condition": "New",
                "variation_note": "",
                "return_eligible": True,
                "return_deadline_in_days": 2,
                "current_unit_cents": 999,
                "current_shipping_cents": 0,
                "current_tax_cents": 0,
                "current_coupon_cents": 0,
                "current_seller": "Other Sample Seller",
                "current_condition": "New",
            }
        ],
    },
    {
        "amazon_order_id": "SAMPLE-1003",
        "purchased_days_ago": 8,
        "shipping_cents": 0,
        "tax_cents": 152,
        "items": [
            {
                "asin": "SAMPLED03",
                "title": "Sample: Field guide to city trees",
                "quantity": 1,
                "unit_price_cents": 1899,
                "item_shipping_cents": 0,
                "item_tax_cents": 152,
                "seller": "Sample Books",
                "condition": "New",
                "variation_note": "",
                "return_eligible": True,
                "return_deadline_in_days": 6,
                "current_unit_cents": 1599,
                "current_shipping_cents": 0,
                "current_tax_cents": 128,
                "current_coupon_cents": 0,
                "current_seller": "Sample Books",
                "current_condition": "Used - Good",
            }
        ],
    },
    {
        "amazon_order_id": "SAMPLE-1004",
        "purchased_days_ago": 40,
        "shipping_cents": 0,
        "tax_cents": 0,
        "items": [
            {
                "asin": "SAMPLED04",
                "title": "Sample: Desk lamp, brass arm",
                "quantity": 1,
                "unit_price_cents": 5499,
                "item_shipping_cents": 0,
                "item_tax_cents": 0,
                "seller": "Sample Home",
                "condition": "New",
                "variation_note": "",
                "return_eligible": False,
                "return_deadline_in_days": -2,
                "current_unit_cents": 3999,
                "current_shipping_cents": 0,
                "current_tax_cents": 0,
                "current_coupon_cents": 0,
                "current_seller": "Sample Home",
                "current_condition": "New",
            }
        ],
    },
    {
        "amazon_order_id": "SAMPLE-1005",
        "purchased_days_ago": 14,
        "shipping_cents": 399,
        "tax_cents": 200,
        "items": [
            {
                "asin": "SAMPLED05",
                "title": "Sample: Pitcher filters, two pack",
                "quantity": 2,
                "unit_price_cents": 1249,
                "item_shipping_cents": 399,
                "item_tax_cents": 200,
                "seller": "Sample Outlet",
                "condition": "New",
                "variation_note": "",
                "return_eligible": True,
                "return_deadline_in_days": 1,
                "current_unit_cents": 1399,
                "current_shipping_cents": 399,
                "current_tax_cents": 220,
                "current_coupon_cents": 0,
                "current_seller": "Sample Outlet",
                "current_condition": "New",
            }
        ],
    },
    {
        "amazon_order_id": "SAMPLE-1006",
        "purchased_days_ago": 10,
        "shipping_cents": 250,
        "tax_cents": 160,
        "items": [
            {
                "asin": "SAMPLED06",
                "title": "Sample: Sand-colored mug",
                "quantity": 1,
                "unit_price_cents": 1999,
                "item_shipping_cents": 250,
                "item_tax_cents": 160,
                "seller": "Sample Outlet",
                "condition": "New",
                "variation_note": "Color: Sand",
                "return_eligible": True,
                "return_deadline_in_days": 3,
                "current_unit_cents": 1499,
                "current_shipping_cents": 0,
                "current_tax_cents": 120,
                "current_coupon_cents": 200,
                "current_seller": "Sample Outlet",
                "current_condition": "New",
            }
        ],
    },
]


def sample_quote(asin: str) -> dict | None:
    for order in SAMPLE_ORDERS:
        for item in order["items"]:
            if item["asin"] == asin:
                return item
    return None
