from __future__ import annotations

import json
import sqlite3
import uuid

from tracker.logging_config import looks_sensitive
from tracker.timeutil import utc_now

LOCAL_PROFILE_ID = "local"

MONITORING_INTERVAL_KEY = "monitoring_interval_minutes"
MIN_INTERVAL_MINUTES = 60
MAX_INTERVAL_MINUTES = 10080
MAX_SAVINGS_CENTS = 10_000_000

NOTIFICATION_FIELDS = {
    "desktop_notifications": "desktop_enabled",
    "email_notifications": "email_enabled",
    "telegram_notifications": "telegram_enabled",
    "notify_price_decrease": "notify_price_decrease",
    "notify_savings": "notify_savings",
    "notify_return_deadlines": "notify_return_deadlines",
    "notify_price_check_failures": "notify_price_check_failures",
    "notify_refund_status": "notify_refund_status",
    "notify_monitoring_unavailable": "notify_monitoring_unavailable",
}

FUTURE_CHANNELS = {"email_notifications", "telegram_notifications"}

FORBIDDEN_SETTING_KEYS = {
    "amazon_password",
    "password",
    "api_key",
    "keepa_api_key",
    "card_number",
    "secret",
    "token",
}


class SettingsValidationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def ensure_local_profile(connection: sqlite3.Connection) -> None:
    now = utc_now()
    connection.execute(
        """
        INSERT INTO profiles (id, display_name, created_at, updated_at)
        VALUES (?, 'Local', ?, ?)
        ON CONFLICT(id) DO NOTHING
        """,
        (LOCAL_PROFILE_ID, now, now),
    )
    connection.execute(
        """
        INSERT INTO notification_preferences (
            profile_id, desktop_enabled, email_enabled, telegram_enabled,
            min_savings_cents, notify_price_decrease, notify_savings,
            notify_return_deadlines, notify_price_check_failures,
            notify_refund_status, notify_monitoring_unavailable, updated_at
        ) VALUES (?, 1, 0, 0, 500, 1, 1, 1, 1, 1, 1, ?)
        ON CONFLICT(profile_id) DO NOTHING
        """,
        (LOCAL_PROFILE_ID, now),
    )
    connection.execute(
        """
        INSERT INTO settings (profile_id, key, value_json, updated_at)
        VALUES (?, ?, '60', ?)
        ON CONFLICT(profile_id, key) DO NOTHING
        """,
        (LOCAL_PROFILE_ID, MONITORING_INTERVAL_KEY, now),
    )
    connection.commit()


