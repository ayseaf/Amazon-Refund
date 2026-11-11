"""HTTP API. Every route is local, and none of them contact Amazon."""

from __future__ import annotations

import logging
from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from apt.config import LOCAL_USER_ID
from apt.db import (
    data_mode,
    delete_sample_orders,
    get_settings,
    insert_notification,
    insert_snapshot,
    last_successful_sync,
    list_item_rows,
    list_notifications,
    list_refunds,
    list_snapshots,
    load_sample_orders,
    notification_exists,
    purge_purchase_data,
    refund_summary,
    sample_loaded,
    save_settings,
    today,
)
from apt.domain import (
    DASHBOARD_DISCLAIMER,
    REFUND_POLICY,
    RETURNS_FORMULA,
    comparable_savings,
    deadline_window,
    difference_label,
    offer_equivalence,
    repurchase_estimate,
    sample_quote,
    stamp_form,
    stamp_word,
)
from apt.secrets import reject_secret_name

router = APIRouter(prefix="/api")
logger = logging.getLogger("apt")
LOCAL_CLIENTS = {"127.0.0.1", "::1", "testclient", "localhost"}
PURGE_PHRASE = "DELETE PURCHASE DATA"
UNAVAILABLE_CHANNELS = {"email_notifications", "telegram_notifications"}


def client_allowed(host: str | None) -> bool:
    return host in LOCAL_CLIENTS


class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    monitoring_interval_minutes: int | None = None
    notify_min_savings_cents: int | None = None
    notify_price_decreases: bool | None = None
    notify_return_deadlines: bool | None = None
    notify_price_check_failures: bool | None = None
    notify_refund_status: bool | None = None
    notify_unmonitorable: bool | None = None
    desktop_notifications: bool | None = None
    email_notifications: bool | None = None
    telegram_notifications: bool | None = None
    restocking_fee_cents: int | None = None
    return_shipping_cents: int | None = None


class SecretBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str


class PurgeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: str


def _connection(request: Request):
    return request.app.state.connect()


def _present_item(row, settings: dict, current_day: date) -> dict:
    checked = row["checked_at"] is not None
    comparable = bool(row["comparable"]) if checked else False
    savings = row["savings_cents"] if checked and comparable else None
    reason = row["reason"] or ""
    deadline = date.fromisoformat(row["return_deadline"]) if row["return_deadline"] else None
    window = deadline_window(deadline, current_day) if deadline else None
    threshold = int(settings["notify_min_savings_cents"])
    purchase_total = (
        row["unit_price_cents"] * row["quantity"]
        + row["item_shipping_cents"]
        + row["item_tax_cents"]
    )
    return {
        "id": row["id"],
        "asin": row["asin"],
        "title": row["title"],
        "product_url": row["product_url"],
        "quantity": row["quantity"],
        "unit_price_cents": row["unit_price_cents"],
        "purchase_total_cents": purchase_total,
        "shipping_cents": row["item_shipping_cents"],
        "tax_cents": row["item_tax_cents"],
        "seller": row["seller"],
        "condition": row["condition"],
        "variation_note": row["variation_note"],
        "amazon_order_id": row["amazon_order_id"],
        "purchased_on": row["purchased_on"],
        "currency": row["currency"],
        "is_sample": bool(row["is_sample"]),
        "order_source": row["order_source"],
        "return_eligible": bool(row["return_eligible"]),
        "return_deadline": row["return_deadline"],
        "deadline_window": window,
        "monitoring_status": row["monitoring_status"],
        "price_checked_at": row["checked_at"],
        "price_source": row["price_source"],
        "latest_price_cents": row["price_cents"] if checked else None,
        "latest_total_cents": row["total_cents"] if checked else None,
        "savings_cents": savings,
        "comparable": comparable if checked else None,
        "difference_label": difference_label(checked, comparable, savings, reason),
        "stamp_word": stamp_word(checked, comparable, savings),
        "stamp_form": stamp_form(checked, comparable, savings, threshold),
        "price_note": row["note"] if checked else "No price check has been run.",
        "repurchase_estimate_cents": repurchase_estimate(
            savings,
            eligible=bool(row["return_eligible"]),
            comparable=comparable if checked else False,
            restocking_cents=int(settings["restocking_fee_cents"]),
            return_shipping_cents=int(settings["return_shipping_cents"]),
        ),
    }


