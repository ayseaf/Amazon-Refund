from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet

from tracker.amazon_scan import review_last_30_days
from tracker.amazon_session import load_session, save_session
from tracker.amazon_urls import SIGN_IN_URL, order_detail_url, product_url
from tracker.db import connect
from tracker.migrate import apply_migrations
from tracker.secrets import EncryptedFileSecretStore
from tracker.services import ensure_local_profile

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "amazon"
AS_OF = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)
HISTORY_URL = "https://www.amazon.com/your-orders/orders?timeFilter=last30"
LAMP = "112-1000001-0000001"
MUG = "112-1000002-0000002"
BOOK = "112-1000003-0000003"
GAP = "112-1000005-0000005"
OLD = "112-1000004-0000004"


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class Page:
    def __init__(self, url: str, status: int, html: str):
        self.url = url
        self.status = status
        self.html = html


class ScriptedBrowser:
    def __init__(self, routes: dict[str, tuple[int, str]], cookies: list[dict] | None = None):
        self.routes = routes
        self.calls: list[str] = []
        self.cookies_loaded: list[dict] = []
        self._cookies = list(cookies or [])
        self.closed = False
        self.held = None
        self.page = Page("about:blank", 200, "")

    def goto(self, url: str) -> Page:
        self.calls.append(url)
        if url not in self.routes:
            raise AssertionError(f"unexpected url {url}")
        status, html = self.routes[url]
        self.page = Page(url, status, html)
        return self.page

    def snapshot(self) -> Page:
        return self.page

    def cookies(self) -> list[dict]:
        return list(self._cookies)

    def add_cookies(self, cookies: list[dict]) -> None:
        self.cookies_loaded = list(cookies)
        self._cookies = list(cookies)

    def close(self) -> None:
        self.closed = True

    def hold(self, seconds: float) -> None:
        self.held = seconds


def _routes(history_name: str = "order_history_no_next.html") -> dict[str, tuple[int, str]]:
    history = _html("order_history.html")
    if history_name == "order_history_no_next.html":
        history = history.replace(
            '<a class="a-pagination-next" href="/your-orders/orders?timeFilter=last30&amp;startIndex=10">Next</a>',
            "",
        )
    return {
        HISTORY_URL: (200, history),
        order_detail_url(LAMP): (200, _html("order_detail_lamp.html")),
        order_detail_url(MUG): (200, _html("order_detail_mug.html")),
        order_detail_url(BOOK): (200, _html("order_detail_book.html")),
        order_detail_url(GAP): (200, _html("order_detail_gap.html")),
        product_url("B0LAMP0001"): (200, _html("product_lamp.html")),
        product_url("B0MUG00001"): (200, _html("product_mug.html")),
        product_url("B0BOOK0001"): (200, _html("product_book.html")),
    }


def _prepare(tmp_path):
    connection = connect(tmp_path / "tracker.sqlite")
    apply_migrations(connection)
    ensure_local_profile(connection)
    store = EncryptedFileSecretStore(tmp_path / "secrets.bin", Fernet.generate_key().decode())
    save_session(
        store,
        [
            {
                "name": "session-id",
                "value": "fixture-session-value",
                "domain": ".amazon.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
            }
        ],
        connection=connection,
    )
    return connection, store


def _review(tmp_path, browser, *, now=AS_OF, sleeps: list[float] | None = None):
    connection, store = _prepare(tmp_path)
    recorded: list[float] = sleeps if sleeps is not None else []
    result = review_last_30_days(
        browser=browser,
        connection=connection,
        secret_store=store,
        now=now,
        sleep=recorded.append,
        rng=random.Random(0),
    )
    return connection, store, result, recorded


