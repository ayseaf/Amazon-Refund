from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta

from tracker.timeutil import as_utc_text


class PhaseNotReady(RuntimeError):
    pass


def scheduler_status(platform_name: str | None = None) -> dict:
    current = sys.platform if platform_name is None else platform_name
    if current == "darwin":
        detail = (
            "Phase 1 does not install or load a launchd agent. "
            "A disabled plist template is included for a later phase. "
            "No price provider is configured, so no checks run."
        )
        backend = "launchd"
    else:
        detail = (
            "Background monitoring is not running. launchd is a macOS service and is "
            "unavailable here. No price provider is configured in Phase 1."
        )
        backend = "disabled"
    return {
        "backend": backend,
        "running": False,
        "available": False,
        "installed": False,
        "detail": detail,
    }


def install_background_scheduler() -> None:
    raise PhaseNotReady(
        "Background scheduling is not installed in Phase 1. "
        "The launchd plist is documentation only and must not be loaded. "
        "Loading it would not check prices."
    )


def reserve_task(
    connection: sqlite3.Connection,
    *,
    profile_id: str,
    task_key: str,
    now: datetime,
    min_interval: timedelta,
    owner: str,
) -> bool:
    """Return True when this caller holds the reservation.

    A second caller receives False until locked_until. Restarts are safe because
    the reservation lives in SQLite, not in process memory.
    """
    if min_interval.total_seconds() < 0:
        raise ValueError("min_interval cannot be negative")
    current = as_utc_text(now)
    locked_until = as_utc_text(now + min_interval)
    row = connection.execute(
        "SELECT locked_until FROM task_reservations WHERE profile_id = ? AND task_key = ?",
        (profile_id, task_key),
    ).fetchone()
    if row is not None and row["locked_until"] > current:
        return False
    if row is None:
        connection.execute(
            """
            INSERT INTO task_reservations (profile_id, task_key, locked_until, owner)
            VALUES (?, ?, ?, ?)
            """,
            (profile_id, task_key, locked_until, owner),
        )
    else:
        connection.execute(
            """
            UPDATE task_reservations
            SET locked_until = ?, owner = ?
            WHERE profile_id = ? AND task_key = ?
            """,
            (locked_until, owner, profile_id, task_key),
        )
    connection.commit()
    return True
