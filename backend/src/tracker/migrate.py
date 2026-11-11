from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from tracker.timeutil import utc_now

SCHEMA_DIR = Path(__file__).resolve().parent / "schema"

MIGRATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
"""


class MigrationChecksumError(RuntimeError):
    pass


def apply_migrations(
    connection: sqlite3.Connection,
    schema_dir: Path | None = None,
) -> list[str]:
    """Apply pending SQL migrations. Returns the versions applied on this call."""
    directory = schema_dir or SCHEMA_DIR
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(MIGRATION_TABLE_SQL)
    applied: list[str] = []
    for path in sorted(directory.glob("*.sql")):
        version = path.name.split("_", 1)[0]
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        existing = connection.execute(
            "SELECT checksum FROM schema_migrations WHERE version = ?",
            (version,),
        ).fetchone()
        if existing is not None:
            if existing["checksum"] != checksum:
                raise MigrationChecksumError(
                    f"Migration {version} was already applied with a different checksum"
                )
            continue
        connection.executescript(path.read_text(encoding="utf-8"))
        connection.execute(
            "INSERT INTO schema_migrations (version, name, checksum, applied_at) VALUES (?, ?, ?, ?)",
            (version, path.name, checksum, utc_now()),
        )
        connection.commit()
        applied.append(version)
    return applied
