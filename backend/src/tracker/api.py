from __future__ import annotations

import logging
import random
import sqlite3
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from tracker import __version__
from tracker.amazon_browser import AmazonBrowserUnavailable, open_visible_browser
from tracker.amazon_scan import list_live_orders, list_opportunities, review_last_30_days, run_visible_sign_in, session_view
from tracker.amazon_session import delete_session
from tracker.config import Settings
from tracker.db import connect
from tracker.logging_config import configure_logging
from tracker.migrate import apply_migrations
from tracker.sample_data import DISCLAIMER, build_sample_catalog
from tracker.scheduler import scheduler_status
from tracker.secrets import (
    SecretNameRejected,
    SecretStoreError,
    SecretStoreLocked,
    SecretStoreReadOnly,
    open_secret_store,
    store_status,
    validate_secret_name,
)
from tracker.services import (
    LOCAL_PROFILE_ID,
    SettingsValidationError,
    ensure_local_profile,
    forget_secret_ref,
    get_settings,
    purge_purchase_data,
    remember_secret_ref,
    update_settings,
)
from tracker.timeutil import utc_now

log = logging.getLogger("tracker.access")

ALLOWED_ORIGINS = [
    "http://127.0.0.1:1420",
    "http://localhost:1420",
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
]

PRICE_CHECK_MESSAGE = (
    "No permitted price source is configured. No price was fetched, and nothing was sent to Amazon."
)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def record_skipped_price_check(connection: sqlite3.Connection, profile_id: str, message: str) -> None:
    now = utc_now()
    connection.execute(
        """
        INSERT INTO price_check_runs (
            id, profile_id, order_item_id, started_at, finished_at, status, source,
            error_code, error_message, next_eligible_at
        ) VALUES (?, ?, NULL, ?, ?, 'skipped', 'none', 'provider_not_configured', ?, NULL)
        """,
        (str(uuid.uuid4()), profile_id, now, now, message),
    )
    connection.commit()


def _default_amazon_tools():
    return {
        "browser_factory": open_visible_browser,
        "sleep": time.sleep,
        "rng": random.SystemRandom(),
        "now": lambda: datetime.now(timezone.utc),
    }


