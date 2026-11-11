from __future__ import annotations

import logging
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet

from tracker.amazon_scan import review_last_30_days, run_visible_sign_in
from tracker.amazon_session import load_session, save_session
from tracker.amazon_urls import SIGN_IN_URL
from tracker.db import connect
from tracker.logging_config import configure_logging, redact
from tracker.migrate import apply_migrations
from tracker.secrets import EncryptedFileSecretStore
from tracker.services import ensure_local_profile

REPO = Path(__file__).resolve().parents[3]
AS_OF = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)


class Page:
    def __init__(self, url: str, status: int, html: str):
        self.url = url
        self.status = status
        self.html = html


class QuietBrowser:
    def __init__(self, html: str, cookie: str):
        self.html = html
        self.cookie = cookie
        self.calls: list[str] = []
        self.page = Page(SIGN_IN_URL, 200, html)
        self.closed = False

    def goto(self, url: str) -> Page:
        self.calls.append(url)
        self.page = Page(url, 200, self.html)
        return self.page

    def snapshot(self) -> Page:
        return Page("https://www.amazon.com/your-orders/orders?timeFilter=last30", 200, "<h1>Your Orders</h1><p>Hello, account holder</p>")

    def cookies(self) -> list[dict]:
        return [
            {
                "name": "session-id",
                "value": self.cookie,
                "domain": ".amazon.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
            }
        ]

    def add_cookies(self, cookies: list[dict]) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    def hold(self, seconds: float) -> None:
        return None


def test_redaction_covers_cookies_and_password_fields():
    assert redact("session-id=abc123def") == "session-id=[redacted]"
    assert redact("Cookie: session-id=abc; ubid-main=zzz") == "Cookie: [redacted]"
    hidden = redact('<input type="password" name="password" value="hunter2">')
    assert "hunter2" not in hidden
    assert redact("price decreased by 500 cents") == "price decreased by 500 cents"


def test_password_cookies_and_session_never_reach_logs_sqlite_or_git(tmp_path, caplog):
    password = "pw-" + uuid.uuid4().hex
    cookie = "ck-" + uuid.uuid4().hex
    html = (
        "<html><body><form action='/ap/signin'>"
        f"<input type='password' name='password' id='ap_password' value='{password}'>"
        "</form><h1>Sign in</h1></body></html>"
    )
    configure_logging()
    caplog.set_level(logging.INFO)
    logging.getLogger("tracker").propagate = True
    connection = connect(tmp_path / "tracker.sqlite")
    apply_migrations(connection)
    ensure_local_profile(connection)
    store = EncryptedFileSecretStore(tmp_path / "secrets.bin", Fernet.generate_key().decode())
    browser = QuietBrowser(html, cookie)
    try:
        result = run_visible_sign_in(
            browser=browser,
            connection=connection,
            secret_store=store,
            now=AS_OF,
            sleep=lambda _seconds: None,
            timeout_s=5,
        )
        assert result.status == "signed_in"
        review = review_last_30_days(
            browser=QuietBrowser("<h1>Your Orders</h1>", cookie),
            connection=connection,
            secret_store=store,
            now=AS_OF,
            sleep=lambda _seconds: None,
            rng=__import__("random").Random(0),
        )
        assert review.status in {"succeeded", "failed", "challenge"}
    finally:
        connection.close()

    database = (tmp_path / "tracker.sqlite").read_bytes()
    secret_file = (tmp_path / "secrets.bin").read_bytes()
    assert password.encode() not in database
    assert cookie.encode() not in database
    assert password.encode() not in secret_file
    assert cookie.encode() not in secret_file
    assert password not in caplog.text
    assert cookie not in caplog.text

    grep = subprocess.run(
        ["git", "grep", "-I", "-n", password, "--", "."],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert grep.returncode == 1
    cookie_grep = subprocess.run(
        ["git", "grep", "-I", "-n", cookie, "--", "."],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert cookie_grep.returncode == 1
    for marker in (password, cookie):
        for path in REPO.rglob("*"):
            if not path.is_file():
                continue
            if any(part in {".git", ".venv", "node_modules", "target"} for part in path.parts):
                continue
            if path.stat().st_size > 2_000_000:
                continue
            contents = path.read_bytes()
            assert marker.encode() not in contents, path


def test_production_code_does_not_type_a_password_or_hide_automation():
    root = REPO / "backend" / "src" / "tracker"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for forbidden in ("ap_password", ".fill(", "page.fill", "keyboard.type", "keyboard.insert", "add_init_script", "disable-blink"):
            if forbidden in text:
                offenders.append(f"{path.name}: {forbidden}")
    assert offenders == []


def test_generic_secret_endpoint_rejects_an_uploaded_session(client):
    uploaded = client.put(
        "/api/v1/secrets/amazon_session",
        json={"value": "session-id=should-not-be-accepted"},
    )
    assert uploaded.status_code == 422
    assert "session-id=should-not-be-accepted" not in uploaded.text


def test_session_save_keeps_amazon_hosts_and_drops_other_domains(tmp_path):
    connection = connect(tmp_path / "tracker.sqlite")
    apply_migrations(connection)
    ensure_local_profile(connection)
    store = EncryptedFileSecretStore(tmp_path / "secrets.bin", Fernet.generate_key().decode())
    try:
        save_session(
            store,
            [
                {"name": "session-id", "value": "kept-www", "domain": "www.amazon.com", "path": "/"},
                {"name": "ubid-main", "value": "dropped-other", "domain": ".example.com", "path": "/"},
            ],
            connection=connection,
        )
        loaded = load_session(store)
        assert loaded is not None
        assert [cookie["value"] for cookie in loaded["cookies"]] == ["kept-www"]
        assert b"dropped-other" not in (tmp_path / "secrets.bin").read_bytes()
        assert b"kept-www" not in (tmp_path / "tracker.sqlite").read_bytes()
    finally:
        connection.close()


def test_session_save_refuses_a_password_field(tmp_path):
    connection = connect(tmp_path / "tracker.sqlite")
    apply_migrations(connection)
    ensure_local_profile(connection)
    store = EncryptedFileSecretStore(tmp_path / "secrets.bin", Fernet.generate_key().decode())
    try:
        save_session(
            store,
            [{"name": "password", "value": "nope", "domain": ".amazon.com", "path": "/"}],
            connection=connection,
        )
        raise AssertionError("password cookie should be rejected")
    except ValueError:
        assert not (tmp_path / "secrets.bin").exists() or b"nope" not in (tmp_path / "secrets.bin").read_bytes()
    finally:
        connection.close()
