from __future__ import annotations

import uuid

from tracker.timeutil import utc_now


def insert_order(connection, profile_id: str = "local", amazon_order_id: str = "TEST-ORDER-1") -> str:
    order_id = str(uuid.uuid4())
    now = utc_now()
    connection.execute(
        """
        INSERT INTO orders (
            id, profile_id, connection_id, amazon_order_id, purchased_at, order_status,
            currency, shipping_amount_cents, tax_amount_cents, order_total_cents,
            ship_to_region, source, imported_at
        ) VALUES (?, ?, NULL, ?, '2026-10-01', 'shipped', 'USD', 0, 0, 1000, 'CA', 'order_export', ?)
        """,
        (order_id, profile_id, amazon_order_id, now),
    )
    connection.commit()
    return order_id


def insert_item(connection, order_id: str, profile_id: str = "local", title: str = "Test item") -> str:
    item_id = str(uuid.uuid4())
    now = utc_now()
    connection.execute(
        """
        INSERT INTO order_items (
            id, order_id, profile_id, asin, title, product_url, seller_name, condition,
            quantity, unit_price_cents, item_shipping_cents, item_tax_cents, variation_json,
            return_eligible, return_deadline_at, monitoring_status, created_at, updated_at
        ) VALUES (
            ?, ?, ?, 'TESTASIN01', ?, NULL, 'Seller', 'New',
            1, 1000, 0, 0, NULL, 1, '2026-12-01', 'monitoring', ?, ?
        )
        """,
        (item_id, order_id, profile_id, title, now, now),
    )
    connection.commit()
    return item_id
