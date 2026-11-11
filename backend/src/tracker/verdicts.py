from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from tracker.money import format_money

POLICY_TEXT = (
    "Amazon does not generally offer automatic price protection after purchase. "
    "A price adjustment or refund is not guaranteed. This app does not submit a request."
)
POLICY_URL = "https://www.amazon.com/gp/help/customer/display.html"

LABELS = {
    "return_possible": "Return possible",
    "price_adjustment_ask_support": "Price adjustment: ask support",
    "not_eligible": "Not eligible",
    "unknown": "Unknown",
}


@dataclass(frozen=True)
class ItemFacts:
    order_id: str
    asin: str | None
    title: str | None
    quantity: int | None
    price_paid_cents: int | None
    current_price_cents: int | None
    purchased_on: str | None
    return_eligible: bool | None
    return_window_end: str | None


@dataclass(frozen=True)
class Verdict:
    verdict: str
    label: str
    rule: str
    missing: tuple[str, ...]
    evidence: dict
    policy_text: str
    policy_url: str
    potential_savings_cents: int | None
    savings_note: str
    not_guaranteed: bool
    draft_kind: str | None
    draft_text: str | None


def _missing(facts: ItemFacts) -> list[str]:
    missing: list[str] = []
    if facts.price_paid_cents is None:
        missing.append("price paid")
    if facts.current_price_cents is None:
        missing.append("current price")
    if facts.return_eligible is None:
        missing.append("whether the item is returnable")
    if facts.return_window_end is None:
        missing.append("return window end date")
    if facts.quantity is None:
        missing.append("quantity")
    return missing


def _evidence(facts: ItemFacts, as_of: date) -> dict:
    return {
        "order_id": facts.order_id,
        "asin": facts.asin,
        "title": facts.title,
        "purchased_on": facts.purchased_on,
        "price_paid_cents": facts.price_paid_cents,
        "current_price_cents": facts.current_price_cents,
        "quantity": facts.quantity,
        "return_eligible": facts.return_eligible,
        "return_window_end": facts.return_window_end,
        "as_of": as_of.isoformat(),
        "guaranteed": False,
        "policy_text": POLICY_TEXT,
        "policy_url": POLICY_URL,
    }


def _build(
    kind: str,
    rule: str,
    missing: tuple[str, ...],
    evidence: dict,
    savings: int | None,
    note: str,
    draft_kind: str | None,
    draft_text: str | None,
) -> Verdict:
    return Verdict(
        verdict=kind,
        label=LABELS[kind],
        rule=rule,
        missing=missing,
        evidence=evidence,
        policy_text=POLICY_TEXT,
        policy_url=POLICY_URL,
        potential_savings_cents=savings,
        savings_note=note,
        not_guaranteed=True,
        draft_kind=draft_kind,
        draft_text=draft_text,
    )


def _return_steps(facts: ItemFacts, savings: int | None, note: str) -> str:
    price_line = ""
    if facts.price_paid_cents is not None and facts.current_price_cents is not None:
        price_line = (
            f"Price paid {format_money(facts.price_paid_cents)}. "
            f"Current public price {format_money(facts.current_price_cents)}.\n"
        )
    saving_line = note
    if savings is not None:
        saving_line = f"The item-price difference is {format_money(savings)}. {note}"
    deadline = f" that ends {facts.return_window_end}" if facts.return_window_end else ""
    return (
        "These steps are for you to do on Amazon. This app does not start the return.\n\n"
        f"1. Open order {facts.order_id} on amazon.com.\n"
        f"2. Check that {facts.title or 'the item'} is still inside the return window{deadline}.\n"
        "3. If you still want to return it, start the return yourself and choose the options Amazon shows.\n"
        "4. If you want to buy it again, place that order yourself after you review shipping and tax.\n\n"
        f"{price_line}{saving_line}\n\n"
        "A refund is not guaranteed. Amazon does not generally offer automatic price protection.\n"
    )


