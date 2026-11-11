from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from tracker.amazon_challenges import detect_challenge
from tracker.amazon_parse import parse_order_detail, parse_order_history, parse_product_price
from tracker.amazon_session import load_session, mark_scan, save_session
from tracker.amazon_urls import ORDER_HISTORY_URL, SIGN_IN_URL, absolute_amazon, order_detail_url, product_url, require_read_only
from tracker.scheduler import reserve_task
from tracker.services import LOCAL_PROFILE_ID, write_audit
from tracker.timeutil import as_utc_text, utc_now
from tracker.verdicts import ItemFacts, decide

log = logging.getLogger("tracker")
SCAN_TASK = "amazon_order_scan"
ORIGIN_LABEL = "Live from Amazon"
SCAN_INTERVAL = timedelta(hours=1)


@dataclass(frozen=True)
class ScanResult:
    status: str
    message: str
    orders_seen: int
    challenge_kind: str | None
    origin_label: str
    next_eligible_at: str | None


@dataclass(frozen=True)
class SignInResult:
    status: str
    message: str
    challenge_kind: str | None = None


def _pause(sleep, rng) -> None:
    sleep(rng.uniform(4.0, 8.0))


def _open(browser, url: str):
    require_read_only(url)
    return browser.goto(url)


def _reservation_until(connection: sqlite3.Connection, profile_id: str, now: datetime) -> str | None:
    row = connection.execute(
        "SELECT locked_until FROM task_reservations WHERE profile_id = ? AND task_key = ?",
        (profile_id, SCAN_TASK),
    ).fetchone()
    if row is not None and row["locked_until"] > as_utc_text(now):
        return row["locked_until"]
    return None


