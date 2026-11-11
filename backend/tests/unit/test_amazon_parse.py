from __future__ import annotations

from pathlib import Path

from tracker.amazon_challenges import detect_challenge
from tracker.amazon_parse import parse_order_detail, parse_order_history, parse_product_price

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "amazon"
TRAPS = ("ADDRESS REDACTED", "Visa ending in REDACTED", "NOT-A-REAL-PASSWORD", "ap_password")


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_order_history_reads_ids_and_dates_and_drops_personal_traps():
    page = parse_order_history(_text("order_history.html"))
    by_id = {order.order_id: order for order in page.orders}
    assert set(by_id) == {
        "112-1000001-0000001",
        "112-1000002-0000002",
        "112-1000003-0000003",
        "112-1000005-0000005",
        "112-1000004-0000004",
    }
    assert by_id["112-1000001-0000001"].purchased_on == "2026-10-20"
    assert by_id["112-1000004-0000004"].purchased_on == "2026-09-01"
    assert page.next_path == "/your-orders/orders?timeFilter=last30&startIndex=10"
    dumped = repr(page)
    for trap in TRAPS:
        assert trap not in dumped


def test_order_detail_extracts_item_fields_and_ignores_address_and_payment():
    items = parse_order_detail(_text("order_detail_lamp.html"))
    assert len(items) == 1
    item = items[0]
    assert item.order_id == "112-1000001-0000001"
    assert item.purchased_on == "2026-10-20"
    assert item.asin == "B0LAMP0001"
    assert item.title == "Redacted desk lamp"
    assert item.quantity == 2
    assert item.price_paid_cents == 2400
    assert item.seller_name == "Northwind Goods"
    assert item.fulfilled_by == "Amazon"
    assert item.condition == "New"
    assert item.delivered_on == "2026-10-23"
    assert item.return_eligible is True
    assert item.return_window_end == "2026-12-04"
    assert item.product_url == "https://www.amazon.com/dp/B0LAMP0001"
    dumped = repr(item)
    for trap in TRAPS:
        assert trap not in dumped


def test_non_returnable_and_closed_window_are_distinguished():
    mug = parse_order_detail(_text("order_detail_mug.html"))[0]
    assert mug.return_eligible is False
    assert mug.return_window_end is None
    assert mug.price_paid_cents == 1500
    assert mug.fulfilled_by == "the seller"
    book = parse_order_detail(_text("order_detail_book.html"))[0]
    assert book.return_eligible is True
    assert book.return_window_end == "2026-10-01"
    assert book.price_paid_cents == 1000


def test_missing_item_fields_stay_missing():
    item = parse_order_detail(_text("order_detail_gap.html"))[0]
    assert item.title == "Redacted cable"
    assert item.asin is None
    assert item.quantity is None
    assert item.price_paid_cents is None
    assert item.return_eligible is None
    assert item.return_window_end is None
    assert item.delivered_on == "2026-11-02"


def test_product_page_price_is_integer_cents():
    offer = parse_product_price(_text("product_lamp.html"))
    assert offer.price_cents == 1900
    assert offer.unavailable is False
    assert offer.title == "Redacted desk lamp"
    missing = parse_product_price(_text("product_unavailable.html"))
    assert missing.price_cents is None
    assert missing.unavailable is True


def test_challenge_pages_are_named_and_not_treated_as_orders():
    captcha = _text("captcha.html")
    assert detect_challenge(captcha, "https://www.amazon.com/errors/validateCaptcha").kind == "captcha"
    assert parse_order_history(captcha).orders == []
    assert detect_challenge(_text("mfa.html"), "https://www.amazon.com/ap/mfa").kind == "mfa"
    assert detect_challenge(_text("unusual.html"), "https://www.amazon.com/ap/signin").kind == "unusual_activity"
    limited = detect_challenge(_text("rate_limit.html"), "https://www.amazon.com/your-orders/orders", 429)
    assert limited is not None
    assert limited.kind == "rate_limited"
    assert detect_challenge(_text("sign_in.html"), "https://www.amazon.com/ap/signin").kind == "sign_in_required"
    assert detect_challenge(_text("orders_home.html"), "https://www.amazon.com/your-orders/orders?timeFilter=last30") is None
