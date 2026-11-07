"""
db.py — Data Access Layer (DB Layer)
-------------------------------------
Responsible ONLY for talking to SQLite. No business rules live here
(that is Logic Layer's job) — this keeps coupling low between layers,
per the Layered architecture chosen for ExpenseMate.
"""

import sqlite3
import os

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "expensemate.db")


class Database:
    """Thin wrapper around a SQLite connection with schema management."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self):
        cur = self.conn.cursor()
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
        self.conn.commit()

    def get_or_create_category(self, name: str) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM categories WHERE name = ?", (name,))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        self.conn.commit()
        return cur.lastrowid

    def list_categories(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM categories ORDER BY name")
        return cur.fetchall()

    def insert_transaction(self, tx_type: str, amount: float, category_id: int,
                            date: str, description: str = "") -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO transactions (type, amount, category_id, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (tx_type, amount, category_id, date, description),
        )
        self.conn.commit()
        return cur.lastrowid

    def delete_transaction(self, tx_id: int):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        self.conn.commit()

    def list_transactions(self, month: int = None, year: int = None):
        cur = self.conn.cursor()
        query = """
            SELECT t.id, t.type, t.amount, c.name AS category, t.date, t.description
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
        """
        params = []
        if month and year:
            query += " WHERE strftime('%m', t.date) = ? AND strftime('%Y', t.date) = ?"
            params = [f"{month:02d}", str(year)]
        query += " ORDER BY t.date DESC"
        cur.execute(query, params)
        return cur.fetchall()

    def set_budget(self, category_id: int, month: int, year: int, limit_amount: float):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO budgets (category_id, month, year, limit_amount) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(category_id, month, year) DO UPDATE SET limit_amount = excluded.limit_amount",
            (category_id, month, year, limit_amount),
        )
        self.conn.commit()

    def get_budgets(self, month: int, year: int):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT b.id, c.name AS category, b.limit_amount
            FROM budgets b JOIN categories c ON b.category_id = c.id
            WHERE b.month = ? AND b.year = ?
        """, (month, year))
        return cur.fetchall()

    def close(self):
        self.conn.close()