def _record_run(
    connection: sqlite3.Connection,
    *,
    profile_id: str,
    started_at: str,
    status: str,
    pages_read: int,
    orders_seen: int,
    challenge_kind: str | None,
    message: str,
    next_eligible_at: str | None,
) -> None:
    connection.execute(
        """
        INSERT INTO amazon_scan_runs (
            id, profile_id, started_at, finished_at, status, pages_read, orders_seen,
            challenge_kind, message, next_eligible_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            profile_id,
            started_at,
            utc_now(),
            status,
            pages_read,
            orders_seen,
            challenge_kind,
            message,
            next_eligible_at,
        ),
    )
    mark_scan(
        connection,
        profile_id=profile_id,
        status=status,
        started_at=started_at,
        finished_at=utc_now(),
        challenge=challenge_kind,
        error=message if status in {"failed", "challenge", "rate_limited"} else None,
    )
    write_audit(
        connection,
        profile_id=profile_id,
        action="amazon_scan_finished",
        detail="An order scan finished. Pages were read one at a time. Nothing was submitted.",
    )
    connection.commit()


def _challenge_result(
    connection: sqlite3.Connection,
    browser,
    *,
    profile_id: str,
    started_at: str,
    pages_read: int,
    challenge,
    next_eligible_at: str | None,
) -> ScanResult:
    status = "rate_limited" if challenge.kind == "rate_limited" else "challenge"
    _record_run(
        connection,
        profile_id=profile_id,
        started_at=started_at,
        status=status,
        pages_read=pages_read,
        orders_seen=0,
        challenge_kind=challenge.kind,
        message=challenge.message,
        next_eligible_at=next_eligible_at,
    )
    browser.hold(15)
    log.info("amazon scan stopped for a challenge kind=%s", challenge.kind)
    return ScanResult(status, challenge.message, 0, challenge.kind, ORIGIN_LABEL, next_eligible_at)


def _replace_live_rows(connection: sqlite3.Connection, profile_id: str) -> None:
    connection.execute("DELETE FROM review_gaps WHERE profile_id = ?", (profile_id,))
    connection.execute(
        "DELETE FROM orders WHERE profile_id = ? AND source = 'amazon_browser'",
        (profile_id,),
    )


def _persist(connection: sqlite3.Connection, profile_id: str, checked: list[tuple], now: datetime) -> None:
    _replace_live_rows(connection, profile_id)
    observed = as_utc_text(now)
    as_of = now.date()
    for item, offer in checked:
        purchased = item.purchased_on or as_of.isoformat()
        if item.price_paid_cents is None or item.quantity is None:
            facts = ItemFacts(
                order_id=item.order_id or "",
                asin=item.asin,
                title=item.title,
                quantity=item.quantity,
                price_paid_cents=item.price_paid_cents,
                current_price_cents=offer.price_cents if offer else None,
                purchased_on=item.purchased_on,
                return_eligible=item.return_eligible,
                return_window_end=item.return_window_end,
            )
            verdict = decide(facts, as_of=as_of)
            connection.execute(
                """
                INSERT INTO review_gaps (
                    id, profile_id, amazon_order_id, title, label, missing_json, detail, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    profile_id,
                    item.order_id,
                    item.title,
                    verdict.label,
                    json.dumps(list(verdict.missing)),
                    verdict.rule,
                    observed,
                ),
            )
            continue
        order_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO orders (
                id, profile_id, connection_id, amazon_order_id, purchased_at, order_status,
                currency, shipping_amount_cents, tax_amount_cents, order_total_cents,
                ship_to_region, source, imported_at
            ) VALUES (?, ?, NULL, ?, ?, NULL, 'USD', 0, 0, NULL, NULL, 'amazon_browser', ?)
            """,
            (order_id, profile_id, item.order_id, purchased, observed),
        )
        item_id = str(uuid.uuid4())
        current = offer.price_cents if offer is not None else None
        monitoring = "monitoring" if current is not None else "unavailable"
        connection.execute(
            """
            INSERT INTO order_items (
                id, order_id, profile_id, asin, title, product_url, seller_name, condition,
                quantity, unit_price_cents, item_shipping_cents, item_tax_cents, variation_json,
                return_eligible, return_deadline_at, monitoring_status, created_at, updated_at,
                delivery_at, fulfilled_by
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, NULL, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                item_id,
                order_id,
                profile_id,
                item.asin,
                item.title or "Untitled item",
                item.product_url,
                item.seller_name,
                item.condition,
                item.quantity,
                item.price_paid_cents,
                None if item.return_eligible is None else int(item.return_eligible),
                item.return_window_end,
                monitoring,
                observed,
                observed,
                item.delivered_on,
                item.fulfilled_by,
            ),
        )
        if current is not None:
            connection.execute(
                """
                INSERT INTO price_observations (
                    id, order_item_id, profile_id, observed_at, source, price_cents, shipping_cents,
                    currency, seller_name, condition, offer_notes, is_equivalent_offer, coupon_cents
                ) VALUES (?, ?, ?, ?, 'amazon_product_page', ?, 0, 'USD', ?, ?, ?, 1, 0)
                """,
                (
                    str(uuid.uuid4()),
                    item_id,
                    profile_id,
                    observed,
                    current,
                    item.seller_name,
                    item.condition,
                    "Public product page price. Shipping, tax, and coupons on that page were not collected.",
                ),
            )
            run_status = "succeeded"
            error = None
        else:
            run_status = "failed"
            error = "The product page did not show a price. No price was invented."
        connection.execute(
            """
            INSERT INTO price_check_runs (
                id, profile_id, order_item_id, started_at, finished_at, status, source,
                error_code, error_message, next_eligible_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'amazon_product_page', ?, ?, NULL)
            """,
            (
                str(uuid.uuid4()),
                profile_id,
                item_id,
                observed,
                observed,
                run_status,
                None if error is None else "price_not_shown",
                error,
            ),
        )
        verdict = decide(
            ItemFacts(
                order_id=item.order_id or "",
                asin=item.asin,
                title=item.title,
                quantity=item.quantity,
                price_paid_cents=item.price_paid_cents,
                current_price_cents=current,
                purchased_on=item.purchased_on,
                return_eligible=item.return_eligible,
                return_window_end=item.return_window_end,
            ),
            as_of=as_of,
        )
        connection.execute(
            """
            INSERT INTO item_verdicts (
                id, order_item_id, profile_id, verdict, label, rule, evidence_json, missing_json,
                policy_text, policy_url, potential_savings_cents, savings_note, not_guaranteed,
                draft_kind, draft_text, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                item_id,
                profile_id,
                verdict.verdict,
                verdict.label,
                verdict.rule,
                json.dumps(verdict.evidence, sort_keys=True),
                json.dumps(list(verdict.missing)),
                verdict.policy_text,
                verdict.policy_url,
                verdict.potential_savings_cents,
                verdict.savings_note,
                verdict.draft_kind,
                verdict.draft_text,
                observed,
            ),
        )
    connection.commit()


def review_last_30_days(
    *,
    browser,
    connection: sqlite3.Connection,
    secret_store,
    now: datetime,
    sleep,
    rng,
    profile_id: str = LOCAL_PROFILE_ID,
) -> ScanResult:
    session = None
    try:
        session = load_session(secret_store)
    except Exception:
        session = None
    if not session:
        message = "No Amazon session is stored on this computer. Sign in first. No page was opened."
        log.info("amazon scan skipped because no session is stored")
        return ScanResult("signed_out", message, 0, None, ORIGIN_LABEL, None)

    locked = _reservation_until(connection, profile_id, now)
    if locked is not None:
        message = "A full order scan already ran in the last hour. Amazon was not opened."
        log.info("amazon scan skipped because the hourly lock is held")
        return ScanResult("skipped", message, 0, None, ORIGIN_LABEL, locked)

    next_eligible = as_utc_text(now + SCAN_INTERVAL)
    if not reserve_task(
        connection,
        profile_id=profile_id,
        task_key=SCAN_TASK,
        now=now,
        min_interval=SCAN_INTERVAL,
        owner="local-scan",
    ):
        message = "A full order scan already ran in the last hour. Amazon was not opened."
        return ScanResult("skipped", message, 0, None, ORIGIN_LABEL, next_eligible)

    started_at = as_utc_text(now)
    pages_read = 0
    try:
        browser.add_cookies(session["cookies"])
        page = _open(browser, ORDER_HISTORY_URL)
        pages_read += 1
        challenge = detect_challenge(page.html, page.url, page.status)
        if challenge is not None:
            return _challenge_result(
                connection,
                browser,
                profile_id=profile_id,
                started_at=started_at,
                pages_read=pages_read,
                challenge=challenge,
                next_eligible_at=next_eligible,
            )
        history = parse_order_history(page.html)
        collected = list(history.orders)
        next_path = history.next_path
        extra_pages = 0
        while next_path and extra_pages < 3:
            _pause(sleep, rng)
            page = _open(browser, absolute_amazon(next_path))
            pages_read += 1
            extra_pages += 1
            challenge = detect_challenge(page.html, page.url, page.status)
            if challenge is not None:
                return _challenge_result(
                    connection,
                    browser,
                    profile_id=profile_id,
                    started_at=started_at,
                    pages_read=pages_read,
                    challenge=challenge,
                    next_eligible_at=next_eligible,
                )
            more = parse_order_history(page.html)
            collected.extend(more.orders)
            next_path = more.next_path

        cutoff = (now.date() - timedelta(days=30)).isoformat()
        recent = [order for order in collected if order.purchased_on is None or order.purchased_on >= cutoff]
        parsed_items = []
        for order in recent:
            _pause(sleep, rng)
            page = _open(browser, order_detail_url(order.order_id))
            pages_read += 1
            challenge = detect_challenge(page.html, page.url, page.status)
            if challenge is not None:
                return _challenge_result(
                    connection,
                    browser,
                    profile_id=profile_id,
                    started_at=started_at,
                    pages_read=pages_read,
                    challenge=challenge,
                    next_eligible_at=next_eligible,
                )
            for item in parse_order_detail(page.html):
                if item.purchased_on and item.purchased_on < cutoff:
                    continue
                parsed_items.append(item)

        checked: list[tuple] = []
        for item in parsed_items:
            offer = None
            if item.asin and item.price_paid_cents is not None and item.quantity is not None:
                _pause(sleep, rng)
                page = _open(browser, product_url(item.asin))
                pages_read += 1
                challenge = detect_challenge(page.html, page.url, page.status)
                if challenge is not None:
                    return _challenge_result(
                        connection,
                        browser,
                        profile_id=profile_id,
                        started_at=started_at,
                        pages_read=pages_read,
                        challenge=challenge,
                        next_eligible_at=next_eligible,
                    )
                offer = parse_product_price(page.html)
            checked.append((item, offer))

        _persist(connection, profile_id, checked, now)
        if checked:
            message = (
                f"Read {len(recent)} orders from the last 30 days on amazon.com. "
                "Prices came from public product pages. Nothing was submitted."
            )
        else:
            message = (
                "The order history page did not show any orders from the last 30 days. "
                "Nothing was invented, and nothing was submitted."
            )
        _record_run(
            connection,
            profile_id=profile_id,
            started_at=started_at,
            status="succeeded",
            pages_read=pages_read,
            orders_seen=len(recent),
            challenge_kind=None,
            message=message,
            next_eligible_at=next_eligible,
        )
        log.info("amazon scan finished status=succeeded orders=%s", len(recent))
        return ScanResult("succeeded", message, len(recent), None, ORIGIN_LABEL, next_eligible)
    except Exception as exc:
        message = "The order scan failed before it finished. No price was invented, and nothing was submitted."
        log.info("amazon scan failed")
        _record_run(
            connection,
            profile_id=profile_id,
            started_at=started_at,
            status="failed",
            pages_read=pages_read,
            orders_seen=0,
            challenge_kind=None,
            message=message,
            next_eligible_at=next_eligible,
        )
        return ScanResult("failed", f"{message} {type(exc).__name__}", 0, None, ORIGIN_LABEL, next_eligible)
    finally:
        browser.close()


def _signed_in(page) -> bool:
    if detect_challenge(page.html, page.url, page.status) is not None:
        return False
    url = page.url.lower()
    text = page.html.lower()
    if "your-orders" not in url and "order-history" not in url:
        return False
    return "your orders" in text or "hello," in text


def run_visible_sign_in(
    *,
    browser,
    connection: sqlite3.Connection,
    secret_store,
    now: datetime,
    sleep,
    timeout_s: float = 300,
    poll_seconds: float = 2,
    profile_id: str = LOCAL_PROFILE_ID,
) -> SignInResult:
    """Open the real sign-in page and wait. Never type, never read the password field."""
    started = as_utc_text(now)
    try:
        page = _open(browser, SIGN_IN_URL)
        limit = max(1, int(timeout_s / poll_seconds)) if poll_seconds else 1
        polls = 0
        last_kind = None
        while polls < limit:
            if polls:
                page = browser.snapshot()
            polls += 1
            challenge = detect_challenge(page.html, page.url, page.status)
            if _signed_in(page):
                count = save_session(secret_store, browser.cookies(), connection=connection, profile_id=profile_id)
                log.info("amazon sign-in finished status=signed_in cookies=%s", count)
                return SignInResult(
                    "signed_in",
                    "Amazon session stored on this computer. The password was not read or stored.",
                )
            if challenge is not None and challenge.kind in {"rate_limited", "unusual_activity"}:
                mark_scan(
                    connection,
                    profile_id=profile_id,
                    status="challenge",
                    started_at=started,
                    finished_at=utc_now(),
                    challenge=challenge.kind,
                    error=challenge.message,
                )
                browser.hold(15)
                log.info("amazon sign-in stopped kind=%s", challenge.kind)
                return SignInResult("challenge", challenge.message, challenge.kind)
            if challenge is not None:
                last_kind = challenge.kind
                mark_scan(
                    connection,
                    profile_id=profile_id,
                    status="awaiting_user",
                    started_at=started,
                    finished_at=None,
                    challenge=challenge.kind,
                    error=challenge.message,
                )
            page = browser.snapshot()
            sleep(poll_seconds)
        message = "Sign-in was not finished in the browser window. No password was stored."
        if last_kind == "captcha":
            message = "Amazon showed a CAPTCHA and sign-in did not finish. This app did not try to get around it."
        return SignInResult("error", message, last_kind)
    finally:
        browser.close()


def session_view(connection: sqlite3.Connection, store, profile_id: str = LOCAL_PROFILE_ID) -> dict:
    row = connection.execute(
        "SELECT * FROM amazon_session_meta WHERE profile_id = ?",
        (profile_id,),
    ).fetchone()
    configured = False
    try:
        configured = load_session(store) is not None
    except Exception:
        configured = False
    status = row["status"] if row is not None else "signed_out"
    if status == "signed_in" and not configured:
        status = "signed_out"
    locked = connection.execute(
        "SELECT locked_until FROM task_reservations WHERE profile_id = ? AND task_key = ?",
        (profile_id, SCAN_TASK),
    ).fetchone()
    return {
        "status": status,
        "marketplace": "amazon.com",
        "cookie_count": row["cookie_count"] if row is not None and configured else None,
        "saved_at": row["saved_at"] if row is not None and configured else None,
        "last_scan_status": row["last_scan_status"] if row is not None else None,
        "last_scan_finished_at": row["last_scan_finished_at"] if row is not None else None,
        "last_challenge": row["last_challenge"] if row is not None else None,
        "last_error": row["last_error"] if row is not None else None,
        "next_scan_eligible_at": locked["locked_until"] if locked is not None else None,
        "accepts_amazon_password": False,
        "origin_label": ORIGIN_LABEL,
    }


def list_live_orders(connection: sqlite3.Connection, profile_id: str = LOCAL_PROFILE_ID) -> dict:
    rows = connection.execute(
        """
        SELECT o.amazon_order_id, o.purchased_at, o.source, i.id AS item_id, i.asin, i.title,
               i.quantity, i.unit_price_cents, i.seller_name, i.condition, i.fulfilled_by,
               i.delivery_at, i.return_eligible, i.return_deadline_at, i.product_url,
               i.monitoring_status, v.verdict, v.label, v.rule, v.evidence_json, v.missing_json,
               v.policy_text, v.policy_url, v.potential_savings_cents, v.savings_note,
               v.not_guaranteed, v.draft_kind, v.draft_text,
               (
                   SELECT price_cents FROM price_observations
                   WHERE order_item_id = i.id
                   ORDER BY observed_at DESC LIMIT 1
               ) AS current_price_cents,
               (
                   SELECT observed_at FROM price_observations
                   WHERE order_item_id = i.id
                   ORDER BY observed_at DESC LIMIT 1
               ) AS price_checked_at
        FROM orders o
        JOIN order_items i ON i.order_id = o.id
        LEFT JOIN item_verdicts v ON v.order_item_id = i.id
        WHERE o.profile_id = ? AND o.source = 'amazon_browser'
        ORDER BY o.purchased_at DESC, i.title
        """,
        (profile_id,),
    ).fetchall()
    items = [_live_item(row) for row in rows]
    gaps = connection.execute(
        """
        SELECT amazon_order_id, title, label, missing_json, detail, created_at
        FROM review_gaps WHERE profile_id = ? ORDER BY created_at
        """,
        (profile_id,),
    ).fetchall()
    for gap in gaps:
        items.append(
            {
                "data_origin": "amazon_browser",
                "origin_label": ORIGIN_LABEL,
                "order_id": gap["amazon_order_id"],
                "title": gap["title"],
                "purchased_at": None,
                "asin": None,
                "quantity": None,
                "unit_price_cents": None,
                "current_price_cents": None,
                "price_checked_at": None,
                "seller_name": None,
                "fulfilled_by": None,
                "condition": None,
                "delivered_on": None,
                "return_eligible": None,
                "return_window_end": None,
                "product_url": None,
                "monitoring_status": "unavailable",
                "verdict": "unknown",
                "verdict_label": gap["label"],
                "rule": gap["detail"],
                "missing": json.loads(gap["missing_json"]),
                "evidence": {},
                "policy_text": None,
                "policy_url": None,
                "potential_savings_cents": None,
                "savings_note": gap["detail"],
                "not_guaranteed": True,
                "guaranteed": False,
                "draft_kind": None,
                "draft_text": None,
            }
        )
    return {
        "data_origin": "amazon_browser",
        "origin_label": ORIGIN_LABEL,
        "sample_label": None,
        "items": items,
    }


def _live_item(row) -> dict:
    evidence = json.loads(row["evidence_json"]) if row["evidence_json"] else {}
    missing = json.loads(row["missing_json"]) if row["missing_json"] else []
    return {
        "data_origin": "amazon_browser",
        "origin_label": ORIGIN_LABEL,
        "order_id": row["amazon_order_id"],
        "title": row["title"],
        "purchased_at": row["purchased_at"],
        "asin": row["asin"],
        "quantity": row["quantity"],
        "unit_price_cents": row["unit_price_cents"],
        "current_price_cents": row["current_price_cents"],
        "price_checked_at": row["price_checked_at"],
        "seller_name": row["seller_name"],
        "fulfilled_by": row["fulfilled_by"],
        "condition": row["condition"],
        "delivered_on": row["delivery_at"],
        "return_eligible": None if row["return_eligible"] is None else bool(row["return_eligible"]),
        "return_window_end": row["return_deadline_at"],
        "product_url": row["product_url"],
        "monitoring_status": row["monitoring_status"],
        "verdict": row["verdict"],
        "verdict_label": row["label"],
        "rule": row["rule"],
        "missing": missing,
        "evidence": evidence,
        "policy_text": row["policy_text"],
        "policy_url": row["policy_url"],
        "potential_savings_cents": row["potential_savings_cents"],
        "savings_note": row["savings_note"],
        "not_guaranteed": True,
        "guaranteed": False,
        "draft_kind": row["draft_kind"],
        "draft_text": row["draft_text"],
    }


def list_opportunities(connection: sqlite3.Connection, profile_id: str = LOCAL_PROFILE_ID) -> dict:
    live = list_live_orders(connection, profile_id)
    actionable = [
        item
        for item in live["items"]
        if item["verdict"] in {"return_possible", "price_adjustment_ask_support", "unknown"}
    ]
    return {
        "data_origin": "amazon_browser",
        "origin_label": ORIGIN_LABEL,
        "items": actionable,
        "nothing_is_submitted": True,
    }
