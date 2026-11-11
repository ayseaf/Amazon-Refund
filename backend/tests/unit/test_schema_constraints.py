from __future__ import annotations

import sqlite3
import uuid

import pytest

from tests.factories import insert_item, insert_order
from tracker.timeutil import utc_now


def test_guaranteed_refund_flag_cannot_be_stored(migrated_conn):
    order_id = insert_order(migrated_conn)
    item_id = insert_item(migrated_conn, order_id)
    now = utc_now()
    with pytest.raises(sqlite3.IntegrityError):
        migrated_conn.execute(
            """
            INSERT INTO savings_estimates (
                id, order_item_id, profile_id, computed_at, purchase_price_cents,
                current_price_cents, estimated_savings_cents, fees_cents, confidence,
                explanation, is_guaranteed
            ) VALUES (?, ?, 'local', ?, 1000, 900, 100, 0, 'low', 'estimate', 1)
            """,
            (str(uuid.uuid4()), item_id, now),
        )


def test_automated_refund_submission_is_rejected(migrated_conn):
    order_id = insert_order(migrated_conn)
    item_id = insert_item(migrated_conn, order_id)
    now = utc_now()
    with pytest.raises(sqlite3.IntegrityError):
        migrated_conn.execute(
            """
            INSERT INTO refund_requests (
                id, profile_id, order_item_id, status, created_at, updated_at, submission_method
            ) VALUES (?, 'local', ?, 'draft', ?, ?, 'automated')
            """,
            (str(uuid.uuid4()), item_id, now, now),
        )


def test_zero_quantity_is_rejected(migrated_conn):
    order_id = insert_order(migrated_conn)
    now = utc_now()
    with pytest.raises(sqlite3.IntegrityError):
        migrated_conn.execute(
            """
            INSERT INTO order_items (
                id, order_id, profile_id, title, quantity, unit_price_cents, created_at, updated_at
            ) VALUES (?, ?, 'local', 'Thing', 0, 100, ?, ?)
            """,
            (str(uuid.uuid4()), order_id, now, now),
        )


def test_notification_dedupe_key_is_unique(migrated_conn):
    now = utc_now()
    migrated_conn.execute(
        """
        INSERT INTO notifications (id, profile_id, dedupe_key, kind, title, body, created_at, channel)
        VALUES ('n1', 'local', 'price-drop:item-1', 'price_decrease', 'Drop', 'Sample', ?, 'desktop')
        """,
        (now,),
    )
    migrated_conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        migrated_conn.execute(
            """
            INSERT INTO notifications (id, profile_id, dedupe_key, kind, title, body, created_at, channel)
            VALUES ('n2', 'local', 'price-drop:item-1', 'price_decrease', 'Drop', 'Sample', ?, 'desktop')
            """,
            (now,),
        )
