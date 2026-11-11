from __future__ import annotations

import pytest

from tracker.money import estimate_return_repurchase, format_money, line_gap_cents


def test_format_money_uses_cents():
    assert format_money(7999) == "$79.99"
    assert format_money(10) == "$0.10"
    assert format_money(-1500) == "-$15.00"


def test_line_gap_applies_quantity_and_missing_prices():
    assert line_gap_cents(1299, 999, 2) == 600
    assert line_gap_cents(1899, None, 1) is None
    with pytest.raises(ValueError):
        line_gap_cents(100, 90, 0)


def test_return_repurchase_estimate_is_never_guaranteed():
    estimate = estimate_return_repurchase(
        unit_price_cents=4499,
        quantity=1,
        current_unit_cents=3999,
        original_tax_cents=360,
        repurchase_tax_cents=320,
    )
    assert estimate["price_delta_cents"] == 500
    assert estimate["tax_delta_cents"] == 40
    assert estimate["net_savings_cents"] == 540
    assert estimate["worth_considering"] is True
    assert estimate["guaranteed"] is False


def test_restocking_fee_can_wipe_out_the_gap():
    estimate = estimate_return_repurchase(
        unit_price_cents=4499,
        quantity=1,
        current_unit_cents=3999,
        original_tax_cents=360,
        repurchase_tax_cents=360,
        restocking_fee_cents=800,
    )
    assert estimate["net_savings_cents"] == -300
    assert estimate["worth_considering"] is False
    assert estimate["guaranteed"] is False


def test_negative_costs_are_rejected():
    with pytest.raises(ValueError):
        estimate_return_repurchase(
            unit_price_cents=100,
            quantity=1,
            current_unit_cents=50,
            original_tax_cents=0,
            repurchase_tax_cents=-1,
        )
