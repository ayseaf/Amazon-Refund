"""Phase 1 behavior: local storage, labeled samples, and no Amazon contact."""

from __future__ import annotations

import logging
import socket
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apt.config import AppConfig, assert_loopback
from apt.db import connect
from apt.domain import (
    comparable_savings,
    deadline_window,
    decide_run,
    difference_label,
    redact,
    repurchase_estimate,
    stamp_form,
    stamp_word,
)
from apt.main import create_app
from apt.secrets import KeychainSecretStore


@pytest.fixture
def client(tmp_path: Path):
    app = create_app(AppConfig(data_dir=tmp_path / "data"))
    with TestClient(app) as test_client:
        yield test_client


def _items(client: TestClient) -> dict[str, dict]:
    body = client.get("/api/orders").json()
    return {item["asin"]: item for item in body["items"]}


def test_health_does_not_claim_an_amazon_connection(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
    assert body["amazon_connected"] is False
    assert body["keepa_called"] is False


def test_empty_dashboard_has_zero_money_and_a_guarantee_disclaimer(client: TestClient):
    body = client.get("/api/dashboard").json()
    assert body["monitored_count"] == 0
    assert body["estimated_savings_cents"] == 0
    assert body["confirmed_refunds_cents"] == 0
    assert body["pending_refund_requests"] == 0
    assert body["upcoming_return_deadlines"] == []
    assert body["recent_price_changes"] == []
    assert body["last_successful_sync"] is None
    assert body["data_mode"] == "empty"
    assert "guarantee" in body["disclaimer"].lower()


def test_schema_covers_future_records_without_card_data(client: TestClient):
    connection = connect(client.app.state.config.database_path)
    names = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert {
        "users",
        "settings",
        "orders",
        "order_items",
        "price_snapshots",
        "price_alerts",
        "refund_requests",
        "notifications",
        "sync_runs",
        "audit_events",
    } <= names
    columns = " ".join(
        row[1]
        for row in connection.execute("PRAGMA table_info(order_items)")
    )
    assert "card" not in columns
    connection.close()


def test_sample_orders_are_labeled_and_do_not_invent_prices(client: TestClient):
    created = client.post("/api/sample-data")
    assert created.status_code == 200
    assert created.json()["amazon_contacted"] is False
    assert created.json()["orders"] == 6
    assert client.post("/api/sample-data").status_code == 409

    items = _items(client)
    assert len(items) == 6
    assert all(item["is_sample"] for item in items.values())
    assert all(item["title"].startswith("Sample:") for item in items.values())
    assert all("amazon.com" not in item["product_url"] for item in items.values())
    assert all(item["difference_label"] == "Not checked" for item in items.values())
    assert all(item["stamp_form"] == "dashed" for item in items.values())

    dashboard = client.get("/api/dashboard").json()
    assert dashboard["data_mode"] == "sample"
    assert dashboard["estimated_savings_cents"] == 0
    assert dashboard["confirmed_refunds_cents"] == 0
    assert dashboard["last_successful_sync"]["source"] == "sample"
    assert dashboard["last_successful_sync"]["amazon_contacted"] is False
    assert {item["window"] for item in dashboard["upcoming_return_deadlines"]} == {
        "1",
        "3",
        "7",
    }


def test_price_check_uses_only_the_sample_source_and_dedupes(client: TestClient, monkeypatch):
    def refuse_network(*_args, **_kwargs):
        raise AssertionError("Phase 1 tried to open a network connection")

    monkeypatch.setattr(socket, "create_connection", refuse_network)
    monkeypatch.setattr(socket.socket, "connect", refuse_network)

    client.post("/api/sample-data")
    checked = client.post("/api/price-checks")
    assert checked.status_code == 200
    body = checked.json()
    assert body["network_requests"] == 0
    assert body["keepa_called"] is False
    assert {row["source"] for row in body["results"]} == {"sample"}

    items = _items(client)
    assert items["SAMPLED01"]["savings_cents"] == 1260
    assert items["SAMPLED01"]["stamp_word"] == "Lower"
    assert items["SAMPLED01"]["stamp_form"] == "double"
    assert items["SAMPLED01"]["difference_label"] == "Lower by $12.60"
    assert items["SAMPLED02"]["stamp_word"] == "Other offer"
    assert items["SAMPLED02"]["savings_cents"] is None
    assert items["SAMPLED02"]["difference_label"].startswith("Seller differs")
    assert items["SAMPLED03"]["difference_label"].startswith("Condition differs")
    assert items["SAMPLED04"]["savings_cents"] == 1500
    assert items["SAMPLED04"]["return_eligible"] is False
    assert items["SAMPLED05"]["difference_label"] == "Higher by $3.20"
    assert items["SAMPLED05"]["stamp_form"] == "solid"
    assert items["SAMPLED06"]["savings_cents"] == 990

    dashboard = client.get("/api/dashboard").json()
    assert dashboard["estimated_savings_cents"] == 3750
    assert dashboard["confirmed_refunds_cents"] == 0
    assert len(dashboard["recent_price_changes"]) == 6

    notes = client.get("/api/notifications").json()["notifications"]
    assert len(notes) == 3
    assert all(note["delivered_to_macos"] is False for note in notes)

    client.post("/api/price-checks")
    assert len(client.get("/api/notifications").json()["notifications"]) == 3
    assert client.get("/api/dashboard").json()["estimated_savings_cents"] == 3750


def test_threshold_and_opt_out_control_notifications_only(client: TestClient):
    client.put("/api/settings", json={"notify_min_savings_cents": 2000})
    client.post("/api/sample-data")
    client.post("/api/price-checks")
    assert client.get("/api/notifications").json()["notifications"] == []
    assert client.get("/api/dashboard").json()["estimated_savings_cents"] == 3750

    cleared = client.delete("/api/sample-data")
    assert cleared.status_code == 200
    client.put(
        "/api/settings",
        json={"notify_min_savings_cents": 500, "notify_price_decreases": False},
    )
    client.post("/api/sample-data")
    client.post("/api/price-checks")
    assert client.get("/api/notifications").json()["notifications"] == []
    assert client.get("/api/dashboard").json()["estimated_savings_cents"] == 3750


def test_real_rows_are_not_priced_from_the_sample_catalog(client: TestClient):
    client.post("/api/sample-data")
    connection = connect(client.app.state.config.database_path)
    cursor = connection.execute(
        """
        INSERT INTO orders (
          user_id, amazon_order_id, purchased_on, currency, shipping_cents,
          tax_cents, source, is_sample, created_at
        ) VALUES ('local', 'CSV-1', '2026-01-01', 'USD', 0, 0, 'csv', 0, '2026-01-01T00:00:00+00:00')
        """
    )
    connection.execute(
        """
        INSERT INTO order_items (
          order_id, asin, title, product_url, quantity, unit_price_cents,
          item_shipping_cents, item_tax_cents, seller, condition, variation_note,
          return_eligible, return_deadline, monitoring_status
        ) VALUES (?, 'B00TEST000', 'Imported kettle', 'https://example.invalid/real',
          1, 1000, 0, 0, 'Example Seller', 'New', '', 1, '2026-02-01', 'unconfigured')
        """,
        (cursor.lastrowid,),
    )
    connection.commit()
    connection.close()

    body = client.post("/api/price-checks").json()
    skipped = next(row for row in body["results"] if row["asin"] == "B00TEST000")
    assert skipped["status"] == "skipped"
    assert skipped["source"] is None
    assert "not configured" in skipped["reason"].lower()
    assert _items(client)["B00TEST000"]["difference_label"] == "Not checked"
    assert body["keepa_called"] is False


def test_other_users_orders_stay_hidden(client: TestClient):
    client.post("/api/sample-data")
    connection = connect(client.app.state.config.database_path)
    connection.execute(
        "INSERT INTO users (id, display_name, created_at) VALUES ('other', 'Other', '2026-01-01T00:00:00+00:00')"
    )
    order_id = connection.execute(
        """
        INSERT INTO orders (
          user_id, amazon_order_id, purchased_on, currency, shipping_cents,
          tax_cents, source, is_sample, created_at
        ) VALUES ('other', 'OTHER-1', '2026-01-02', 'USD', 0, 0, 'csv', 0, '2026-01-02T00:00:00+00:00')
        """
    ).lastrowid
    connection.execute(
        """
        INSERT INTO order_items (
          order_id, asin, title, product_url, quantity, unit_price_cents,
          item_shipping_cents, item_tax_cents, seller, condition, variation_note,
          return_eligible, return_deadline, monitoring_status
        ) VALUES (?, 'OTHERASIN1', 'Other person kettle', 'https://example.invalid/other',
          1, 1000, 0, 0, 'Other', 'New', '', 1, '2026-02-01', 'unconfigured')
        """,
        (order_id,),
    )
    connection.commit()
    connection.close()
    orders = client.get("/api/orders").json()
    assert all(item["amazon_order_id"] != "OTHER-1" for item in orders["items"])
    assert all(item["title"] != "Other person kettle" for item in orders["items"])
    assert orders["items"]


def test_refunds_are_not_invented_from_a_price_drop(client: TestClient):
    client.post("/api/sample-data")
    client.post("/api/price-checks")
    body = client.get("/api/refunds").json()
    assert body["requests"] == []
    assert body["confirmed_refunds_cents"] == 0
    assert "guarantee" in body["policy"].lower()
    assert "will not submit" in body["policy"].lower()


def test_returns_estimate_is_read_only_math(client: TestClient):
    client.post("/api/sample-data")
    client.post("/api/price-checks")
    body = client.get("/api/returns").json()
    assert body["submission_available"] is False
    by_asin = {row["asin"]: row for row in body["items"]}
    assert by_asin["SAMPLED01"]["repurchase_estimate_cents"] == 1260
    assert by_asin["SAMPLED04"]["repurchase_estimate_cents"] is None
    assert by_asin["SAMPLED02"]["repurchase_estimate_cents"] is None
    assert by_asin["SAMPLED05"]["repurchase_estimate_cents"] == -320
    assert "nothing is submitted" in body["formula"].lower()


def test_settings_reject_too_frequent_checks_and_unbuilt_channels(client: TestClient):
    assert client.put("/api/settings", json={"monitoring_interval_minutes": 30}).status_code == 400
    saved = client.put("/api/settings", json={"monitoring_interval_minutes": 120, "notify_min_savings_cents": 800})
    assert saved.status_code == 200
    assert saved.json()["monitoring_interval_minutes"] == 120
    assert client.get("/api/settings").json()["notify_min_savings_cents"] == 800
    email = client.put("/api/settings", json={"email_notifications": True})
    assert email.status_code == 400
    assert client.get("/api/monitoring").json()["scheduler_installed"] is False


def test_secrets_are_encrypted_and_passwords_are_refused(client: TestClient):
    secret = "super-secret-keepa-value"
    refused = client.put("/api/secrets/amazon_password", json={"value": "hunter2"})
    assert refused.status_code == 400
    assert "password" in refused.json()["detail"].lower()

    stored = client.put("/api/secrets/keepa_api_key", json={"value": secret})
    assert stored.status_code == 200
    assert secret not in stored.text
    listing = client.get("/api/secrets")
    assert secret not in listing.text
    assert listing.json()["secrets"] == [{"name": "keepa_api_key", "stored": True}]

    data_dir = client.app.state.config.data_dir
    raw = b"".join(path.read_bytes() for path in data_dir.rglob("*") if path.is_file())
    assert secret.encode() not in raw
    secret_files = [
        path
        for path in data_dir.rglob("*")
        if path.is_file() and path.name.startswith("secrets")
    ]
    assert secret_files
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in secret_files)

    checked = client.post("/api/price-checks")
    assert checked.json()["keepa_called"] is False
    assert secret.encode() not in (data_dir / "logs" / "app.log").read_bytes()


