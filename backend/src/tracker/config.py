from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRACKER_",
        env_file=None,
        extra="ignore",
    )

    db_path: Path = Path("data/tracker.sqlite")
    secret_backend: str = "auto"
    secret_key: str = ""
    secret_file: Path = Path("data/secrets.bin")
    host: str = "127.0.0.1"
    port: int = 8787


def find_env_file() -> Path | None:
    for candidate in (Path.cwd() / ".env", Path.cwd().parent / ".env"):
        if candidate.is_file():
            return candidate
    return None
