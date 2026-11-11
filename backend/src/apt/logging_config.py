"""Application logs. Secret-shaped text is rewritten before it is written."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from apt.domain import redact


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            try:
                rendered = record.msg % record.args
            except (TypeError, ValueError):
                rendered = str(record.msg)
            record.msg = redact(str(rendered))
            record.args = ()
        else:
            record.msg = redact(str(record.msg))
        return True


class RedactFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def setup_logging(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("apt")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False
    handler = logging.FileHandler(path)
    handler.addFilter(RedactFilter())
    handler.setFormatter(RedactFormatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    os.chmod(path, 0o600)