def _items(request: Request) -> list[dict]:
    connection = _connection(request)
    try:
        settings = get_settings(connection)
        current_day = today()
        rows = [_present_item(row, settings, current_day) for row in list_item_rows(connection)]
    finally:
        connection.close()
    rank = {"1": 0, "3": 1, "7": 2, None: 3, "past": 4}
    rows.sort(key=lambda item: (rank.get(item["deadline_window"], 5), -(item["savings_cents"] or 0)))
    return rows


def _sync_payload(connection) -> dict | None:
    row = last_successful_sync(connection)
    if row is None:
        return None
    return {
        "finished_at": row["finished_at"],
        "source": row["source"],
        "message": row["message"],
        "orders_seen": row["orders_seen"],
        "amazon_contacted": False,
    }


def _public_settings(values: dict) -> dict:
    return {
        **values,
        "email_notifications_available": False,
        "telegram_notifications_available": False,
        "desktop_notifications_available": False,
        "minimum_interval_minutes": 60,
    }


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": "0.1.0",
        "amazon_connected": False,
        "keepa_called": False,
    }


@router.get("/dashboard")
def dashboard(request: Request) -> dict:
    items = _items(request)
    connection = _connection(request)
    try:
        mode = data_mode(connection)
        sync = _sync_payload(connection)
        pending, confirmed = refund_summary(connection)
        changes = [
            {
                "asin": row["asin"],
                "title": row["title"],
                "checked_at": row["checked_at"],
                "source": row["source"],
                "savings_cents": row["savings_cents"],
                "comparable": bool(row["comparable"]),
                "is_sample": bool(row["is_sample"]),
                "note": row["note"],
            }
            for row in list_snapshots(connection)[:8]
        ]
    finally:
        connection.close()
    upcoming = [
        {
            "asin": item["asin"],
            "title": item["title"],
            "return_deadline": item["return_deadline"],
            "window": item["deadline_window"],
            "is_sample": item["is_sample"],
        }
        for item in items
        if item["deadline_window"] in {"1", "3", "7"}
    ]
    estimated = sum(item["savings_cents"] or 0 for item in items if (item["savings_cents"] or 0) > 0)
    return {
        "monitored_count": len(items),
        "estimated_savings_cents": estimated,
        "confirmed_refunds_cents": confirmed,
        "pending_refund_requests": pending,
        "upcoming_return_deadlines": upcoming,
        "recent_price_changes": changes,
        "last_successful_sync": sync,
        "data_mode": mode,
        "amazon_connected": False,
        "disclaimer": DASHBOARD_DISCLAIMER,
    }


@router.get("/orders")
def orders(request: Request) -> dict:
    connection = _connection(request)
    try:
        mode = data_mode(connection)
    finally:
        connection.close()
    return {"items": _items(request), "data_mode": mode, "amazon_connected": False}


@router.post("/sample-data")
def create_sample(request: Request) -> dict:
    connection = _connection(request)
    try:
        if sample_loaded(connection):
            raise HTTPException(status_code=409, detail="Sample data is already loaded.")
        count = load_sample_orders(connection)
        connection.commit()
    finally:
        connection.close()
    logger.info("Loaded sample orders count=%s", count)
    return {"orders": count, "amazon_contacted": False}


@router.delete("/sample-data")
def remove_sample(request: Request) -> dict:
    connection = _connection(request)
    try:
        delete_sample_orders(connection)
        connection.commit()
    finally:
        connection.close()
    logger.info("Removed labeled sample orders")
    return {"removed": True, "amazon_contacted": False}