def test_purge_requires_the_exact_phrase_and_keeps_the_key(client: TestClient):
    client.post("/api/sample-data")
    client.post("/api/price-checks")
    client.put("/api/secrets/keepa_api_key", json={"value": "kept-key-value"})
    assert client.request("DELETE", "/api/purchase-data", json={"confirmation": "delete"}).status_code == 400
    removed = client.request(
        "DELETE",
        "/api/purchase-data",
        json={"confirmation": "DELETE PURCHASE DATA"},
    )
    assert removed.status_code == 200
    assert client.get("/api/orders").json()["items"] == []
    assert client.get("/api/dashboard").json()["data_mode"] == "empty"
    assert client.get("/api/notifications").json()["notifications"] == []
    assert client.get("/api/secrets").json()["secrets"][0]["stored"] is True
    log = (client.app.state.config.data_dir / "logs" / "app.log").read_text()
    assert "Enamel kettle" not in log
    assert "kept-key-value" not in log


def test_sample_delete_leaves_a_non_sample_row(client: TestClient):
    client.post("/api/sample-data")
    connection = connect(client.app.state.config.database_path)
    connection.execute(
        """
        INSERT INTO orders (
          user_id, amazon_order_id, purchased_on, currency, shipping_cents,
          tax_cents, source, is_sample, created_at
        ) VALUES ('local', 'CSV-9', '2026-03-01', 'USD', 0, 0, 'csv', 0, '2026-03-01T00:00:00+00:00')
        """
    )
    connection.commit()
    connection.close()
    assert client.delete("/api/sample-data").status_code == 200
    listed = client.get("/api/orders").json()["items"]
    assert [item["amazon_order_id"] for item in listed] == []
    orders = connect(client.app.state.config.database_path)
    remaining = [
        tuple(row)
        for row in orders.execute("SELECT amazon_order_id, is_sample FROM orders").fetchall()
    ]
    orders.close()
    assert remaining == [("CSV-9", 0)]


