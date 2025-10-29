"""Database initialization utilities for the LinkedIn watcher tool.

This module centralizes creation of the SQLite database file and exposes
helpers for retrieving a connection with the correct configuration. Other
modules should import `get_conn` for database access and call `init_db`
at application start to ensure required tables exist.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
import os


DB_FILENAME = "linkedintel.db"

# Allow persistent storage via environment variable (e.g., Render Disk mounted path)
_data_dir = os.environ.get("DATA_DIR")
if _data_dir:
    DB_PATH = Path(_data_dir).expanduser().resolve() / DB_FILENAME
else:
    DB_PATH = Path(__file__).resolve().parent / DB_FILENAME


def get_conn() -> sqlite3.Connection:
    """Return a SQLite connection to the application database.

    The connection has `row_factory` configured to return `sqlite3.Row`
    instances, enabling name-based column access.
    """

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """Create database tables if they do not already exist."""

    conn = get_conn()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                firm TEXT,
                profile_url TEXT NOT NULL,
                last_title TEXT,
                last_company TEXT,
                last_seen TEXT
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                old_title TEXT,
                new_title TEXT,
                old_company TEXT,
                new_company TEXT,
                change_type TEXT NOT NULL,
                FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")

