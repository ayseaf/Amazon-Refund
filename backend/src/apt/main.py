"""Application factory. Importing this module does not create a database."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apt.api import client_allowed, router
from apt.config import AppConfig
from apt.db import connect, init_db
from apt.logging_config import setup_logging
from apt.secrets import build_secret_store

logger = logging.getLogger("apt")

ALLOWED_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:1420",
    "http://localhost:1420",
    "tauri://localhost",
    "http://tauri.localhost",
]


def create_app(config: AppConfig) -> FastAPI:
    config.data_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(config.data_dir / "logs" / "app.log")
    init_db(config.database_path)
    app = FastAPI(title="Amazon Price Tracker & Refund Assistant", version="0.1.0")
    app.state.config = config
    app.state.connect = lambda: connect(config.database_path)
    app.state.secrets = build_secret_store(config.data_dir)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["content-type"],
    )

    @app.middleware("http")
    async def local_only(request, call_next):
        host = request.client.host if request.client else None
        if not client_allowed(host):
            return JSONResponse({"detail": "This service accepts local requests only."}, status_code=403)
        response = await call_next(request)
        logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
        return response

    app.include_router(router)
    return app


def create_production_app() -> FastAPI:
    return create_app(AppConfig.from_env())