def test_loopback_bind_and_remote_client_are_refused():
    assert assert_loopback("127.0.0.1") == "127.0.0.1"
    with pytest.raises(ValueError):
        assert_loopback("0.0.0.0")


def test_remote_client_is_rejected(client: TestClient):
    from apt.api import client_allowed

    assert client_allowed("127.0.0.1") is True
    assert client_allowed("testclient") is True
    assert client_allowed("8.8.8.8") is False


def test_savings_math_includes_quantity_shipping_tax_and_coupon():
    savings = comparable_savings(
        quantity=2,
        unit_price_cents=1249,
        purchase_shipping_cents=399,
        purchase_tax_cents=200,
        current_unit_cents=1399,
        current_shipping_cents=399,
        current_tax_cents=220,
        current_coupon_cents=0,
    )
    assert savings == -320
    assert repurchase_estimate(savings, eligible=True, comparable=True, restocking_cents=150, return_shipping_cents=50) == -520
    assert repurchase_estimate(savings, eligible=False, comparable=True, restocking_cents=0, return_shipping_cents=0) is None
    assert repurchase_estimate(100, eligible=True, comparable=False, restocking_cents=0, return_shipping_cents=0) is None


def test_labels_deadlines_and_scheduler_decisions():
    assert difference_label(False, True, 100, "unused") == "Not checked"
    assert difference_label(True, False, None, "Seller differs from the purchase.") == "Seller differs from the purchase."
    assert difference_label(True, True, 0, "") == "Unchanged"
    assert stamp_word(False, True, None) == "Not checked"
    assert stamp_word(True, False, None) == "Other offer"
    assert stamp_form(False, True, None, 500) == "dashed"
    assert stamp_form(True, True, 500, 500) == "double"
    assert stamp_form(True, True, 100, 500) == "solid"
    today = date(2026, 11, 11)
    assert deadline_window(date(2026, 11, 12), today) == "1"
    assert deadline_window(date(2026, 11, 14), today) == "3"
    assert deadline_window(date(2026, 11, 18), today) == "7"
    assert deadline_window(date(2026, 12, 1), today) is None
    assert deadline_window(date(2026, 11, 10), today) == "past"

    now = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
    assert decide_run(now, None, timedelta(hours=1), False).start is True
    assert decide_run(now, now - timedelta(minutes=30), timedelta(hours=1), False).start is False
    assert decide_run(now, now - timedelta(hours=2), timedelta(hours=1), True).start is False
    assert decide_run(now, now - timedelta(hours=2), timedelta(hours=1), False).start is True


def test_redaction_and_keychain_command_shape():
    assert "abc123secret" not in redact("provider api_key=abc123secret trailing")
    cleaned = redact("Authorization: Bearer abc.def")
    assert "abc.def" not in cleaned
    command = KeychainSecretStore()._add_command("keepa_api_key", "hidden-value")
    assert command[0] == "security"
    assert isinstance(command, list)
    assert "hidden-value" in command


def test_log_line_is_redacted(tmp_path: Path, caplog):
    app = create_app(AppConfig(data_dir=tmp_path / "logged"))
    with caplog.at_level(logging.INFO, logger="apt"):
        logging.getLogger("apt").info("api_key=%s", "should-not-survive")
    log_text = (tmp_path / "logged" / "logs" / "app.log").read_text()
    assert "should-not-survive" not in log_text
    assert "redacted" in log_text
    with TestClient(app) as test_client:
        assert test_client.get("/api/health").status_code == 200
