import os
import sqlite3
import tempfile
import unittest

import helpers  # noqa: F401  (adds src/ to the import path)

from database import Database
from migrate_db import run_migration, snapshot
from migrations import LATEST_VERSION, get_schema_version, migrate

V1_SCHEMA = """
CREATE TABLE categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
    amount REAL NOT NULL CHECK(amount > 0),
    category_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    description TEXT,
    FOREIGN KEY(category_id) REFERENCES categories(id));
CREATE TABLE budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
    year INTEGER NOT NULL,
    limit_amount REAL NOT NULL CHECK(limit_amount > 0),
    UNIQUE(category_id, month, year),
    FOREIGN KEY(category_id) REFERENCES categories(id));
INSERT INTO categories (name) VALUES ('Food'), ('Rent');
INSERT INTO transactions (type, amount, category_id, date, description) VALUES
    ('expense', 3500, 1, '2026-09-02', 'Groceries'),
    ('expense', 15000, 2, '2026-09-15', 'September rent'),
    ('income', 50000, 1, '2026-09-01', NULL);
INSERT INTO budgets (category_id, month, year, limit_amount) VALUES (1, 9, 2026, 8000);
"""


class TestMigration(unittest.TestCase):
    """Builds a real Assignment 01 (v1) database file, then migrates it."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmpdir.name, "legacy.db")
        conn = sqlite3.connect(self.path)
        conn.executescript(V1_SCHEMA)
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_legacy_database_starts_at_version_zero(self):
        conn = sqlite3.connect(self.path)
        self.assertEqual(get_schema_version(conn), 0)
        conn.close()

    def test_migration_reaches_latest_version(self):
        report = run_migration(self.path)
        self.assertEqual(report["after_version"], LATEST_VERSION)
        self.assertEqual(report["applied"], [1, 2])

    def test_existing_records_are_unchanged(self):
        report = run_migration(self.path)
        self.assertTrue(report["verified"])
        self.assertEqual(report["before"], report["after"])
        self.assertEqual(report["after"]["count"], 3)

    def test_created_at_is_backfilled_with_transaction_date(self):
        run_migration(self.path)
        conn = sqlite3.connect(self.path)
        rows = conn.execute("SELECT date, created_at FROM transactions").fetchall()
        conn.close()
        self.assertTrue(all(d == c for d, c in rows))

    def test_backup_file_is_created(self):
        report = run_migration(self.path)
        self.assertTrue(os.path.exists(report["backup"]))

    def test_migration_is_repeatable(self):
        run_migration(self.path)
        second = run_migration(self.path)
        self.assertEqual(second["applied"], [])
        self.assertTrue(second["verified"])

    def test_budgets_survive_migration(self):
        run_migration(self.path)
        conn = sqlite3.connect(self.path)
        row = conn.execute("SELECT limit_amount FROM budgets").fetchone()
        conn.close()
        self.assertEqual(row[0], 8000)

    def test_app_opens_legacy_database_and_reads_old_data(self):
        db = Database(self.path)   # opening auto-migrates
        try:
            from bootstrap import build_controller
            controller = build_controller(db)
            self.assertEqual(len(controller.get_transactions()), 3)
            summary = controller.monthly_summary(9, 2026)
            self.assertEqual(summary, {"income": 50000, "expense": 18500, "net": 31500})
            alerts = controller.check_budget_alerts(9, 2026)
            self.assertEqual(alerts[0]["status"], "ok")
        finally:
            db.close()

    def test_new_inserts_after_migration_get_created_at(self):
        db = Database(self.path)
        try:
            from bootstrap import build_controller
            tx_id = build_controller(db).add_transaction("expense", 10, "Food", "2026-10-01")
            created = db.conn.execute(
                "SELECT created_at FROM transactions WHERE id = ?", (tx_id,)).fetchone()[0]
            self.assertTrue(created and created != "2026-10-01")
        finally:
            db.close()

    def test_snapshot_detects_a_changed_record(self):
        conn = sqlite3.connect(self.path)
        before = snapshot(conn)
        conn.execute("UPDATE transactions SET amount = 1 WHERE id = 1")
        self.assertNotEqual(before, snapshot(conn))
        conn.close()


if __name__ == "__main__":
    unittest.main()
