from __future__ import annotations

import logging
import re

_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|secret|password|token)\b(\s*[:=]\s*)(\S+)"
)
_BEARER = re.compile(r"(?i)\bbearer\s+\S+")


def redact(text: str) -> str:
    text = _ASSIGNMENT.sub(lambda match: f"{match.group(1)}{match.group(2)}[redacted]", text)
    text = _BEARER.sub("Bearer [redacted]", text)
    return text


def looks_sensitive(text: str) -> bool:
    return redact(text) != text


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if isinstance(record.args, dict):
            record.args = {
                key: redact(value) if isinstance(value, str) else value
                for key, value in record.args.items()
            }
        elif isinstance(record.args, tuple):
            record.args = tuple(redact(value) if isinstance(value, str) else value for value in record.args)
        return True


def configure_logging() -> None:
    logger = logging.getLogger("tracker")
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.addFilter(RedactionFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
