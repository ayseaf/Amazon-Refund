from __future__ import annotations

import json
import sqlite3
from typing import Any

from tracker.secrets import SESSION_SECRET_NAME
from tracker.services import LOCAL_PROFILE_ID, forget_secret_ref, remember_secret_ref, write_audit
from tracker.timeutil import utc_now


class SessionRejected(ValueError):
    pass


def _clean_cookies(cookies: list[dict]) -> list[dict]:
    cleaned: list[dict] = []
    for cookie in cookies:
        name = str(cookie.get("name") or "")
        if not name or "password" in name.lower():
            raise SessionRejected("A password is never stored. Sign-in stays in the browser window.")
        domain = str(cookie.get("domain") or "")
        host = domain.lstrip(".").lower()
        if host != "amazon.com" and not host.endswith(".amazon.com"):
            continue
        value = cookie.get("value")
        if not isinstance(value, str) or value == "":
            continue
        cleaned.append(
            {
                "name": name,
                "value": value,
                "domain": domain if domain.startswith(".") else f".{domain}",
                "path": cookie.get("path") or "/",
                "secure": bool(cookie.get("secure", True)),
                "httpOnly": bool(cookie.get("httpOnly", True)),
            }
        )
    if not cleaned:
        raise SessionRejected("No amazon.com session cookies were available to store.")
    return cleaned


def _write_meta(
    connection: sqlite3.Connection,
    *,
    profile_id: str,
    status: str,
    saved_at: str | None = None,
    cookie_count: int | None = None,
    last_challenge: str | None = None,
    last_error: str | None = None,
    touch_saved: bool = False,
) -> None:
    now = utc_now()
    existing = connection.execute(
        "SELECT saved_at, cookie_count, last_challenge, last_error, last_scan_started_at, last_scan_finished_at, last_scan_status FROM amazon_session_meta WHERE profile_id = ?",
        (profile_id,),
    ).fetchone()
    if not touch_saved and existing is not None:
        saved_at = existing["saved_at"] if saved_at is None else saved_at
        if cookie_count is None:
            cookie_count = existing["cookie_count"]
    connection.execute(
        """
        INSERT INTO amazon_session_meta (
            profile_id, marketplace, status, saved_at, last_scan_started_at, last_scan_finished_at,
            last_scan_status, last_challenge, last_error, cookie_count, updated_at
        ) VALUES (?, 'amazon.com', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(profile_id) DO UPDATE SET
            status = excluded.status,
            saved_at = excluded.saved_at,
            last_scan_started_at = excluded.last_scan_started_at,
            last_scan_finished_at = excluded.last_scan_finished_at,
            last_scan_status = excluded.last_scan_status,
            last_challenge = excluded.last_challenge,
            last_error = excluded.last_error,
            cookie_count = excluded.cookie_count,
            updated_at = excluded.updated_at
        """,
        (
            profile_id,
            status,
            saved_at,
            existing["last_scan_started_at"] if existing else None,
            existing["last_scan_finished_at"] if existing else None,
            existing["last_scan_status"] if existing else None,
            last_challenge if last_challenge is not None else (existing["last_challenge"] if existing else None),
            last_error if last_error is not None else (existing["last_error"] if existing else None),
            cookie_count,
            now,
        ),
    )
    connection.commit()


def mark_scan(
    connection: sqlite3.Connection,
    *,
    profile_id: str,
    status: str,
    started_at: str | None = None,
    finished_at: str | None = None,
    challenge: str | None = None,
    error: str | None = None,
) -> None:
    now = utc_now()
    existing = connection.execute(
        "SELECT status, saved_at, cookie_count, last_challenge, last_error FROM amazon_session_meta WHERE profile_id = ?",
        (profile_id,),
    ).fetchone()
    connection.execute(
        """
        INSERT INTO amazon_session_meta (
            profile_id, marketplace, status, saved_at, last_scan_started_at, last_scan_finished_at,
            last_scan_status, last_challenge, last_error, cookie_count, updated_at
        ) VALUES (?, 'amazon.com', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(profile_id) DO UPDATE SET
            last_scan_started_at = COALESCE(excluded.last_scan_started_at, amazon_session_meta.last_scan_started_at),
            last_scan_finished_at = COALESCE(excluded.last_scan_finished_at, amazon_session_meta.last_scan_finished_at),
            last_scan_status = excluded.last_scan_status,
            last_challenge = excluded.last_challenge,
            last_error = excluded.last_error,
            updated_at = excluded.updated_at
        """,
        (
            profile_id,
            existing["status"] if existing else "signed_out",
            existing["saved_at"] if existing else None,
            started_at,
            finished_at,
            status,
            challenge if challenge is not None else (existing["last_challenge"] if existing else None),
            error,
            existing["cookie_count"] if existing else None,
            now,
        ),
    )
    connection.commit()


def save_session(
    store,
    cookies: list[dict],
    *,
    connection: sqlite3.Connection,
    profile_id: str = LOCAL_PROFILE_ID,
    saved_at: str | None = None,
) -> int:
    cleaned = _clean_cookies(cookies)
    stamp = saved_at or utc_now()
    payload = json.dumps(
        {"v": 1, "marketplace": "amazon.com", "saved_at": stamp, "cookies": cleaned},
        sort_keys=True,
    )
    store.put(SESSION_SECRET_NAME, payload, purpose="session")
    _write_meta(
        connection,
        profile_id=profile_id,
        status="signed_in",
        saved_at=stamp,
        cookie_count=len(cleaned),
        last_challenge=None,
        last_error=None,
        touch_saved=True,
    )
    remember_secret_ref(connection, SESSION_SECRET_NAME, store.backend_name, profile_id)
    write_audit(
        connection,
        profile_id=profile_id,
        action="amazon_session_saved",
        detail="Encrypted Amazon session cookies were saved. A password was not stored.",
    )
    connection.commit()
    return len(cleaned)


def load_session(store) -> dict[str, Any] | None:
    raw = store.get(SESSION_SECRET_NAME, purpose="session")
    if not raw:
        return None
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get("marketplace") != "amazon.com":
        raise SessionRejected("Only an amazon.com session can be loaded.")
    return payload


def delete_session(store, connection: sqlite3.Connection, profile_id: str = LOCAL_PROFILE_ID) -> None:
    store.delete(SESSION_SECRET_NAME, purpose="session")
    forget_secret_ref(connection, SESSION_SECRET_NAME, profile_id)
    _write_meta(
        connection,
        profile_id=profile_id,
        status="signed_out",
        saved_at=None,
        cookie_count=None,
        last_challenge=None,
        last_error=None,
        touch_saved=True,
    )
    write_audit(
        connection,
        profile_id=profile_id,
        action="amazon_session_deleted",
        detail="The encrypted Amazon session was deleted.",
    )
    connection.commit()
