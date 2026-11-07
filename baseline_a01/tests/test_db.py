import os
import sys
import unittest
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from db import Database


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmpfile.close()
        self.db = Database(self.tmpfile.name)

    def tearDown(self):
        self.db.close()
        os.unlink(self.tmpfile.name)

    def test_get_or_create_category_is_idempotent(self):
        id1 = self.db.get_or_create_category("Food")
        id2 = self.db.get_or_create_category("Food")
        self.assertEqual(id1, id2)

    def test_insert_and_list_transaction(self):
        cat_id = self.db.get_or_create_category("Rent")
        self.db.insert_transaction("expense", 500.0, cat_id, "2026-09-01", "Sept rent")
        rows = self.db.list_transactions()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "Rent")
        self.assertEqual(rows[0]["amount"], 500.0)

    def test_list_transactions_filters_by_month_year(self):
        cat_id = self.db.get_or_create_category("Food")
        self.db.insert_transaction("expense", 20.0, cat_id, "2026-01-15")
        self.db.insert_transaction("expense", 30.0, cat_id, "2026-09-15")
        rows = self.db.list_transactions(month=9, year=2026)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["amount"], 30.0)

    def test_delete_transaction(self):
        cat_id = self.db.get_or_create_category("Food")
        tx_id = self.db.insert_transaction("expense", 20.0, cat_id, "2026-09-15")
        self.db.delete_transaction(tx_id)
        self.assertEqual(len(self.db.list_transactions()), 0)

    def test_set_budget_upsert(self):
        cat_id = self.db.get_or_create_category("Food")
        self.db.set_budget(cat_id, 9, 2026, 1000.0)
        self.db.set_budget(cat_id, 9, 2026, 1500.0)
        budgets = self.db.get_budgets(9, 2026)
        self.assertEqual(len(budgets), 1)
        self.assertEqual(budgets[0]["limit_amount"], 1500.0)

    def test_transaction_rejects_invalid_type(self):
        cat_id = self.db.get_or_create_category("Food")
        with self.assertRaises(Exception):
            self.db.insert_transaction("invalid_type", 20.0, cat_id, "2026-09-15")

    def test_transaction_rejects_nonpositive_amount(self):
        cat_id = self.db.get_or_create_category("Food")
        with self.assertRaises(Exception):
            self.db.insert_transaction("expense", -5.0, cat_id, "2026-09-15")


if __name__ == "__main__":
    unittest.main()
