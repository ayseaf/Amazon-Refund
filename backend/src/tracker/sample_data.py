from __future__ import annotations

from datetime import date

from tracker.money import estimate_return_repurchase, format_money, line_gap_cents

SAMPLE_AS_OF = "2026-11-11"
POLICY_NOTE = (
    "Amazon does not generally guarantee post-purchase price matching. A refund is not guaranteed."
)
DISCLAIMER = (
    "SAMPLE DATA. These orders, prices, and refund amounts are fictional illustrations. "
    "Nothing is loaded from an Amazon account. A price adjustment or refund is not guaranteed."
)
CLOCK_NOTE = "Sample deadlines use the sample clock 2026-11-11, not today's date."


def days_until(deadline: str | None, as_of: str = SAMPLE_AS_OF) -> int | None:
    if deadline is None:
        return None
    return (date.fromisoformat(deadline) - date.fromisoformat(as_of)).days


def deadline_warning(days: int | None, eligible: bool | None) -> str | None:
    if days is None:
        return None
    if days < 0:
        return "passed"
    if eligible is False:
        return None
    if days == 0:
        return "due today"
    if days <= 1:
        return "1 day"
    if days <= 3:
        return "3 days"
    if days <= 7:
        return "7 days"
    return None


def draft_price_adjustment_message(item: dict) -> str:
    if item.get("latest_price_cents") is None or item.get("line_difference_cents") is None:
        raise ValueError("A draft needs a recorded current price")
    return (
        "Hello,\n\n"
        f"I purchased {item['title']} (ASIN {item['asin']}) on {item['purchased_at']} "
        f"in order {item['order_id']} for {format_money(item['unit_price_cents'])} each, "
        f"quantity {item['quantity']}.\n\n"
        f"A later public price I have on record is {format_money(item['latest_price_cents'])}, "
        f"a line difference of {format_money(item['line_difference_cents'])} before fees.\n\n"
        "I am asking whether a price adjustment or partial refund is available. "
        "I understand Amazon does not generally guarantee post-purchase price matching, "
        "and that a refund is not guaranteed.\n\n"
        "Thank you.\n"
    )


def _raw_items() -> list[dict]:
    return [
        {
            "order_id": "SAMPLE-111-0000001",
            "asin": "SAMPLE0001",
            "title": "[SAMPLE] Over-ear headphones",
            "purchased_at": "2026-10-15",
            "quantity": 1,
            "unit_price_cents": 7999,
            "shipping_cents": 0,
            "tax_cents": 640,
            "seller_name": "[SAMPLE] Example Seller",
            "condition": "New",
            "return_eligible": True,
            "return_deadline_at": "2026-11-18",
            "monitoring_status": "monitoring",
            "latest_price_cents": 6499,
            "latest_price_checked_at": "2026-11-10T15:00:00+00:00",
            "price_source": "sample",
            "price_adjustment_available": None,
            "price_adjustment_note": "Not determined. Phase 1 does not contact Amazon or sellers.",
        },
        {
            "order_id": "SAMPLE-111-0000002",
            "asin": "SAMPLE0002",
            "title": "[SAMPLE] USB-C cable",
            "purchased_at": "2026-10-28",
            "quantity": 2,
            "unit_price_cents": 1299,
            "shipping_cents": 399,
            "tax_cents": 208,
            "seller_name": "[SAMPLE] Example Seller",
            "condition": "New",
            "return_eligible": True,
            "return_deadline_at": "2026-11-14",
            "monitoring_status": "monitoring",
            "latest_price_cents": 999,
            "latest_price_checked_at": "2026-11-10T15:00:00+00:00",
            "price_source": "sample",
            "price_adjustment_available": None,
            "price_adjustment_note": "Not determined. Phase 1 does not contact Amazon or sellers.",
        },
        {
            "order_id": "SAMPLE-111-0000003",
            "asin": "SAMPLE0003",
            "title": "[SAMPLE] Cast iron skillet",
            "purchased_at": "2026-10-30",
            "quantity": 1,
            "unit_price_cents": 4499,
            "shipping_cents": 0,
            "tax_cents": 360,
            "seller_name": "[SAMPLE] Example Seller",
            "condition": "New",
            "return_eligible": True,
            "return_deadline_at": "2026-11-12",
            "monitoring_status": "monitoring",
            "latest_price_cents": 3999,
            "latest_price_checked_at": "2026-11-10T15:00:00+00:00",
            "price_source": "sample",
            "price_adjustment_available": False,
            "price_adjustment_note": (
                "SAMPLE scenario: treated as no price adjustment offered, so a return can be compared. "
                "This is not a decision from Amazon."
            ),
            "repurchase_tax_cents": 320,
            "return_shipping_cents": 0,
            "restocking_fee_cents": 0,
            "repurchase_shipping_cents": 0,
        },
        {
            "order_id": "SAMPLE-111-0000004",
            "asin": "SAMPLE0004",
            "title": "[SAMPLE] Paperback cookbook",
            "purchased_at": "2026-09-01",
            "quantity": 1,
            "unit_price_cents": 1899,
            "shipping_cents": 0,
            "tax_cents": 152,
            "seller_name": "[SAMPLE] Example Seller",
            "condition": "New",
            "return_eligible": False,
            "return_deadline_at": "2026-10-01",
            "monitoring_status": "unavailable",
            "latest_price_cents": None,
            "latest_price_checked_at": None,
            "price_source": None,
            "price_adjustment_available": None,
            "price_adjustment_note": "Not determined. There is no current price in the sample.",
            "monitoring_note": "SAMPLE: no permitted price source is configured for this row.",
        },
        {
            "order_id": "SAMPLE-111-0000005",
            "asin": "SAMPLE0005",
            "title": "[SAMPLE] Monitor arm",
            "purchased_at": "2026-10-01",
            "quantity": 1,
            "unit_price_cents": 8999,
            "shipping_cents": 0,
            "tax_cents": 720,
            "seller_name": "[SAMPLE] Example Seller",
            "condition": "New",
            "return_eligible": True,
            "return_deadline_at": "2026-12-01",
            "monitoring_status": "monitoring",
            "latest_price_cents": 7999,
            "latest_price_checked_at": "2026-11-10T15:00:00+00:00",
            "price_source": "sample",
            "price_adjustment_available": None,
            "price_adjustment_note": "Not determined. Phase 1 does not contact Amazon or sellers.",
        },
        {
            "order_id": "SAMPLE-111-0000006",
            "asin": "SAMPLE0006",
            "title": "[SAMPLE] Desk lamp",
            "purchased_at": "2026-10-05",
            "quantity": 1,
            "unit_price_cents": 3500,
            "shipping_cents": 0,
            "tax_cents": 280,
            "seller_name": "[SAMPLE] Example Seller",
            "condition": "New",
            "return_eligible": True,
            "return_deadline_at": "2026-11-20",
            "monitoring_status": "monitoring",
            "latest_price_cents": 3000,
            "latest_price_checked_at": "2026-11-10T15:00:00+00:00",
            "price_source": "sample",
            "price_adjustment_available": None,
            "price_adjustment_note": "Not determined. Phase 1 does not contact Amazon or sellers.",
        },
    ]


def _enrich_item(raw: dict) -> dict:
    gap = line_gap_cents(raw["unit_price_cents"], raw["latest_price_cents"], raw["quantity"])
    days = days_until(raw["return_deadline_at"])
    item = {
        "data_origin": "sample",
        "sample_label": "SAMPLE",
        "currency": "USD",
        "product_url": None,
        "line_difference_cents": gap,
        "days_until_deadline": days,
        "guaranteed": False,
        **raw,
    }
    item.setdefault("monitoring_note", None)
    return item


def _refund(
    item: dict,
    *,
    status: str,
    requested_amount_cents: int,
    confirmed_refund_cents: int | None,
    final_denial: bool,
    submission_method: str | None,
    note: str,
) -> dict:
    return {
        "data_origin": "sample",
        "sample_label": "SAMPLE",
        "order_id": item["order_id"],
        "title": item["title"],
        "asin": item["asin"],
        "status": status,
        "requested_amount_cents": requested_amount_cents,
        "confirmed_refund_cents": confirmed_refund_cents,
        "draft_message": draft_price_adjustment_message(item),
        "policy_note": POLICY_NOTE,
        "final_denial": final_denial,
        "automated_submission": False,
        "submission_method": submission_method,
        "guaranteed": False,
        "note": note,
    }


