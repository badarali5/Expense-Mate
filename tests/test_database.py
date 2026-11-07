import os
import sqlite3
import unittest

from helpers import make_db
from migrations import LATEST_VERSION


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.path, self.db = make_db()

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def test_new_database_is_at_latest_schema_version(self):
        self.assertEqual(self.db.schema_version, LATEST_VERSION)

    def test_schema_has_all_tables_and_created_at_column(self):
        tables = {r[0] for r in self.db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        self.assertTrue({"categories", "transactions", "budgets"} <= tables)
        columns = {r[1] for r in self.db.conn.execute("PRAGMA table_info(transactions)")}
        self.assertIn("created_at", columns)

    def test_foreign_keys_are_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.conn.execute(
                "INSERT INTO transactions (type, amount, category_id, date) "
                "VALUES ('expense', 5, 999, '2026-09-01')")

    def test_reopening_is_idempotent(self):
        from database import Database
        self.db.close()
        again = Database(self.path)
        try:
            self.assertEqual(again.schema_version, LATEST_VERSION)
        finally:
            again.close()
        self.db = Database(self.path)

    def test_context_manager_closes_connection(self):
        from database import Database
        with Database(self.path) as db:
            conn = db.conn
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")


if __name__ == "__main__":
    unittest.main()