@router.post("/price-checks")
def price_checks(request: Request) -> dict:
    connection = _connection(request)
    checked_at = datetime.now().astimezone().isoformat()
    results = []
    try:
        settings = get_settings(connection)
        threshold = int(settings["notify_min_savings_cents"])
        notify = bool(settings["notify_price_decreases"])
        rows = list_item_rows(connection)
        skipped = 0
        for row in rows:
            if not row["is_sample"]:
                skipped += 1
                results.append(
                    {
                        "asin": row["asin"],
                        "status": "skipped",
                        "source": None,
                        "reason": "A permitted price source is not configured for this item.",
                    }
                )
                continue
            quote = sample_quote(row["asin"])
            if quote is None:
                skipped += 1
                results.append(
                    {
                        "asin": row["asin"],
                        "status": "skipped",
                        "source": None,
                        "reason": "This sample item has no labeled price.",
                    }
                )
                continue
            comparable, reason = offer_equivalence(
                row["seller"],
                row["condition"],
                quote["current_seller"],
                quote["current_condition"],
            )
            savings = comparable_savings(
                quantity=row["quantity"],
                unit_price_cents=row["unit_price_cents"],
                purchase_shipping_cents=row["item_shipping_cents"],
                purchase_tax_cents=row["item_tax_cents"],
                current_unit_cents=quote["current_unit_cents"],
                current_shipping_cents=quote["current_shipping_cents"],
                current_tax_cents=quote["current_tax_cents"],
                current_coupon_cents=quote["current_coupon_cents"],
            )
            total = (
                quote["current_unit_cents"] * row["quantity"]
                + quote["current_shipping_cents"]
                + quote["current_tax_cents"]
                - quote["current_coupon_cents"]
            )
            note = (
                "Sample price. Not read from Amazon or Keepa. "
                "Tax in this sample is a labeled assumption. "
                + reason
            )
            snapshot_id = insert_snapshot(
                connection,
                row["id"],
                {
                    "checked_at": checked_at,
                    "source": "sample",
                    "comparable": comparable,
                    "price_cents": quote["current_unit_cents"],
                    "shipping_cents": quote["current_shipping_cents"],
                    "tax_cents": quote["current_tax_cents"],
                    "coupon_cents": quote["current_coupon_cents"],
                    "total_cents": total,
                    "savings_cents": savings if comparable else None,
                    "seller": quote["current_seller"],
                    "condition": quote["current_condition"],
                    "reason": reason,
                    "note": note,
                },
            )
            if notify and comparable and savings >= threshold and savings > 0:
                dedupe_key = f"drop:{row['id']}:{total}"
                insert_notification(
                    connection,
                    user_id=LOCAL_USER_ID,
                    order_item_id=row["id"],
                    kind="price_decrease",
                    title="Sample price is lower",
                    body=(
                        f"{row['title']}: the labeled sample total is lower than the amount paid. "
                        "No refund was requested."
                    ),
                    dedupe_key=dedupe_key,
                    snapshot_id=snapshot_id,
                    savings_cents=savings,
                )
            results.append(
                {
                    "asin": row["asin"],
                    "status": "checked",
                    "source": "sample",
                    "reason": reason,
                }
            )
        if skipped and settings["notify_price_check_failures"]:
            failure_key = "price-source-unconfigured"
            if not notification_exists(connection, failure_key):
                insert_notification(
                    connection,
                    user_id=LOCAL_USER_ID,
                    order_item_id=None,
                    kind="price_check_failure",
                    title="Price source is not configured",
                    body="One or more items were skipped. No price request was sent.",
                    dedupe_key=failure_key,
                )
        connection.commit()
    finally:
        connection.close()
    logger.info("Price check finished results=%s network_requests=0", len(results))
    return {
        "network_requests": 0,
        "keepa_called": False,
        "desktop_delivery": "not_sent_in_this_version",
        "results": results,
    }


@router.get("/monitoring")
def monitoring(request: Request) -> dict:
    connection = _connection(request)
    try:
        settings = get_settings(connection)
        latest = connection_execute_last_check(connection)
    finally:
        connection.close()
    return {
        "scheduler_installed": False,
        "keepa_requests_sent": False,
        "keepa_called": False,
        "interval_minutes": settings["monitoring_interval_minutes"],
        "desktop_delivery": "not_sent_in_this_version",
        "email_available": False,
        "telegram_available": False,
        "last_check": latest,
        "manual_check_available": True,
        "note": (
            "No launchd job is installed. Checks run only when you use Check prices. "
            "Keepa is not called in this version, even if a key is stored."
        ),
    }


def connection_execute_last_check(connection):
    row = connection.execute(
        """
        SELECT s.checked_at, s.source
        FROM price_snapshots s
        JOIN order_items i ON i.id = s.order_item_id
        JOIN orders o ON o.id = i.order_id
        WHERE o.user_id = ?
        ORDER BY s.checked_at DESC, s.id DESC
        LIMIT 1
        """,
        (LOCAL_USER_ID,),
    ).fetchone()
    if row is None:
        return None
    return {"checked_at": row["checked_at"], "source": row["source"], "network_requests": 0}


@router.get("/refunds")
def refunds(request: Request) -> dict:
    connection = _connection(request)
    try:
        pending, confirmed = refund_summary(connection)
        requests = [
            {
                "asin": row["asin"],
                "title": row["title"],
                "status": row["status"],
                "confirmed_refund_cents": row["confirmed_refund_cents"],
                "updated_at": row["updated_at"],
            }
            for row in list_refunds(connection)
        ]
    finally:
        connection.close()
    return {
        "requests": requests,
        "pending_refund_requests": pending,
        "confirmed_refunds_cents": confirmed,
        "policy": REFUND_POLICY,
        "drafts_available": False,
    }