def write_audit(
    connection: sqlite3.Connection,
    *,
    profile_id: str | None,
    action: str,
    detail: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> None:
    if detail and looks_sensitive(detail):
        raise ValueError("Refusing to write sensitive data to the audit log")
    connection.execute(
        """
        INSERT INTO audit_log (id, profile_id, occurred_at, action, entity_type, entity_id, detail)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), profile_id, utc_now(), action, entity_type, entity_id, detail),
    )


def get_settings(connection: sqlite3.Connection, profile_id: str = LOCAL_PROFILE_ID) -> dict:
    preference = connection.execute(
        "SELECT * FROM notification_preferences WHERE profile_id = ?",
        (profile_id,),
    ).fetchone()
    if preference is None:
        raise SettingsValidationError("profile_missing", "The local profile has not been created")
    interval_row = connection.execute(
        "SELECT value_json FROM settings WHERE profile_id = ? AND key = ?",
        (profile_id, MONITORING_INTERVAL_KEY),
    ).fetchone()
    interval = int(json.loads(interval_row["value_json"])) if interval_row else MIN_INTERVAL_MINUTES
    return {
        "monitoring_interval_minutes": interval,
        "min_savings_cents": preference["min_savings_cents"],
        "desktop_notifications": bool(preference["desktop_enabled"]),
        "email_notifications": bool(preference["email_enabled"]),
        "telegram_notifications": bool(preference["telegram_enabled"]),
        "notify_price_decrease": bool(preference["notify_price_decrease"]),
        "notify_savings": bool(preference["notify_savings"]),
        "notify_return_deadlines": bool(preference["notify_return_deadlines"]),
        "notify_price_check_failures": bool(preference["notify_price_check_failures"]),
        "notify_refund_status": bool(preference["notify_refund_status"]),
        "notify_monitoring_unavailable": bool(preference["notify_monitoring_unavailable"]),
        "email_available": False,
        "telegram_available": False,
        "phase": 1,
    }


def _reject_forbidden(patch: dict) -> None:
    for key in patch:
        lowered = key.lower()
        if key in FORBIDDEN_SETTING_KEYS or any(
            part in lowered for part in ("password", "secret", "token", "card", "api_key")
        ):
            raise SettingsValidationError(
                "secret_not_allowed",
                "Settings cannot store passwords, API keys, or card data. "
                "A Keepa key goes to the secret store, and Amazon passwords are never accepted.",
            )


def update_settings(
    connection: sqlite3.Connection,
    patch: dict,
    profile_id: str = LOCAL_PROFILE_ID,
) -> dict:
    _reject_forbidden(patch)
    unknown = set(patch) - (set(NOTIFICATION_FIELDS) | {"monitoring_interval_minutes", "min_savings_cents"})
    if unknown:
        raise SettingsValidationError("unknown_setting", "One or more settings are not recognized")

    if "monitoring_interval_minutes" in patch:
        value = patch["monitoring_interval_minutes"]
        if isinstance(value, bool) or not isinstance(value, int):
            raise SettingsValidationError("invalid_interval", "The monitoring interval must be a whole number of minutes")
        if value < MIN_INTERVAL_MINUTES or value > MAX_INTERVAL_MINUTES:
            raise SettingsValidationError(
                "invalid_interval",
                "Phase 1 allows a monitoring interval from 60 minutes through 7 days. "
                "Shorter intervals stay off until a price provider's rate limit is known.",
            )

    if "min_savings_cents" in patch:
        value = patch["min_savings_cents"]
        if isinstance(value, bool) or not isinstance(value, int):
            raise SettingsValidationError("invalid_savings_threshold", "The savings threshold must be a whole number of cents")
        if value < 0 or value > MAX_SAVINGS_CENTS:
            raise SettingsValidationError(
                "invalid_savings_threshold",
                "The savings threshold must be between $0.00 and $100,000.00",
            )

    for field in FUTURE_CHANNELS:
        if patch.get(field) is True:
            raise SettingsValidationError(
                "channel_not_available",
                "Email and Telegram notifications are not available in this version.",
            )

    now = utc_now()
    if "monitoring_interval_minutes" in patch:
        connection.execute(
            """
            INSERT INTO settings (profile_id, key, value_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(profile_id, key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (profile_id, MONITORING_INTERVAL_KEY, json.dumps(patch["monitoring_interval_minutes"]), now),
        )
    assignments: list[str] = []
    values: list[object] = []
    if "min_savings_cents" in patch:
        assignments.append("min_savings_cents = ?")
        values.append(patch["min_savings_cents"])
    for api_name, column in NOTIFICATION_FIELDS.items():
        if api_name in patch:
            if not isinstance(patch[api_name], bool):
                raise SettingsValidationError("invalid_toggle", f"{api_name} must be true or false")
            assignments.append(f"{column} = ?")
            values.append(1 if patch[api_name] else 0)
    if assignments:
        assignments.append("updated_at = ?")
        values.append(now)
        values.append(profile_id)
        connection.execute(
            f"UPDATE notification_preferences SET {', '.join(assignments)} WHERE profile_id = ?",
            values,
        )
    connection.commit()
    return get_settings(connection, profile_id)


def remember_secret_ref(
    connection: sqlite3.Connection,
    name: str,
    backend: str,
    profile_id: str = LOCAL_PROFILE_ID,
) -> None:
    now = utc_now()
    connection.execute(
        """
        INSERT INTO secret_refs (id, profile_id, name, backend, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(profile_id, name) DO UPDATE SET
            backend = excluded.backend,
            updated_at = excluded.updated_at
        """,
        (str(uuid.uuid4()), profile_id, name, backend, now, now),
    )
    connection.commit()


def forget_secret_ref(
    connection: sqlite3.Connection,
    name: str,
    profile_id: str = LOCAL_PROFILE_ID,
) -> None:
    connection.execute(
        "DELETE FROM secret_refs WHERE profile_id = ? AND name = ?",
        (profile_id, name),
    )
    connection.commit()


def purge_purchase_data(connection: sqlite3.Connection, profile_id: str = LOCAL_PROFILE_ID) -> dict[str, int]:
    statements = [
        ("refund_events", "DELETE FROM refund_events WHERE profile_id = ?"),
        ("refund_requests", "DELETE FROM refund_requests WHERE profile_id = ?"),
        ("savings_estimates", "DELETE FROM savings_estimates WHERE profile_id = ?"),
        ("price_observations", "DELETE FROM price_observations WHERE profile_id = ?"),
        ("price_check_runs", "DELETE FROM price_check_runs WHERE profile_id = ?"),
        ("notifications", "DELETE FROM notifications WHERE profile_id = ?"),
        ("order_items", "DELETE FROM order_items WHERE profile_id = ?"),
        ("orders", "DELETE FROM orders WHERE profile_id = ?"),
        ("amazon_connections", "DELETE FROM amazon_connections WHERE profile_id = ?"),
        ("task_reservations", "DELETE FROM task_reservations WHERE profile_id = ?"),
        ("audit_log", "DELETE FROM audit_log WHERE profile_id = ?"),
    ]
    counts: dict[str, int] = {}
    for name, sql in statements:
        cursor = connection.execute(sql, (profile_id,))
        counts[name] = cursor.rowcount if cursor.rowcount is not None and cursor.rowcount >= 0 else 0
    write_audit(
        connection,
        profile_id=profile_id,
        action="purchase_data_purged",
        detail="Local purchase rows were deleted by request. Order identifiers were not recorded.",
    )
    connection.commit()
    return counts