def _recommended_action(item: dict, refund: dict | None, repurchase: dict | None) -> str:
    if refund and refund["status"] == "accepted":
        return "Sample refund already recorded as confirmed. No further action."
    if refund and refund["final_denial"]:
        return (
            "Price adjustment request was denied in this sample. "
            "Returning is a separate decision and still requires your confirmation. "
            "No return will be submitted."
        )
    if item["return_eligible"] is False:
        return "No return action. This sample item is not eligible."
    if item["price_adjustment_available"] is False and repurchase and repurchase["worth_considering"]:
        return (
            "Review a possible return and repurchase. "
            "Nothing will be submitted without your confirmation. "
            "Phase 1 cannot submit a return."
        )
    if (item["line_difference_cents"] or 0) > 0 and item["price_adjustment_available"] is None:
        return (
            "A price difference is illustrated. Whether Amazon or the seller offers an adjustment is unknown. "
            "No request will be sent."
        )
    return "No action suggested."


def build_sample_catalog() -> dict:
    items = [_enrich_item(raw) for raw in _raw_items()]
    by_order = {item["order_id"]: item for item in items}
    refunds = [
        _refund(
            by_order["SAMPLE-111-0000001"],
            status="pending",
            requested_amount_cents=1500,
            confirmed_refund_cents=None,
            final_denial=False,
            submission_method=None,
            note="SAMPLE status only. Nothing has been sent to Amazon.",
        ),
        _refund(
            by_order["SAMPLE-111-0000005"],
            status="accepted",
            requested_amount_cents=1000,
            confirmed_refund_cents=1000,
            final_denial=False,
            submission_method="manual_user",
            note=(
                "SAMPLE record of an amount a person confirmed by hand. "
                "No refund was requested or received by this application."
            ),
        ),
        _refund(
            by_order["SAMPLE-111-0000006"],
            status="denied",
            requested_amount_cents=500,
            confirmed_refund_cents=0,
            final_denial=True,
            submission_method="manual_user",
            note="SAMPLE final denial. The application will not draft or send another request for this item.",
        ),
    ]
    refund_by_order = {refund["order_id"]: refund for refund in refunds}
    covered = {
        refund["order_id"]
        for refund in refunds
        if refund["status"] == "accepted" and (refund["confirmed_refund_cents"] or 0) > 0
    }
    estimated = 0
    for item in items:
        gap = item["line_difference_cents"]
        if gap is None or gap <= 0 or item["order_id"] in covered:
            continue
        estimated += gap
    confirmed = sum(
        refund["confirmed_refund_cents"] or 0 for refund in refunds if refund["status"] == "accepted"
    )
    pending = sum(1 for refund in refunds if refund["status"] in {"submitted", "pending", "ready_for_review"})
    recent = [
        {
            "data_origin": "sample",
            "sample_label": "SAMPLE",
            "order_id": item["order_id"],
            "title": item["title"],
            "difference_cents": item["line_difference_cents"],
            "guaranteed": False,
        }
        for item in items
        if item["line_difference_cents"] not in (None, 0)
    ]
    recent.sort(key=lambda row: (-row["difference_cents"], row["order_id"]))
    upcoming = [
        {
            "data_origin": "sample",
            "sample_label": "SAMPLE",
            "order_id": item["order_id"],
            "title": item["title"],
            "return_deadline_at": item["return_deadline_at"],
            "days_until_deadline": item["days_until_deadline"],
            "warning": deadline_warning(item["days_until_deadline"], item["return_eligible"]),
        }
        for item in items
        if item["return_eligible"] and item["days_until_deadline"] is not None and 0 <= item["days_until_deadline"] <= 7
    ]
    upcoming.sort(key=lambda row: row["days_until_deadline"])

    returns = []
    for item in items:
        repurchase = None
        if (
            item["price_adjustment_available"] is False
            and item["return_eligible"]
            and item["latest_price_cents"] is not None
        ):
            repurchase = estimate_return_repurchase(
                unit_price_cents=item["unit_price_cents"],
                quantity=item["quantity"],
                current_unit_cents=item["latest_price_cents"],
                original_tax_cents=item["tax_cents"],
                repurchase_tax_cents=item.get("repurchase_tax_cents", item["tax_cents"]),
                return_shipping_cents=item.get("return_shipping_cents", 0),
                restocking_fee_cents=item.get("restocking_fee_cents", 0),
                repurchase_shipping_cents=item.get("repurchase_shipping_cents", 0),
            )
            repurchase["data_origin"] = "sample"
            repurchase["sample_label"] = "SAMPLE"
        refund = refund_by_order.get(item["order_id"])
        returns.append(
            {
                "data_origin": "sample",
                "sample_label": "SAMPLE",
                "order_id": item["order_id"],
                "title": item["title"],
                "return_eligible": item["return_eligible"],
                "return_deadline_at": item["return_deadline_at"],
                "days_until_deadline": item["days_until_deadline"],
                "warning": deadline_warning(item["days_until_deadline"], item["return_eligible"]),
                "repurchase": repurchase,
                "recommended_action": _recommended_action(item, refund, repurchase),
                "guaranteed": False,
            }
        )

    savings_history = [
        {
            "data_origin": "sample",
            "sample_label": "SAMPLE",
            "order_id": item["order_id"],
            "title": item["title"],
            "kind": "estimated_gap",
            "amount_cents": item["line_difference_cents"],
            "guaranteed": False,
            "note": "Illustrated price gap. Not a confirmed refund.",
        }
        for item in items
        if item["line_difference_cents"] is not None and item["line_difference_cents"] > 0
    ]
    for refund in refunds:
        if refund["status"] == "accepted" and (refund["confirmed_refund_cents"] or 0) > 0:
            savings_history.append(
                {
                    "data_origin": "sample",
                    "sample_label": "SAMPLE",
                    "order_id": refund["order_id"],
                    "title": refund["title"],
                    "kind": "confirmed_refund",
                    "amount_cents": refund["confirmed_refund_cents"],
                    "guaranteed": False,
                    "note": refund["note"],
                }
            )

    return {
        "data_origin": "sample",
        "sample_label": "SAMPLE",
        "disclaimer": DISCLAIMER,
        "policy_note": POLICY_NOTE,
        "amazon_connected": False,
        "last_successful_sync_at": None,
        "as_of": SAMPLE_AS_OF,
        "clock_note": CLOCK_NOTE,
        "items": items,
        "refund_requests": refunds,
        "returns": returns,
        "savings_history": savings_history,
        "monitoring": {
            "provider": None,
            "checks_running": False,
            "minimum_interval_minutes": 60,
            "note": (
                "No permitted price source is configured. "
                "The manual check records a skipped run and does not fetch a price."
            ),
            "rows": [
                {
                    "data_origin": "sample",
                    "sample_label": "SAMPLE",
                    "order_id": item["order_id"],
                    "title": item["title"],
                    "monitoring_status": item["monitoring_status"],
                    "latest_price_cents": item["latest_price_cents"],
                    "latest_price_checked_at": item["latest_price_checked_at"],
                    "price_source": item["price_source"],
                    "line_difference_cents": item["line_difference_cents"],
                    "monitoring_note": item["monitoring_note"],
                    "guaranteed": False,
                }
                for item in items
            ],
        },
        "dashboard": {
            "products_monitored": sum(1 for item in items if item["monitoring_status"] == "monitoring"),
            "estimated_savings_cents": estimated,
            "confirmed_refunds_cents": confirmed,
            "pending_refund_requests": pending,
            "upcoming_return_deadlines": upcoming,
            "recent_price_changes": recent,
            "last_successful_sync_at": None,
            "amazon_connected": False,
            "data_origin": "sample",
            "sample_label": "SAMPLE",
        },
    }
