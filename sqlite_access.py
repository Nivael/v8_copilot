"""Read-only SQLite connections; transaction and close ownership stay with callers."""
from __future__ import annotations

import sqlite3
from pathlib import Path


def connect_ro(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection
