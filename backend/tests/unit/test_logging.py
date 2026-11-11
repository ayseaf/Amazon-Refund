from __future__ import annotations

import logging

from tracker.logging_config import RedactionFilter, redact


def test_redact_assignments_and_bearer_tokens():
    assert redact("api_key=supersecret") == "api_key=[redacted]"
    assert redact("password: hunter2") == "password: [redacted]"
    assert redact("Authorization: Bearer abc.def-ghi") == "Authorization: Bearer [redacted]"
    assert redact("price decreased by 500 cents") == "price decreased by 500 cents"


def test_redaction_filter_rewrites_log_records():
    record = logging.LogRecord(
        name="tracker",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="stored token=abc123",
        args=(),
        exc_info=None,
    )
    assert RedactionFilter().filter(record) is True
    assert record.msg == "stored token=[redacted]"
    assert "abc123" not in record.msg
