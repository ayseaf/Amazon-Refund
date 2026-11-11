"""Runtime configuration. The API binds to loopback only."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

LOCAL_USER_ID = "local"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def assert_loopback(host: str) -> str:
    if host not in LOOPBACK_HOSTS:
        raise ValueError(f"Refusing to bind {host}. This service stays on the local machine.")
    return host


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path
    host: str = "127.0.0.1"
    port: int = 8787

    @property
    def database_path(self) -> Path:
        return self.data_dir / "tracker.sqlite"

    @classmethod
    def from_env(cls) -> AppConfig:
        raw_dir = os.environ.get("APT_DATA_DIR")
        data_dir = Path(raw_dir) if raw_dir else Path.home() / ".local" / "share" / "amazon-price-tracker"
        host = assert_loopback(os.environ.get("APT_HOST", "127.0.0.1"))
        port = int(os.environ.get("APT_PORT", "8787"))
        if not 1 <= port <= 65535:
            raise ValueError("APT_PORT is out of range.")
        return cls(data_dir=data_dir, host=host, port=port)
