from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def _protect_directory(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    resolved = directory.resolve()
    if resolved == Path.cwd().resolve() or resolved == Path("/"):
        return
    os.chmod(resolved, 0o700)


def protect_sqlite_files(path: Path) -> None:
    for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        if candidate.exists():
            os.chmod(candidate, 0o600)


def connect(path: Path) -> sqlite3.Connection:
    _protect_directory(path.parent)
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    protect_sqlite_files(path)
    return connection


def table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row["name"] for row in rows}


def column_names(connection: sqlite3.Connection, table: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}
