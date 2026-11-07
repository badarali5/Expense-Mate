import os
import unittest

from helpers import make_db
from repository import BudgetRepository, CategoryRepository, TransactionRepository


class TestRepositories(unittest.TestCase):
    """Ported from the Assignment 01 test_db.py (same cases, repository API)."""

    def setUp(self):
        self.path, self.db = make_db()
        self.categories = CategoryRepository(self.db.conn)
        self.transactions = TransactionRepository(self.db.conn)
        self.budgets = BudgetRepository(self.db.conn)

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def test_get_or_create_category_is_idempotent(self):
        self.assertEqual(self.categories.get_or_create("Food"),
                         self.categories.get_or_create("Food"))

    def test_list_categories_sorted_by_name(self):
        self.categories.get_or_create("Rent")
        self.categories.get_or_create("Food")
        self.assertEqual([c["name"] for c in self.categories.list_all()], ["Food", "Rent"])

    def test_insert_and_list_transaction(self):
        cat_id = self.categories.get_or_create("Rent")
        self.transactions.insert("expense", 500.0, cat_id, "2026-09-01", "Sept rent")
        rows = self.transactions.list()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "Rent")
        self.assertEqual(rows[0]["amount"], 500.0)

    def test_insert_records_created_at(self):
        cat_id = self.categories.get_or_create("Rent")
        tx_id = self.transactions.insert("expense", 500.0, cat_id, "2026-09-01")
        created = self.db.conn.execute(
            "SELECT created_at FROM transactions WHERE id = ?", (tx_id,)).fetchone()[0]
        self.assertIsNotNone(created)

    def test_list_transactions_filters_by_month_year(self):
        cat_id = self.categories.get_or_create("Food")
        self.transactions.insert("expense", 20.0, cat_id, "2026-01-15")
        self.transactions.insert("expense", 30.0, cat_id, "2026-09-15")
        rows = self.transactions.list(month=9, year=2026)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["amount"], 30.0)

    def test_delete_transaction(self):
        cat_id = self.categories.get_or_create("Food")
        tx_id = self.transactions.insert("expense", 20.0, cat_id, "2026-09-15")
        self.transactions.delete(tx_id)
        self.assertEqual(len(self.transactions.list()), 0)

    def test_budget_upsert(self):
        cat_id = self.categories.get_or_create("Food")
        self.budgets.upsert(cat_id, 9, 2026, 1000.0)
        self.budgets.upsert(cat_id, 9, 2026, 1500.0)
        rows = self.budgets.list_for_month(9, 2026)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["limit_amount"], 1500.0)

    def test_budgets_are_filtered_by_month(self):
        cat_id = self.categories.get_or_create("Food")
        self.budgets.upsert(cat_id, 9, 2026, 1000.0)
        self.assertEqual(self.budgets.list_for_month(10, 2026), [])

    def test_transaction_rejects_invalid_type(self):
        cat_id = self.categories.get_or_create("Food")
        with self.assertRaises(Exception):
            self.transactions.insert("invalid_type", 20.0, cat_id, "2026-09-15")

    def test_transaction_rejects_nonpositive_amount(self):
        cat_id = self.categories.get_or_create("Food")
        with self.assertRaises(Exception):
            self.transactions.insert("expense", -5.0, cat_id, "2026-09-15")


if __name__ == "__main__":
    unittest.main()