def create_app(settings: Settings | None = None, amazon_tools: dict | None = None) -> FastAPI:
    settings = settings or Settings(_env_file=None)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging()
        connection = connect(app.state.settings.db_path)
        try:
            apply_migrations(connection)
            ensure_local_profile(connection)
        finally:
            connection.close()
        app.state.secrets = open_secret_store(
            app.state.settings.secret_backend,
            app.state.settings.secret_file,
            app.state.settings.secret_key,
            sys.platform,
        )
        yield

    app = FastAPI(
        title="Amazon Price Tracker & Refund Assistant",
        version=__version__,
        description=(
            "Local Phase 1 API. Sample routes return fictional data and do not contact Amazon. "
            "This service never accepts an Amazon password and never submits a return, "
            "order, or refund request."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.amazon_tools = amazon_tools or _default_amazon_tools()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["GET", "PUT", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-Confirm-Delete"],
        allow_credentials=False,
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        response = await call_next(request)
        log.info("%s %s %s", request.method, request.url.path, response.status_code)
        return response

    @app.exception_handler(ApiError)
    async def handle_api_error(_request: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}})

    def db_connection():
        connection = connect(app.state.settings.db_path)
        try:
            yield connection
        finally:
            connection.close()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "amazon-price-tracker", "phase": 2}

    @app.get("/health/live")
    def live():
        return {"status": "live"}

    @app.get("/health/ready")
    def ready(connection: sqlite3.Connection = Depends(db_connection)):
        row = connection.execute("SELECT COUNT(*) AS n FROM schema_migrations").fetchone()
        if row is None or row["n"] < 1:
            raise ApiError(503, "database_not_ready", "Migrations have not been applied")
        return {"status": "ready", "migrations": row["n"]}

    def live_order_count(connection: sqlite3.Connection) -> int:
        row = connection.execute(
            "SELECT COUNT(*) AS n FROM orders WHERE profile_id = ? AND source = 'amazon_browser'",
            (LOCAL_PROFILE_ID,),
        ).fetchone()
        return int(row["n"]) if row else 0

    @app.get("/api/v1/info")
    def info(connection: sqlite3.Connection = Depends(db_connection)):
        secrets = app.state.secrets
        view = session_view(connection, secrets)
        connected = view["status"] == "signed_in"
        return {
            "name": "Amazon Price Tracker & Refund Assistant",
            "version": __version__,
            "phase": 2,
            "sample_data_only": live_order_count(connection) == 0,
            "amazon_connected": connected,
            "accepts_amazon_password": False,
            "secret_backend": secrets.backend_name,
            "secret_store": store_status(secrets),
            "scheduler": scheduler_status(),
            "platform": sys.platform,
            "database": "sqlite",
            "price_provider": None,
            "disclaimer": DISCLAIMER,
        }

    @app.get("/api/v1/stats")
    def stats(connection: sqlite3.Connection = Depends(db_connection)):
        orders = connection.execute(
            "SELECT COUNT(*) AS n FROM orders WHERE profile_id = ?",
            (LOCAL_PROFILE_ID,),
        ).fetchone()
        items = connection.execute(
            "SELECT COUNT(*) AS n FROM order_items WHERE profile_id = ?",
            (LOCAL_PROFILE_ID,),
        ).fetchone()
        return {
            "data_origin": "database",
            "stored_orders": orders["n"],
            "stored_items": items["n"],
            "sample_rows_included": False,
        }

    @app.get("/api/v1/sample/catalog")
    def sample_catalog():
        return build_sample_catalog()

    @app.get("/api/v1/settings")
    def read_settings(connection: sqlite3.Connection = Depends(db_connection)):
        return get_settings(connection)

    @app.put("/api/v1/settings")
    def write_settings(patch: dict, connection: sqlite3.Connection = Depends(db_connection)):
        if not isinstance(patch, dict):
            raise ApiError(422, "invalid_settings", "Settings must be a JSON object")
        try:
            return update_settings(connection, patch)
        except SettingsValidationError as exc:
            raise ApiError(422, exc.code, exc.message) from exc

    @app.put("/api/v1/secrets/{name}")
    def put_secret(name: str, body: dict, connection: sqlite3.Connection = Depends(db_connection)):
        try:
            validated = validate_secret_name(name)
        except SecretNameRejected as exc:
            raise ApiError(422, "secret_not_allowed", str(exc)) from exc
        if not isinstance(body, dict) or "value" not in body or not isinstance(body["value"], str):
            raise ApiError(422, "invalid_secret", "Send a JSON object with a string value")
        try:
            app.state.secrets.put(validated, body["value"])
        except SecretStoreLocked as exc:
            raise ApiError(503, "secret_store_locked", str(exc)) from exc
        except SecretStoreReadOnly as exc:
            raise ApiError(405, "secret_store_read_only", str(exc)) from exc
        except (SecretStoreError, SecretNameRejected) as exc:
            raise ApiError(422, "secret_rejected", str(exc)) from exc
        remember_secret_ref(connection, validated, app.state.secrets.backend_name)
        return Response(status_code=204)

    @app.get("/api/v1/secrets/{name}")
    def read_secret(name: str):
        try:
            validated = validate_secret_name(name)
            configured = app.state.secrets.get(validated) is not None
        except SecretNameRejected as exc:
            raise ApiError(422, "secret_not_allowed", str(exc)) from exc
        except SecretStoreLocked as exc:
            raise ApiError(503, "secret_store_locked", str(exc)) from exc
        except SecretStoreError as exc:
            raise ApiError(500, "secret_store_error", "The secret store could not be read") from exc
        return {
            "name": validated,
            "configured": configured,
            "backend": app.state.secrets.backend_name,
        }

    @app.delete("/api/v1/secrets/{name}")
    def delete_secret(name: str, connection: sqlite3.Connection = Depends(db_connection)):
        try:
            validated = validate_secret_name(name)
            app.state.secrets.delete(validated)
        except SecretNameRejected as exc:
            raise ApiError(422, "secret_not_allowed", str(exc)) from exc
        except SecretStoreLocked as exc:
            raise ApiError(503, "secret_store_locked", str(exc)) from exc
        except SecretStoreReadOnly as exc:
            raise ApiError(405, "secret_store_read_only", str(exc)) from exc
        except SecretStoreError as exc:
            raise ApiError(422, "secret_rejected", str(exc)) from exc
        forget_secret_ref(connection, validated)
        return Response(status_code=204)

    @app.post("/api/v1/price-checks")
    def price_checks(connection: sqlite3.Connection = Depends(db_connection)):
        record_skipped_price_check(connection, LOCAL_PROFILE_ID, PRICE_CHECK_MESSAGE)
        return JSONResponse(
            status_code=409,
            content={
                "error": {"code": "provider_not_configured", "message": PRICE_CHECK_MESSAGE},
                "checked": False,
                "price_cents": None,
                "recorded_run_status": "skipped",
            },
        )

    @app.delete("/api/v1/purchases")
    def delete_purchases(request: Request, connection: sqlite3.Connection = Depends(db_connection)):
        if request.headers.get("X-Confirm-Delete") != "DELETE-PURCHASE-DATA":
            raise ApiError(
                400,
                "confirmation_required",
                "Send header X-Confirm-Delete: DELETE-PURCHASE-DATA to delete locally stored purchase data.",
            )
        counts = purge_purchase_data(connection)
        return {"deleted": counts, "sample_data_affected": False}

    @app.get("/api/v1/scheduler")
    def read_scheduler():
        return scheduler_status()

    @app.get("/api/v1/amazon/session")
    def read_amazon_session(connection: sqlite3.Connection = Depends(db_connection)):
        return session_view(connection, app.state.secrets)

    @app.post("/api/v1/amazon/sign-in")
    def begin_sign_in(connection: sqlite3.Connection = Depends(db_connection)):
        tools = app.state.amazon_tools
        try:
            browser = tools["browser_factory"]()
        except AmazonBrowserUnavailable as exc:
            raise ApiError(503, "browser_unavailable", str(exc)) from exc
        result = run_visible_sign_in(
            browser=browser,
            connection=connection,
            secret_store=app.state.secrets,
            now=tools["now"](),
            sleep=tools["sleep"],
        )
        return {
            "status": result.status,
            "message": result.message,
            "challenge_kind": result.challenge_kind,
            "accepts_amazon_password": False,
            "session": session_view(connection, app.state.secrets),
        }

    @app.post("/api/v1/amazon/scan")
    def scan_orders(connection: sqlite3.Connection = Depends(db_connection)):
        tools = app.state.amazon_tools
        view = session_view(connection, app.state.secrets)
        if view["status"] != "signed_in":
            raise ApiError(
                409,
                "amazon_signed_out",
                "No Amazon session is stored on this computer. Open Amazon sign-in first. No page was opened.",
            )
        try:
            browser = tools["browser_factory"]()
        except AmazonBrowserUnavailable as exc:
            raise ApiError(503, "browser_unavailable", str(exc)) from exc
        result = review_last_30_days(
            browser=browser,
            connection=connection,
            secret_store=app.state.secrets,
            now=tools["now"](),
            sleep=tools["sleep"],
            rng=tools["rng"],
        )
        status_code = 200 if result.status == "succeeded" else 409
        return JSONResponse(
            status_code=status_code,
            content={
                "status": result.status,
                "message": result.message,
                "orders_seen": result.orders_seen,
                "challenge_kind": result.challenge_kind,
                "origin_label": result.origin_label,
                "next_eligible_at": result.next_eligible_at,
                "submitted": False,
            },
        )

    @app.delete("/api/v1/amazon/session")
    def sign_out(connection: sqlite3.Connection = Depends(db_connection)):
        delete_session(app.state.secrets, connection)
        return {
            "status": "signed_out",
            "deleted": True,
            "accepts_amazon_password": False,
        }

    @app.get("/api/v1/orders")
    def read_orders(connection: sqlite3.Connection = Depends(db_connection)):
        return list_live_orders(connection)

    @app.get("/api/v1/opportunities")
    def read_opportunities(connection: sqlite3.Connection = Depends(db_connection)):
        return list_opportunities(connection)

    return app