def test_review_reads_one_page_at_a_time_and_labels_live_verdicts(tmp_path):
    browser = ScriptedBrowser(_routes())
    connection, _store, result, delays = _review(tmp_path, browser)
    try:
        assert result.status == "succeeded"
        assert result.orders_seen == 4
        assert OLD not in " ".join(browser.calls)
        assert browser.calls[0] == HISTORY_URL
        assert all(delay >= 4 for delay in delays)
        assert all(delay <= 8 for delay in delays)
        assert delays
        rows = connection.execute(
            """
            SELECT o.amazon_order_id, o.source, i.title, i.unit_price_cents, v.verdict, v.label, v.not_guaranteed
            FROM orders o
            JOIN order_items i ON i.order_id = o.id
            JOIN item_verdicts v ON v.order_item_id = i.id
            ORDER BY o.amazon_order_id
            """
        ).fetchall()
        by_order = {row["amazon_order_id"]: row for row in rows}
        assert set(by_order) == {LAMP, MUG, BOOK}
        assert by_order[LAMP]["source"] == "amazon_browser"
        assert by_order[LAMP]["verdict"] == "return_possible"
        assert by_order[LAMP]["label"] == "Return possible"
        assert by_order[LAMP]["not_guaranteed"] == 1
        assert by_order[MUG]["verdict"] == "price_adjustment_ask_support"
        assert by_order[BOOK]["verdict"] == "not_eligible"
        gap = connection.execute(
            "SELECT missing_json, label FROM review_gaps WHERE amazon_order_id = ?",
            (GAP,),
        ).fetchone()
        assert gap is not None
        assert gap["label"] == "Unknown"
        assert "price paid" in gap["missing_json"]
        blob = (tmp_path / "tracker.sqlite").read_bytes()
        assert b"ADDRESS REDACTED" not in blob
        assert b"NOT-A-REAL-PASSWORD" not in blob
        assert b"Visa ending in REDACTED" not in blob
        prices = connection.execute(
            "SELECT source, price_cents FROM price_observations ORDER BY price_cents"
        ).fetchall()
        assert [row["price_cents"] for row in prices] == [1000, 1200, 1900]
        assert {row["source"] for row in prices} == {"amazon_product_page"}
    finally:
        connection.close()
    assert result.origin_label == "Live from Amazon"


def test_a_second_scan_inside_the_hour_does_not_open_amazon(tmp_path):
    first = ScriptedBrowser(_routes())
    connection, store, result, _delays = _review(tmp_path, first)
    assert result.status == "succeeded"
    second = ScriptedBrowser(_routes())
    try:
        again = review_last_30_days(
            browser=second,
            connection=connection,
            secret_store=store,
            now=AS_OF + timedelta(minutes=30),
            sleep=lambda _seconds: None,
            rng=random.Random(1),
        )
    finally:
        connection.close()
    assert again.status == "skipped"
    assert second.calls == []
    assert "hour" in again.message.lower()


def test_captcha_stops_the_scan_without_another_page(tmp_path):
    routes = _routes()
    routes[HISTORY_URL] = (200, _html("captcha.html"))
    browser = ScriptedBrowser(routes)
    connection, _store, result, _delays = _review(tmp_path, browser)
    try:
        assert result.status == "challenge"
        assert result.challenge_kind == "captcha"
        assert browser.calls == [HISTORY_URL]
        assert connection.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"] == 0
        assert "captcha" in result.message.lower()
    finally:
        connection.close()
    assert browser.closed is True


def test_sign_in_waits_for_the_user_and_does_not_store_the_password(tmp_path):
    from tracker.amazon_scan import run_visible_sign_in

    password = "sign-in-password-marker"
    cookie = "sign-in-cookie-marker"
    sign_in = _html("sign_in.html").replace(
        'value=""',
        f'value="{password}"',
    )
    home = _html("orders_home.html")

    class SigningBrowser(ScriptedBrowser):
        def __init__(self):
            super().__init__(
                {SIGN_IN_URL: (200, sign_in)},
                cookies=[
                    {
                        "name": "session-id",
                        "value": cookie,
                        "domain": ".amazon.com",
                        "path": "/",
                        "secure": True,
                        "httpOnly": True,
                    }
                ],
            )
            self.seen = 0

        def snapshot(self):
            self.seen += 1
            if self.seen < 2:
                return Page(self.page.url, 200, sign_in)
            return Page("https://www.amazon.com/your-orders/orders?timeFilter=last30", 200, home)

    connection = connect(tmp_path / "tracker.sqlite")
    apply_migrations(connection)
    ensure_local_profile(connection)
    store = EncryptedFileSecretStore(tmp_path / "secrets.bin", Fernet.generate_key().decode())
    browser = SigningBrowser()
    result = run_visible_sign_in(
        browser=browser,
        connection=connection,
        secret_store=store,
        now=AS_OF,
        sleep=lambda _seconds: None,
        timeout_s=30,
    )
    try:
        assert result.status == "signed_in"
        loaded = load_session(store)
        assert loaded is not None
        assert loaded["cookies"][0]["value"] == cookie
        blob = (tmp_path / "tracker.sqlite").read_bytes()
        assert password.encode() not in blob
        assert cookie.encode() not in blob
        assert b"ap_password" not in blob
    finally:
        connection.close()
    assert password.encode() not in (tmp_path / "secrets.bin").read_bytes()
    assert cookie.encode() not in (tmp_path / "secrets.bin").read_bytes()
