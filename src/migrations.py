"""
migrations.py — Schema Migration (Part A)
------------------------------------------
Versioned, repeatable schema migrations for ExpenseMate.

The schema version is stored in SQLite's built-in `PRAGMA user_version`.
  v0 -> brand-new file OR an Assignment 01 database (no version recorded)
  v1 -> Assignment 01 baseline schema (categories, transactions, budgets)
  v2 -> v1 + transactions.created_at (when a record was entered)

Each migration is idempotent, so running the procedure twice is safe.
"""

import sqlite3

LATEST_VERSION = 2


def get_schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def _set_schema_version(conn: sqlite3.Connection, version: int):
    conn.execute(f"PRAGMA user_version = {int(version)}")


def _migrate_to_v1(conn: sqlite3.Connection):
    """Baseline: the exact Assignment 01 schema. IF NOT EXISTS lets an existing
    Assignment 01 database be adopted without touching its data."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
            amount REAL NOT NULL CHECK(amount > 0),
            category_id INTEGER NOT NULL,
            date TEXT NOT NULL,          -- ISO format YYYY-MM-DD
            description TEXT,
            FOREIGN KEY(category_id) REFERENCES categories(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
            year INTEGER NOT NULL,
            limit_amount REAL NOT NULL CHECK(limit_amount > 0),
            UNIQUE(category_id, month, year),
            FOREIGN KEY(category_id) REFERENCES categories(id)
        )
    """)


def _migrate_to_v2(conn: sqlite3.Connection):
    """Add transactions.created_at. Existing rows are back-filled with their
    own transaction date, so no row is left NULL and no original column changes."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(transactions)")}
    if "created_at" not in columns:
        conn.execute("ALTER TABLE transactions ADD COLUMN created_at TEXT")
    conn.execute("UPDATE transactions SET created_at = date WHERE created_at IS NULL")


MIGRATIONS = {1: _migrate_to_v1, 2: _migrate_to_v2}


def migrate(conn: sqlite3.Connection) -> list:
    """Apply every pending migration in order. Returns the versions applied."""
    applied = []
    for version in range(get_schema_version(conn) + 1, LATEST_VERSION + 1):
        MIGRATIONS[version](conn)
        _set_schema_version(conn, version)
        conn.commit()
        applied.append(version)
    return applied
