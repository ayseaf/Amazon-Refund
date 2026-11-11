from __future__ import annotations

import logging
from pathlib import Path

from tests.factories import insert_item, insert_order
from tracker.api import create_app
from tracker.config import Settings
from tracker.db import connect


def test_health_ready_and_info(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "amazon-price-tracker", "phase": 2}
    assert client.get("/health/live").json()["status"] == "live"
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["migrations"] == 2
    info = client.get("/api/v1/info").json()
    assert info["phase"] == 2
    assert info["sample_data_only"] is True
    assert info["amazon_connected"] is False
    assert info["accepts_amazon_password"] is False
    assert info["price_provider"] is None
    assert info["secret_store"] == "ready"
    assert info["scheduler"]["running"] is False
    stats = client.get("/api/v1/stats").json()
    assert stats == {
        "data_origin": "database",
        "stored_orders": 0,
        "stored_items": 0,
        "sample_rows_included": False,
    }
    assert client.get("/openapi.json").status_code == 200


def test_sample_catalog_is_separate_from_the_database(client):
    catalog = client.get("/api/v1/sample/catalog")
    assert catalog.status_code == 200
    body = catalog.json()
    assert body["data_origin"] == "sample"
    assert body["amazon_connected"] is False
    assert "SAMPLE" in body["disclaimer"]
    assert len(body["items"]) == 6
    assert client.get("/api/v1/stats").json()["stored_orders"] == 0


def test_price_check_does_not_invent_a_price(client, app_settings):
    response = client.post("/api/v1/price-checks")
    assert response.status_code == 409
    body = response.json()
    assert body["checked"] is False
    assert body["price_cents"] is None
    assert body["error"]["code"] == "provider_not_configured"
    assert "nothing was sent to Amazon" in body["error"]["message"]
    connection = connect(app_settings.db_path)
    try:
        observations = connection.execute("SELECT COUNT(*) AS n FROM price_observations").fetchone()["n"]
        runs = connection.execute(
            "SELECT status, error_code, source FROM price_check_runs"
        ).fetchall()
    finally:
        connection.close()
    assert observations == 0
    assert len(runs) == 1
    assert runs[0]["status"] == "skipped"
    assert runs[0]["error_code"] == "provider_not_configured"
    assert runs[0]["source"] == "none"


def test_settings_round_trip_and_secret_rejection(client):
    assert client.get("/api/v1/settings").json()["monitoring_interval_minutes"] == 60
    saved = client.put("/api/v1/settings", json={"monitoring_interval_minutes": 180, "notify_savings": False})
    assert saved.status_code == 200
    assert saved.json()["monitoring_interval_minutes"] == 180
    assert saved.json()["notify_savings"] is False
    rejected = client.put("/api/v1/settings", json={"amazon_password": "nope"})
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "secret_not_allowed"
    too_soon = client.put("/api/v1/settings", json={"monitoring_interval_minutes": 15})
    assert too_soon.status_code == 422
    email = client.put("/api/v1/settings", json={"telegram_notifications": True})
    assert email.status_code == 422
    assert email.json()["error"]["code"] == "channel_not_available"


def test_keepa_key_is_not_echoed_or_written_to_sqlite(client, app_settings, caplog):
    caplog.set_level(logging.INFO)
    logging.getLogger("tracker").propagate = True
    secret = "keepa-live-key-not-for-storage-9f3a"
    stored = client.put("/api/v1/secrets/keepa_api_key", json={"value": secret})
    assert stored.status_code == 204
    assert secret.encode() not in stored.content
    visible = client.get("/api/v1/secrets/keepa_api_key")
    assert visible.status_code == 200
    assert visible.json() == {"name": "keepa_api_key", "configured": True, "backend": "encrypted_file"}
    assert secret not in visible.text
    assert secret not in caplog.text
    blob = app_settings.db_path.read_bytes()
    for suffix in ("-wal", "-shm"):
        extra = Path(str(app_settings.db_path) + suffix)
        if extra.exists():
            blob += extra.read_bytes()
    assert secret.encode() not in blob
    assert secret.encode() not in app_settings.secret_file.read_bytes()
    removed = client.delete("/api/v1/secrets/keepa_api_key")
    assert removed.status_code == 204
    assert client.get("/api/v1/secrets/keepa_api_key").json()["configured"] is False


def test_amazon_password_secret_is_rejected(client):
    response = client.put("/api/v1/secrets/amazon_password", json={"value": "nope"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "secret_not_allowed"


def test_purchase_delete_requires_confirmation_and_clears_rows(client, app_settings):
    missing = client.delete("/api/v1/purchases")
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "confirmation_required"
    connection = connect(app_settings.db_path)
    try:
        order_id = insert_order(connection)
        insert_item(connection, order_id)
    finally:
        connection.close()
    assert client.get("/api/v1/stats").json()["stored_orders"] == 1
    deleted = client.delete("/api/v1/purchases", headers={"X-Confirm-Delete": "DELETE-PURCHASE-DATA"})
    assert deleted.status_code == 200
    assert deleted.json()["sample_data_affected"] is False
    assert deleted.json()["deleted"]["orders"] == 1
    assert client.get("/api/v1/stats").json()["stored_orders"] == 0
    assert client.get("/api/v1/sample/catalog").status_code == 200


def test_locked_secret_store_still_serves_health(tmp_path):
    from fastapi.testclient import TestClient

    settings = Settings(
        _env_file=None,
        db_path=tmp_path / "tracker.sqlite",
        secret_backend="encrypted_file",
        secret_key="",
        secret_file=tmp_path / "secrets.bin",
    )
    with TestClient(create_app(settings)) as test_client:
        assert test_client.get("/health/ready").status_code == 200
        info = test_client.get("/api/v1/info").json()
        assert info["secret_store"] == "locked"
        rejected = test_client.put("/api/v1/secrets/keepa_api_key", json={"value": "abc"})
        assert rejected.status_code == 503
        assert rejected.json()["error"]["code"] == "secret_store_locked"


def test_default_bind_host_is_loopback(monkeypatch):
    monkeypatch.delenv("TRACKER_HOST", raising=False)
    assert Settings(_env_file=None).host == "127.0.0.1"


def test_production_code_does_not_collect_a_password_or_submit_to_amazon():
    repo = Path(__file__).resolve().parents[3]
    source = []
    for path in (repo / "backend" / "src").rglob("*.py"):
        source.append(path.read_text(encoding="utf-8"))
    frontend = repo / "frontend" / "src"
    if frontend.exists():
        for path in frontend.rglob("*"):
            if path.suffix in {".ts", ".tsx", ".css"}:
                source.append(path.read_text(encoding="utf-8"))
    text = "\n".join(source)
    assert "AMAZON_PASSWORD" not in text
    assert "amazon_password" in text
    assert "ap_password" not in text
    assert ".fill(" not in text
    assert "https://www.amazon.com/gp/buy" not in text
    assert "https://www.amazon.com/checkout" not in text
    assert "https://www.amazon.com/your-orders/orders?timeFilter=last30" in text
