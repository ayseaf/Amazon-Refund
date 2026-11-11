from __future__ import annotations

import uuid

import pytest

from tests.factories import insert_item, insert_order
from tracker.services import (
    SettingsValidationError,
    forget_secret_ref,
    get_settings,
    purge_purchase_data,
    remember_secret_ref,
    update_settings,
    write_audit,
)
from tracker.timeutil import utc_now


def test_defaults_and_interval_bounds(migrated_conn):
    settings = get_settings(migrated_conn)
    assert settings["monitoring_interval_minutes"] == 60
    assert settings["min_savings_cents"] == 500
    assert settings["desktop_notifications"] is True
    assert settings["email_notifications"] is False
    assert settings["email_available"] is False
    assert settings["phase"] == 2

    updated = update_settings(
        migrated_conn,
        {"monitoring_interval_minutes": 120, "min_savings_cents": 2500, "desktop_notifications": False},
    )
    assert updated["monitoring_interval_minutes"] == 120
    assert updated["min_savings_cents"] == 2500
    assert updated["desktop_notifications"] is False


def test_sub_hour_interval_is_rejected(migrated_conn):
    with pytest.raises(SettingsValidationError) as caught:
        update_settings(migrated_conn, {"monitoring_interval_minutes": 30})
    assert caught.value.code == "invalid_interval"
    assert get_settings(migrated_conn)["monitoring_interval_minutes"] == 60


def test_email_channel_cannot_be_enabled(migrated_conn):
    with pytest.raises(SettingsValidationError) as caught:
        update_settings(migrated_conn, {"email_notifications": True})
    assert caught.value.code == "channel_not_available"


def test_passwords_cannot_be_saved_as_settings(migrated_conn):
    with pytest.raises(SettingsValidationError) as caught:
        update_settings(migrated_conn, {"amazon_password": "nope"})
    assert caught.value.code == "secret_not_allowed"


def test_audit_log_rejects_secrets(migrated_conn):
    with pytest.raises(ValueError):
        write_audit(migrated_conn, profile_id="local", action="bad", detail="api_key=supersecret")
    count = migrated_conn.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"]
    assert count == 0


def test_purge_removes_purchase_rows_and_keeps_the_profile(migrated_conn):
    order_id = insert_order(migrated_conn, amazon_order_id="REAL-LOOKING-ORDER")
    item_id = insert_item(migrated_conn, order_id)
    now = utc_now()
    migrated_conn.execute(
        """
        INSERT INTO amazon_connections (
            id, profile_id, marketplace, method, status, created_at, updated_at
        ) VALUES ('conn', 'local', 'amazon.com', 'order_export', 'disconnected', ?, ?)
        """,
        (now, now),
    )
    migrated_conn.execute(
        """
        INSERT INTO price_observations (
            id, order_item_id, profile_id, observed_at, source, price_cents
        ) VALUES (?, ?, 'local', ?, 'manual', 900)
        """,
        (str(uuid.uuid4()), item_id, now),
    )
    refund_id = str(uuid.uuid4())
    migrated_conn.execute(
        """
        INSERT INTO refund_requests (
            id, profile_id, order_item_id, status, created_at, updated_at, submission_method
        ) VALUES (?, 'local', ?, 'draft', ?, ?, 'manual_user')
        """,
        (refund_id, item_id, now, now),
    )
    migrated_conn.execute(
        """
        INSERT INTO refund_events (id, refund_request_id, profile_id, occurred_at, event_type, note)
        VALUES (?, ?, 'local', ?, 'drafted', 'local note')
        """,
        (str(uuid.uuid4()), refund_id, now),
    )
    migrated_conn.execute(
        """
        INSERT INTO notifications (id, profile_id, dedupe_key, kind, title, body, created_at)
        VALUES ('n1', 'local', 'deadline:1', 'return_deadline', 'Deadline', 'Soon', ?)
        """,
        (now,),
    )
    write_audit(
        migrated_conn,
        profile_id="local",
        action="imported",
        entity_type="order",
        entity_id=order_id,
        detail="imported one order",
    )
    remember_secret_ref(migrated_conn, "keepa_api_key", "encrypted_file")
    migrated_conn.commit()

    counts = purge_purchase_data(migrated_conn)
    assert counts["orders"] == 1
    assert counts["order_items"] == 1
    assert migrated_conn.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"] == 0
    assert migrated_conn.execute("SELECT COUNT(*) AS n FROM price_observations").fetchone()["n"] == 0
    assert migrated_conn.execute("SELECT COUNT(*) AS n FROM refund_requests").fetchone()["n"] == 0
    assert migrated_conn.execute("SELECT COUNT(*) AS n FROM profiles").fetchone()["n"] == 1
    assert migrated_conn.execute("SELECT COUNT(*) AS n FROM secret_refs").fetchone()["n"] == 1
    assert get_settings(migrated_conn)["monitoring_interval_minutes"] == 60
    audits = migrated_conn.execute("SELECT action, detail, entity_id FROM audit_log").fetchall()
    assert [row["action"] for row in audits] == ["purchase_data_purged"]
    assert order_id not in (audits[0]["detail"] or "")
    assert audits[0]["entity_id"] is None
    forget_secret_ref(migrated_conn, "keepa_api_key")
    assert migrated_conn.execute("SELECT COUNT(*) AS n FROM secret_refs").fetchone()["n"] == 0
