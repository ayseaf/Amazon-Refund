from __future__ import annotations

import pytest

from tracker.sample_data import POLICY_NOTE, build_sample_catalog, draft_price_adjustment_message


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def test_catalog_is_labeled_sample_and_not_connected():
    catalog = build_sample_catalog()
    assert catalog["data_origin"] == "sample"
    assert catalog["sample_label"] == "SAMPLE"
    assert catalog["amazon_connected"] is False
    assert catalog["last_successful_sync_at"] is None
    assert "not guaranteed" in catalog["disclaimer"].lower()
    assert catalog["policy_note"] == POLICY_NOTE
    for node in _walk(catalog):
        if "order_id" in node or "title" in node:
            assert node["sample_label"] == "SAMPLE"
            assert node["data_origin"] == "sample"
        if "guaranteed" in node:
            assert node["guaranteed"] is False
        if "automated_submission" in node:
            assert node["automated_submission"] is False
        if "product_url" in node:
            assert node["product_url"] is None


def test_dashboard_totals_match_the_sample_orders():
    catalog = build_sample_catalog()
    dashboard = catalog["dashboard"]
    assert dashboard["products_monitored"] == 5
    assert dashboard["estimated_savings_cents"] == 3100
    assert dashboard["confirmed_refunds_cents"] == 1000
    assert dashboard["pending_refund_requests"] == 1
    warnings = [row["warning"] for row in dashboard["upcoming_return_deadlines"]]
    assert warnings == ["1 day", "3 days", "7 days"]
    assert [row["order_id"] for row in dashboard["recent_price_changes"][:2]] == [
        "SAMPLE-111-0000001",
        "SAMPLE-111-0000005",
    ]


def test_sample_refunds_are_not_promises():
    catalog = build_sample_catalog()
    refunds = {refund["order_id"]: refund for refund in catalog["refund_requests"]}
    pending = refunds["SAMPLE-111-0000001"]
    accepted = refunds["SAMPLE-111-0000005"]
    denied = refunds["SAMPLE-111-0000006"]
    assert pending["status"] == "pending"
    assert pending["submission_method"] is None
    assert "nothing has been sent" in pending["note"].lower()
    assert accepted["confirmed_refund_cents"] == 1000
    assert "no refund was requested or received" in accepted["note"].lower()
    assert denied["final_denial"] is True
    assert denied["confirmed_refund_cents"] == 0
    for refund in refunds.values():
        assert refund["submission_method"] in {None, "manual_user"}
        assert "not guaranteed" in refund["draft_message"]
        assert "refund is guaranteed" not in refund["draft_message"]
        assert refund["policy_note"] == POLICY_NOTE


def test_return_comparison_is_only_the_sample_skillet():
    catalog = build_sample_catalog()
    compared = [row for row in catalog["returns"] if row["repurchase"] is not None]
    assert len(compared) == 1
    skillet = compared[0]
    assert skillet["order_id"] == "SAMPLE-111-0000003"
    assert skillet["repurchase"]["net_savings_cents"] == 540
    assert skillet["repurchase"]["guaranteed"] is False
    assert "confirmation" in skillet["recommended_action"]
    book = next(row for row in catalog["returns"] if row["order_id"] == "SAMPLE-111-0000004")
    assert book["warning"] == "passed"
    assert "not eligible" in book["recommended_action"]


def test_draft_requires_a_price():
    with pytest.raises(ValueError):
        draft_price_adjustment_message(
            {
                "title": "[SAMPLE] Paperback cookbook",
                "asin": "SAMPLE0004",
                "purchased_at": "2026-09-01",
                "order_id": "SAMPLE-111-0000004",
                "unit_price_cents": 1899,
                "quantity": 1,
                "latest_price_cents": None,
                "line_difference_cents": None,
            }
        )


def test_order_ids_and_asins_are_unique_and_obviously_fake():
    catalog = build_sample_catalog()
    order_ids = [item["order_id"] for item in catalog["items"]]
    asins = [item["asin"] for item in catalog["items"]]
    assert len(order_ids) == len(set(order_ids)) == 6
    assert len(asins) == len(set(asins))
    assert all(order_id.startswith("SAMPLE-") for order_id in order_ids)
    assert all(asin.startswith("SAMPLE") for asin in asins)
    assert all(item["title"].startswith("[SAMPLE]") for item in catalog["items"])
