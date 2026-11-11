"""SQLite storage. Purchase rows are local. Secrets are not stored here."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from apt.config import LOCAL_USER_ID
from apt.domain import DEFAULT_SETTINGS, SAMPLE_ORDERS

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
  user_id TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (user_id, key),
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS sync_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  source TEXT NOT NULL,
  message TEXT NOT NULL,
  orders_seen INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  amazon_order_id TEXT NOT NULL,
  purchased_on TEXT NOT NULL,
  currency TEXT NOT NULL,
  shipping_cents INTEGER NOT NULL,
  tax_cents INTEGER NOT NULL,
  source TEXT NOT NULL,
  is_sample INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (user_id, amazon_order_id),
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS order_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL,
  asin TEXT NOT NULL,
  title TEXT NOT NULL,
  product_url TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  unit_price_cents INTEGER NOT NULL,
  item_shipping_cents INTEGER NOT NULL,
  item_tax_cents INTEGER NOT NULL,
  seller TEXT NOT NULL,
  condition TEXT NOT NULL,
  variation_note TEXT NOT NULL,
  return_eligible INTEGER NOT NULL,
  return_deadline TEXT,
  monitoring_status TEXT NOT NULL,
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS price_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_item_id INTEGER NOT NULL,
  checked_at TEXT NOT NULL,
  source TEXT NOT NULL,
  comparable INTEGER NOT NULL,
  price_cents INTEGER,
  shipping_cents INTEGER,
  tax_cents INTEGER,
  coupon_cents INTEGER,
  total_cents INTEGER,
  savings_cents INTEGER,
  currency TEXT NOT NULL,
  seller TEXT,
  condition TEXT,
  reason TEXT NOT NULL,
  note TEXT NOT NULL,
  FOREIGN KEY (order_item_id) REFERENCES order_items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS price_alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_item_id INTEGER NOT NULL,
  snapshot_id INTEGER NOT NULL,
  dedupe_key TEXT NOT NULL UNIQUE,
  savings_cents INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (order_item_id) REFERENCES order_items(id) ON DELETE CASCADE,
  FOREIGN KEY (snapshot_id) REFERENCES price_snapshots(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS refund_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_item_id INTEGER NOT NULL,
  status TEXT NOT NULL,
  message TEXT NOT NULL,
  confirmed_refund_cents INTEGER,
  denial_final INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (order_item_id) REFERENCES order_items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  order_item_id INTEGER,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  dedupe_key TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  delivered_to_macos INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (order_item_id) REFERENCES order_items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  at TEXT NOT NULL,
  action TEXT NOT NULL,
  detail TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id)
);
"""


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    connection = connect(path)
    try:
        connection.executescript(SCHEMA)
        now = _now()
        connection.execute(
            "INSERT OR IGNORE INTO users (id, display_name, created_at) VALUES (?, ?, ?)",
            (LOCAL_USER_ID, "Local user", now),
        )
        for key, value in DEFAULT_SETTINGS.items():
            connection.execute(
                """
                INSERT OR IGNORE INTO settings (user_id, key, value, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (LOCAL_USER_ID, key, json.dumps(value), now),
            )
        connection.commit()
    finally:
        connection.close()
    os.chmod(path, 0o600)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def today() -> date:
    return datetime.now(timezone.utc).date()


def get_settings(connection: sqlite3.Connection, user_id: str = LOCAL_USER_ID) -> dict:
    merged: dict = dict(DEFAULT_SETTINGS)
    rows = connection.execute(
        "SELECT key, value FROM settings WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    for row in rows:
        merged[row["key"]] = json.loads(row["value"])
    return merged


def save_settings(connection: sqlite3.Connection, values: dict, user_id: str = LOCAL_USER_ID) -> dict:
    now = _now()
    for key, value in values.items():
        connection.execute(
            """
            INSERT INTO settings (user_id, key, value, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (user_id, key, json.dumps(value), now),
        )
    return get_settings(connection, user_id)


def sample_loaded(connection: sqlite3.Connection, user_id: str = LOCAL_USER_ID) -> bool:
    row = connection.execute(
        "SELECT 1 FROM orders WHERE user_id = ? AND is_sample = 1 LIMIT 1",
        (user_id,),
    ).fetchone()
    return row is not None


def load_sample_orders(connection: sqlite3.Connection, user_id: str = LOCAL_USER_ID) -> int:
    current_day = today()
    now = _now()
    count = 0
    for order in SAMPLE_ORDERS:
        purchased = current_day - timedelta(days=order["purchased_days_ago"])
        cursor = connection.execute(
            """
            INSERT INTO orders (
              user_id, amazon_order_id, purchased_on, currency, shipping_cents,
              tax_cents, source, is_sample, created_at
            ) VALUES (?, ?, ?, 'USD', ?, ?, 'sample', 1, ?)
            """,
            (
                user_id,
                order["amazon_order_id"],
                purchased.isoformat(),
                order["shipping_cents"],
                order["tax_cents"],
                now,
            ),
        )
        order_id = cursor.lastrowid
        for item in order["items"]:
            deadline = current_day + timedelta(days=item["return_deadline_in_days"])
            connection.execute(
                """
                INSERT INTO order_items (
                  order_id, asin, title, product_url, quantity, unit_price_cents,
                  item_shipping_cents, item_tax_cents, seller, condition, variation_note,
                  return_eligible, return_deadline, monitoring_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'sample')
                """,
                (
                    order_id,
                    item["asin"],
                    item["title"],
                    f"https://example.invalid/sample/{item['asin']}",
                    item["quantity"],
                    item["unit_price_cents"],
                    item["item_shipping_cents"],
                    item["item_tax_cents"],
                    item["seller"],
                    item["condition"],
                    item["variation_note"],
                    1 if item["return_eligible"] else 0,
                    deadline.isoformat(),
                ),
            )
        count += 1
    connection.execute(
        """
        INSERT INTO sync_runs (
          user_id, started_at, finished_at, status, source, message, orders_seen
        ) VALUES (?, ?, ?, 'succeeded', 'sample', ?, ?)
        """,
        (
            user_id,
            now,
            now,
            "Loaded labeled sample orders. Amazon was not contacted.",
            count,
        ),
    )
    _audit(connection, user_id, "sample_loaded", f"Loaded {count} labeled sample orders.")
    return count


def delete_sample_orders(connection: sqlite3.Connection, user_id: str = LOCAL_USER_ID) -> None:
    connection.execute(
        "DELETE FROM orders WHERE user_id = ? AND is_sample = 1",
        (user_id,),
    )
    connection.execute(
        "DELETE FROM sync_runs WHERE user_id = ? AND source = 'sample'",
        (user_id,),
    )
    _audit(connection, user_id, "sample_deleted", "Removed labeled sample orders.")


def purge_purchase_data(connection: sqlite3.Connection, user_id: str = LOCAL_USER_ID) -> None:
    connection.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
    connection.execute("DELETE FROM orders WHERE user_id = ?", (user_id,))
    connection.execute("DELETE FROM sync_runs WHERE user_id = ?", (user_id,))
    _audit(connection, user_id, "purchase_data_deleted", "Removed local purchase rows.")


def list_item_rows(connection: sqlite3.Connection, user_id: str = LOCAL_USER_ID) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT
              i.id, i.asin, i.title, i.product_url, i.quantity, i.unit_price_cents,
              i.item_shipping_cents, i.item_tax_cents, i.seller, i.condition,
              i.variation_note, i.return_eligible, i.return_deadline, i.monitoring_status,
              o.amazon_order_id, o.purchased_on, o.is_sample, o.currency, o.source AS order_source,
              s.checked_at, s.source AS price_source, s.comparable, s.price_cents,
              s.total_cents, s.savings_cents, s.reason, s.note
            FROM order_items i
            JOIN orders o ON o.id = i.order_id
            LEFT JOIN price_snapshots s ON s.id = (
              SELECT id FROM price_snapshots
              WHERE order_item_id = i.id
              ORDER BY checked_at DESC, id DESC
              LIMIT 1
            )
            WHERE o.user_id = ?
            """,
            (user_id,),
        ).fetchall()
    )


def data_mode(connection: sqlite3.Connection, user_id: str = LOCAL_USER_ID) -> str:
    rows = connection.execute(
        "SELECT DISTINCT is_sample FROM orders WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    flags = {row[0] for row in rows}
    if not flags:
        return "empty"
    if flags == {1}:
        return "sample"
    if flags == {0}:
        return "imported"
    return "mixed"


def last_successful_sync(connection: sqlite3.Connection, user_id: str = LOCAL_USER_ID) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT finished_at, source, message, orders_seen
        FROM sync_runs
        WHERE user_id = ? AND status = 'succeeded'
        ORDER BY finished_at DESC, id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()


def insert_snapshot(connection: sqlite3.Connection, item_id: int, payload: dict) -> int:
    cursor = connection.execute(
        """
        INSERT INTO price_snapshots (
          order_item_id, checked_at, source, comparable, price_cents, shipping_cents,
          tax_cents, coupon_cents, total_cents, savings_cents, currency, seller,
          condition, reason, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'USD', ?, ?, ?, ?)
        """,
        (
            item_id,
            payload["checked_at"],
            payload["source"],
            1 if payload["comparable"] else 0,
            payload["price_cents"],
            payload["shipping_cents"],
            payload["tax_cents"],
            payload["coupon_cents"],
            payload["total_cents"],
            payload["savings_cents"],
            payload["seller"],
            payload["condition"],
            payload["reason"],
            payload["note"],
        ),
    )
    return int(cursor.lastrowid)


def notification_exists(connection: sqlite3.Connection, dedupe_key: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM notifications WHERE dedupe_key = ?",
        (dedupe_key,),
    ).fetchone()
    return row is not None


def insert_notification(
    connection: sqlite3.Connection,
    *,
    user_id: str,
    order_item_id: int | None,
    kind: str,
    title: str,
    body: str,
    dedupe_key: str,
    snapshot_id: int | None = None,
    savings_cents: int | None = None,
) -> None:
    if notification_exists(connection, dedupe_key):
        return
    now = _now()
    connection.execute(
        """
        INSERT INTO notifications (
          user_id, order_item_id, kind, title, body, dedupe_key, created_at, delivered_to_macos
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (user_id, order_item_id, kind, title, body, dedupe_key, now),
    )
    if snapshot_id is not None and order_item_id is not None and savings_cents is not None:
        connection.execute(
            """
            INSERT INTO price_alerts (
              order_item_id, snapshot_id, dedupe_key, savings_cents, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (order_item_id, snapshot_id, dedupe_key, savings_cents, now),
        )


def list_notifications(connection: sqlite3.Connection, user_id: str = LOCAL_USER_ID) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT kind, title, body, created_at, delivered_to_macos
            FROM notifications
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
    )


def list_snapshots(connection: sqlite3.Connection, user_id: str = LOCAL_USER_ID) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT
              s.checked_at, s.source, s.comparable, s.savings_cents, s.total_cents,
              s.price_cents, s.note, s.reason, i.asin, i.title, o.is_sample
            FROM price_snapshots s
            JOIN order_items i ON i.id = s.order_item_id
            JOIN orders o ON o.id = i.order_id
            WHERE o.user_id = ?
            ORDER BY s.checked_at DESC, s.id DESC
            """,
            (user_id,),
        ).fetchall()
    )


