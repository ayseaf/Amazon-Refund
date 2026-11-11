from __future__ import annotations


def format_money(cents: int, currency: str = "USD") -> str:
    if currency != "USD":
        raise ValueError("Only USD formatting is implemented in Phase 1")
    sign = "-" if cents < 0 else ""
    amount = abs(cents)
    return f"{sign}${amount // 100}.{amount % 100:02d}"


def line_gap_cents(unit_price_cents: int, latest_price_cents: int | None, quantity: int) -> int | None:
    """Positive means the current unit price is lower than the purchase unit price."""
    if quantity < 1:
        raise ValueError("quantity must be positive")
    if unit_price_cents < 0:
        raise ValueError("unit price cannot be negative")
    if latest_price_cents is None:
        return None
    if latest_price_cents < 0:
        raise ValueError("latest price cannot be negative")
    return (unit_price_cents - latest_price_cents) * quantity


def estimate_return_repurchase(
    *,
    unit_price_cents: int,
    quantity: int,
    current_unit_cents: int,
    original_tax_cents: int,
    repurchase_tax_cents: int,
    return_shipping_cents: int = 0,
    restocking_fee_cents: int = 0,
    repurchase_shipping_cents: int = 0,
) -> dict:
    """Estimate a return-and-repurchase. Original outbound shipping is treated as sunk.

    net = (purchase unit - current unit) * quantity
          + (original tax - repurchase tax)
          - return shipping - restocking fee - repurchase shipping

    Assumes original tax is refunded and repurchase tax is charged again.
    The result is an estimate. It is never a guaranteed refund.
    """
    values = {
        "unit_price_cents": unit_price_cents,
        "quantity": quantity,
        "current_unit_cents": current_unit_cents,
        "original_tax_cents": original_tax_cents,
        "repurchase_tax_cents": repurchase_tax_cents,
        "return_shipping_cents": return_shipping_cents,
        "restocking_fee_cents": restocking_fee_cents,
        "repurchase_shipping_cents": repurchase_shipping_cents,
    }
    if quantity < 1:
        raise ValueError("quantity must be positive")
    for name, value in values.items():
        if name == "quantity":
            continue
        if value < 0:
            raise ValueError(f"{name} cannot be negative")
    price_delta = (unit_price_cents - current_unit_cents) * quantity
    tax_delta = original_tax_cents - repurchase_tax_cents
    costs = return_shipping_cents + restocking_fee_cents + repurchase_shipping_cents
    net = price_delta + tax_delta - costs
    return {
        "price_delta_cents": price_delta,
        "tax_delta_cents": tax_delta,
        "return_shipping_cents": return_shipping_cents,
        "restocking_fee_cents": restocking_fee_cents,
        "repurchase_shipping_cents": repurchase_shipping_cents,
        "net_savings_cents": net,
        "worth_considering": net > 0,
        "guaranteed": False,
        "formula": (
            "net = (purchase unit price - current unit price) × quantity "
            "+ (original tax - repurchase tax) "
            "- return shipping - restocking fee - repurchase shipping. "
            "Original outbound shipping is treated as sunk. "
            "This is an estimate, not a guaranteed refund, and nothing is submitted automatically."
        ),
    }
