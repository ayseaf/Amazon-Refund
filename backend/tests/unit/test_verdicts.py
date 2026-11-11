from __future__ import annotations

from datetime import date

from tracker.verdicts import ItemFacts, decide

AS_OF = date(2026, 11, 11)


def _facts(**overrides) -> ItemFacts:
    base = dict(
        order_id="112-1000001-0000001",
        asin="B0LAMP0001",
        title="Redacted desk lamp",
        quantity=2,
        price_paid_cents=2400,
        current_price_cents=1900,
        purchased_on="2026-10-20",
        return_eligible=True,
        return_window_end="2026-12-04",
    )
    base.update(overrides)
    return ItemFacts(**base)


def test_open_return_window_with_a_lower_price_is_return_possible():
    verdict = decide(_facts(), as_of=AS_OF)
    assert verdict.verdict == "return_possible"
    assert verdict.label == "Return possible"
    assert verdict.not_guaranteed is True
    assert verdict.potential_savings_cents == 1000
    assert "2026-12-04" in verdict.rule
    assert verdict.evidence["price_paid_cents"] == 2400
    assert verdict.evidence["current_price_cents"] == 1900
    assert verdict.draft_kind == "return_steps"
    assert verdict.draft_text is not None
    assert "not guaranteed" in verdict.policy_text.lower()
    assert "this app does not start the return" in verdict.draft_text.lower()
    assert "112-1000001-0000001" in verdict.draft_text
    assert "$19.00" in verdict.draft_text or "1900" in verdict.evidence.__repr__()


def test_open_window_without_a_lower_price_does_not_invent_savings():
    verdict = decide(_facts(current_price_cents=2500, quantity=1), as_of=AS_OF)
    assert verdict.verdict == "return_possible"
    assert verdict.potential_savings_cents is None
    assert "not lower" in verdict.savings_note.lower()


def test_price_drop_outside_a_return_is_a_manual_request_and_not_guaranteed():
    verdict = decide(
        _facts(
            order_id="112-1000002-0000002",
            asin="B0MUG00001",
            title="Redacted ceramic mug",
            quantity=1,
            price_paid_cents=1500,
            current_price_cents=1200,
            return_eligible=False,
            return_window_end=None,
        ),
        as_of=AS_OF,
    )
    assert verdict.verdict == "price_adjustment_ask_support"
    assert verdict.label == "Price adjustment: ask support"
    assert verdict.not_guaranteed is True
    assert "not guaranteed" in verdict.policy_text.lower()
    assert "automatic" in verdict.policy_text.lower()
    assert verdict.policy_url.startswith("https://www.amazon.com/")
    assert verdict.draft_kind == "price_adjustment_message"
    assert verdict.draft_text is not None
    lowered = verdict.draft_text.lower()
    assert "not guaranteed" in lowered
    assert "112-1000002-0000002" in verdict.draft_text
    assert "i have submitted" not in lowered
    assert "refund is approved" not in lowered
    assert verdict.potential_savings_cents == 300


def test_closed_window_and_no_price_drop_is_not_eligible():
    verdict = decide(
        _facts(
            price_paid_cents=1000,
            current_price_cents=1000,
            quantity=1,
            return_eligible=True,
            return_window_end="2026-10-01",
        ),
        as_of=AS_OF,
    )
    assert verdict.verdict == "not_eligible"
    assert verdict.label == "Not eligible"
    assert "outside" in verdict.rule.lower() or "window" in verdict.rule.lower()
    assert "no price drop" in verdict.rule.lower()
    assert verdict.draft_text is None
    assert verdict.potential_savings_cents is None


def test_non_returnable_without_a_price_drop_is_not_eligible():
    verdict = decide(
        _facts(
            price_paid_cents=1000,
            current_price_cents=1100,
            quantity=1,
            return_eligible=False,
            return_window_end=None,
        ),
        as_of=AS_OF,
    )
    assert verdict.verdict == "not_eligible"
    assert "non-returnable" in verdict.rule.lower() or "not returnable" in verdict.rule.lower()


def test_a_price_drop_after_the_window_asks_support_instead_of_a_return():
    verdict = decide(
        _facts(
            price_paid_cents=1000,
            current_price_cents=800,
            quantity=1,
            return_eligible=True,
            return_window_end="2026-10-01",
        ),
        as_of=AS_OF,
    )
    assert verdict.verdict == "price_adjustment_ask_support"
    assert verdict.potential_savings_cents == 200
    assert verdict.not_guaranteed is True


def test_missing_prices_and_return_facts_are_unknown():
    verdict = decide(
        _facts(
            quantity=None,
            price_paid_cents=None,
            current_price_cents=None,
            return_eligible=None,
            return_window_end=None,
            asin=None,
        ),
        as_of=AS_OF,
    )
    assert verdict.verdict == "unknown"
    assert verdict.label == "Unknown"
    missing = " ".join(verdict.missing).lower()
    assert "price paid" in missing
    assert "current price" in missing
    assert "return" in missing
    assert verdict.draft_text is None
    assert verdict.potential_savings_cents is None


def test_a_verdict_cannot_be_marked_guaranteed():
    verdict = decide(_facts(), as_of=AS_OF)
    assert verdict.not_guaranteed is True
    assert verdict.evidence.get("guaranteed") is False
