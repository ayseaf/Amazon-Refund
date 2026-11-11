from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from tracker.api import create_app
from tracker.config import Settings
from tracker.db import connect
from tracker.migrate import apply_migrations
from tracker.services import ensure_local_profile


@pytest.fixture
def fernet_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
def app_settings(tmp_path, fernet_key) -> Settings:
    return Settings(
        _env_file=None,
        db_path=tmp_path / "tracker.sqlite",
        secret_backend="encrypted_file",
        secret_key=fernet_key,
        secret_file=tmp_path / "secrets.bin",
    )


@pytest.fixture
def client(app_settings):
    with TestClient(create_app(app_settings)) as test_client:
        yield test_client


@pytest.fixture
def migrated_conn(tmp_path):
    connection = connect(tmp_path / "unit.sqlite")
    apply_migrations(connection)
    ensure_local_profile(connection)
    try:
        yield connection
    finally:
        connection.close()