@router.get("/returns")
def returns(request: Request) -> dict:
    items = _items(request)
    connection = _connection(request)
    try:
        settings = get_settings(connection)
    finally:
        connection.close()
    return {
        "submission_available": False,
        "formula": RETURNS_FORMULA,
        "restocking_fee_cents": settings["restocking_fee_cents"],
        "return_shipping_cents": settings["return_shipping_cents"],
        "items": items,
    }


@router.get("/savings")
def savings(request: Request) -> dict:
    connection = _connection(request)
    try:
        history = [
            {
                "asin": row["asin"],
                "title": row["title"],
                "checked_at": row["checked_at"],
                "source": row["source"],
                "comparable": bool(row["comparable"]),
                "savings_cents": row["savings_cents"],
                "total_cents": row["total_cents"],
                "price_cents": row["price_cents"],
                "is_sample": bool(row["is_sample"]),
                "note": row["note"],
            }
            for row in list_snapshots(connection)
        ]
    finally:
        connection.close()
    return {"snapshots": history, "amazon_contacted": False}


@router.get("/notifications")
def notifications(request: Request) -> dict:
    connection = _connection(request)
    try:
        rows = list_notifications(connection)
    finally:
        connection.close()
    return {
        "notifications": [
            {
                "kind": row["kind"],
                "title": row["title"],
                "body": row["body"],
                "created_at": row["created_at"],
                "delivered_to_macos": bool(row["delivered_to_macos"]),
            }
            for row in rows
        ],
        "desktop_delivery": "not_sent_in_this_version",
    }


@router.get("/settings")
def read_settings(request: Request) -> dict:
    connection = _connection(request)
    try:
        values = get_settings(connection)
    finally:
        connection.close()
    return _public_settings(values)


@router.put("/settings")
def update_settings(patch: SettingsPatch, request: Request) -> dict:
    changes = patch.model_dump(exclude_none=True)
    for channel in UNAVAILABLE_CHANNELS:
        if changes.get(channel) is True:
            raise HTTPException(
                status_code=400,
                detail="Email and Telegram notifications are not available in this version.",
            )
    interval = changes.get("monitoring_interval_minutes")
    if interval is not None and not 60 <= interval <= 1440:
        raise HTTPException(
            status_code=400,
            detail="Monitoring interval must be between 60 and 1440 minutes.",
        )
    for money_key in ("notify_min_savings_cents", "restocking_fee_cents", "return_shipping_cents"):
        if money_key in changes and changes[money_key] < 0:
            raise HTTPException(status_code=400, detail="Money settings cannot be negative.")
    connection = _connection(request)
    try:
        saved = save_settings(connection, changes)
        connection.commit()
    finally:
        connection.close()
    logger.info("Updated settings keys=%s", ",".join(sorted(changes)))
    return _public_settings(saved)


@router.get("/secrets")
def read_secrets(request: Request) -> dict:
    store = request.app.state.secrets
    stored = []
    if store.exists("keepa_api_key"):
        stored.append({"name": "keepa_api_key", "stored": True})
    return {"secrets": stored}


@router.put("/secrets/{name}")
def write_secret(name: str, body: SecretBody, request: Request) -> dict:
    message = reject_secret_name(name)
    if message:
        raise HTTPException(status_code=400, detail=message)
    if not body.value.strip():
        raise HTTPException(status_code=400, detail="The secret value was empty.")
    request.app.state.secrets.put(name, body.value)
    logger.info("Stored secret name=%s", name)
    return {"name": name, "stored": True}


@router.delete("/secrets/{name}")
def remove_secret(name: str, request: Request) -> dict:
    message = reject_secret_name(name)
    if message:
        raise HTTPException(status_code=400, detail=message)
    request.app.state.secrets.delete(name)
    logger.info("Deleted secret name=%s", name)
    return {"name": name, "stored": False}


@router.delete("/purchase-data")
def delete_purchase_data(body: PurgeBody, request: Request) -> dict:
    if body.confirmation != PURGE_PHRASE:
        raise HTTPException(
            status_code=400,
            detail=f"Type {PURGE_PHRASE} to delete local purchase data.",
        )
    connection = _connection(request)
    try:
        purge_purchase_data(connection)
        connection.commit()
    finally:
        connection.close()
    logger.info("Deleted local purchase data")
    return {"deleted": True, "secrets_kept": True}
