from __future__ import annotations

import sqlite3

import pytest

from tracker.db import column_names, connect, table_names
from tracker.migrate import MigrationChecksumError, apply_migrations

EXPECTED_TABLES = {
    "profiles",
    "settings",
    "notification_preferences",
    "amazon_connections",
    "orders",
    "order_items",
    "price_observations",
    "price_check_runs",
    "savings_estimates",
    "refund_requests",
    "refund_events",
    "notifications",
    "secret_refs",
    "task_reservations",
    "audit_log",
    "schema_migrations",
    "amazon_session_meta",
    "amazon_scan_runs",
    "item_verdicts",
    "review_gaps",
}


def test_migrations_create_the_phase_one_schema(tmp_path):
    connection = connect(tmp_path / "fresh.sqlite")
    applied = apply_migrations(connection)
    assert applied == ["001", "002"]
    assert table_names(connection) == EXPECTED_TABLES


def test_migrations_are_idempotent(tmp_path):
    connection = connect(tmp_path / "fresh.sqlite")
    apply_migrations(connection)
    assert apply_migrations(connection) == []
    count = connection.execute("SELECT COUNT(*) AS n FROM schema_migrations").fetchone()["n"]
    assert count == 2


def test_changed_checksum_is_rejected(tmp_path):
    connection = connect(tmp_path / "fresh.sqlite")
    apply_migrations(connection)
    connection.execute("UPDATE schema_migrations SET checksum = 'deadbeef' WHERE version = '001'")
    connection.commit()
    with pytest.raises(MigrationChecksumError):
        apply_migrations(connection)


def test_schema_has_no_password_or_card_columns(tmp_path):
    connection = connect(tmp_path / "fresh.sqlite")
    apply_migrations(connection)
    forbidden = {"password", "amazon_password", "card_number", "cvv", "credit_card", "api_key"}
    found = set()
    for table in table_names(connection):
        found.update(column_names(connection, table))
    assert found.isdisjoint(forbidden)


def test_schema_sql_does_not_mention_passwords():
    from tracker.migrate import SCHEMA_DIR

    sql = (SCHEMA_DIR / "001_initial.sql").read_text(encoding="utf-8").lower()
    assert "password" not in sql
    assert "card_number" not in sql


def test_database_file_is_private(tmp_path):
    directory = tmp_path / "db"
    path = directory / "tracker.sqlite"
    connection = connect(path)
    connection.execute("CREATE TABLE IF NOT EXISTS probe (id INTEGER)")
    connection.commit()
    assert path.stat().st_mode & 0o777 == 0o600
    assert directory.stat().st_mode & 0o777 == 0o700
    connection.close()


def test_foreign_keys_reject_an_item_without_an_order(tmp_path):
    connection = connect(tmp_path / "fresh.sqlite")
    apply_migrations(connection)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO order_items (
                id, order_id, profile_id, title, quantity, unit_price_cents, created_at, updated_at
            ) VALUES ('item', 'missing-order', 'missing-profile', 'Thing', 1, 100, 't', 't')
            """
        )
