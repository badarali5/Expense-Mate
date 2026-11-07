"""
database.py — Database Layer
-----------------------------
Owns the SQLite connection and schema versioning ONLY.
It contains no queries for application data (Repository layer) and no
business rules (Service layer). Rewritten from the Assignment 01 `Database`
class, which mixed connection handling, schema and every query in one place.
"""

import os
import sqlite3

from migrations import migrate, get_schema_version

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "expensemate.db")


class Database:
    """SQLite connection that is always brought up to the latest schema version."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.row_factory = sqlite3.Row
        migrate(self.conn)

    @property
    def schema_version(self) -> int:
        return get_schema_version(self.conn)

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
