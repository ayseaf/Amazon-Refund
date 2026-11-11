from __future__ import annotations

import uvicorn

from tracker.api import create_app
from tracker.config import Settings, find_env_file
from tracker.logging_config import configure_logging


def main() -> None:
    configure_logging()
    env_file = find_env_file()
    settings = Settings(_env_file=env_file) if env_file else Settings(_env_file=None)
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level="info",
        access_log=False,
    )