def _adjustment_message(facts: ItemFacts, savings: int) -> str:
    return (
        "Hello,\n\n"
        f"I bought {facts.title or 'an item'} (ASIN {facts.asin or 'not shown'}) "
        f"on {facts.purchased_on or 'the date shown on the order'} "
        f"in order {facts.order_id} for {format_money(facts.price_paid_cents or 0)} each, "
        f"quantity {facts.quantity}.\n\n"
        f"The public price I can see now is {format_money(facts.current_price_cents or 0)} each, "
        f"which is {format_money(savings)} less for this quantity before fees that were not shown.\n\n"
        "I am asking whether a price adjustment or partial refund is available. "
        "I understand Amazon does not generally offer automatic price protection, "
        "and that a refund is not guaranteed.\n\n"
        "I will send this myself after I review it. Nothing has been submitted.\n\n"
        "Thank you.\n"
    )


def decide(facts: ItemFacts, *, as_of: date) -> Verdict:
    missing = _missing(facts)
    evidence = _evidence(facts, as_of)
    window_end = date.fromisoformat(facts.return_window_end) if facts.return_window_end else None
    inside = facts.return_eligible is True and window_end is not None and as_of <= window_end
    outside = window_end is not None and as_of > window_end
    prices_known = (
        facts.price_paid_cents is not None
        and facts.current_price_cents is not None
        and facts.quantity is not None
    )
    price_drop = bool(
        prices_known
        and facts.current_price_cents is not None
        and facts.price_paid_cents is not None
        and facts.quantity is not None
        and facts.current_price_cents < facts.price_paid_cents
    )
    savings = None
    if price_drop and facts.price_paid_cents is not None and facts.current_price_cents is not None and facts.quantity:
        savings = (facts.price_paid_cents - facts.current_price_cents) * facts.quantity

    if inside:
        if price_drop and savings is not None:
            note = (
                "Potential saving if you return it and buy it again is the unit price difference times quantity. "
                "Return shipping, restocking fees, and a change in tax were not shown, so they are not included. "
                "A refund is not guaranteed, and this app does not start the return."
            )
        elif prices_known:
            note = "The current price is not lower, so returning it to buy it again would not save money on the item price."
            savings = None
        else:
            note = (
                "The return window is still open. The current price or the price paid was not shown, "
                "so a repurchase saving was not calculated."
            )
        return _build(
            "return_possible",
            (
                "The order shows this item is returnable and "
                f"{as_of.isoformat()} is on or before the return window end {facts.return_window_end}."
            ),
            tuple(missing),
            evidence,
            savings,
            note,
            "return_steps",
            _return_steps(facts, savings, note),
        )

    if price_drop and savings is not None:
        note = (
            "This is the unit price difference times quantity. "
            "Amazon does not generally offer automatic price protection. A manual request is not guaranteed."
        )
        return _build(
            "price_adjustment_ask_support",
            (
                "The current unit price is lower than the price paid, and the item is not inside a return window "
                "shown on the order. A manual customer-service request might be worth asking about. It is not guaranteed."
            ),
            tuple(missing),
            evidence,
            savings,
            note,
            "price_adjustment_message",
            _adjustment_message(facts, savings),
        )

    if prices_known and facts.current_price_cents is not None and facts.price_paid_cents is not None:
        if facts.current_price_cents >= facts.price_paid_cents or outside or facts.return_eligible is False:
            reasons: list[str] = []
            if outside:
                reasons.append("outside the return window")
            if facts.return_eligible is False:
                reasons.append("not returnable")
            if facts.current_price_cents >= facts.price_paid_cents:
                reasons.append("no price drop")
            return _build(
                "not_eligible",
                "Not eligible: " + " and ".join(reasons) + ".",
                (),
                evidence,
                None,
                "No savings estimate.",
                None,
                None,
            )

    return _build(
        "unknown",
        "A verdict needs data that was not shown: " + ", ".join(missing) + ".",
        tuple(missing),
        evidence,
        None,
        "No savings estimate.",
        None,
        None,
    )