def refund_summary(connection: sqlite3.Connection, user_id: str = LOCAL_USER_ID) -> tuple[int, int]:
    pending = connection.execute(
        """
        SELECT COUNT(*)
        FROM refund_requests r
        JOIN order_items i ON i.id = r.order_item_id
        JOIN orders o ON o.id = i.order_id
        WHERE o.user_id = ? AND r.status IN ('submitted', 'pending')
        """,
        (user_id,),
    ).fetchone()[0]
    confirmed = connection.execute(
        """
        SELECT COALESCE(SUM(r.confirmed_refund_cents), 0)
        FROM refund_requests r
        JOIN order_items i ON i.id = r.order_item_id
        JOIN orders o ON o.id = i.order_id
        WHERE o.user_id = ? AND r.status = 'accepted'
        """,
        (user_id,),
    ).fetchone()[0]
    return int(pending), int(confirmed)


def list_refunds(connection: sqlite3.Connection, user_id: str = LOCAL_USER_ID) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT r.status, r.message, r.confirmed_refund_cents, r.updated_at, i.title, i.asin
            FROM refund_requests r
            JOIN order_items i ON i.id = r.order_item_id
            JOIN orders o ON o.id = i.order_id
            WHERE o.user_id = ?
            ORDER BY r.updated_at DESC
            """,
            (user_id,),
        ).fetchall()
    )


def _audit(connection: sqlite3.Connection, user_id: str, action: str, detail: str) -> None:
    connection.execute(
        "INSERT INTO audit_events (user_id, at, action, detail) VALUES (?, ?, ?, ?)",
        (user_id, _now(), action, detail),
    )
