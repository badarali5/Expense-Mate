"""
repository.py — Repository Layer (Data Access)
-----------------------------------------------
The ONLY place SQL is executed. Repositories receive a connection from the
Database layer and expose plain methods to the Service layer. They contain no
validation and no calculations (totals, ratios, alerts) — only queries.
"""

import sqlite3
from datetime import datetime


class CategoryRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_or_create(self, name: str) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM categories WHERE name = ?", (name,))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        self.conn.commit()
        return cur.lastrowid

    def list_all(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM categories ORDER BY name")
        return cur.fetchall()


class TransactionRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert(self, tx_type: str, amount: float, category_id: int,
               date: str, description: str = "") -> int:
        created_at = datetime.now().isoformat(timespec="seconds")
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO transactions (type, amount, category_id, date, description, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (tx_type, amount, category_id, date, description, created_at),
        )
        self.conn.commit()
        return cur.lastrowid

    def delete(self, tx_id: int):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        self.conn.commit()

    def list(self, month: int = None, year: int = None):
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


class BudgetRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert(self, category_id: int, month: int, year: int, limit_amount: float):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO budgets (category_id, month, year, limit_amount) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(category_id, month, year) DO UPDATE SET limit_amount = excluded.limit_amount",
            (category_id, month, year, limit_amount),
        )
        self.conn.commit()

    def list_for_month(self, month: int, year: int):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT b.id, c.name AS category, b.limit_amount
            FROM budgets b JOIN categories c ON b.category_id = c.id
            WHERE b.month = ? AND b.year = ?
        """, (month, year))
        return cur.fetchall()
