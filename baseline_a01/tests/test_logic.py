import os
import sys
import csv
import unittest
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from db import Database
from logic import ExpenseManager, ValidationError


class TestExpenseManager(unittest.TestCase):
    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmpfile.close()
        self.manager = ExpenseManager(Database(self.tmpfile.name))

    def tearDown(self):
        self.manager.db.close()
        os.unlink(self.tmpfile.name)

    def test_add_transaction_rejects_bad_type(self):
        with self.assertRaises(ValidationError):
            self.manager.add_transaction("saving", 10, "Food", "2026-09-01")

    def test_add_transaction_rejects_negative_amount(self):
        with self.assertRaises(ValidationError):
            self.manager.add_transaction("expense", -10, "Food", "2026-09-01")

    def test_add_transaction_rejects_nonnumeric_amount(self):
        with self.assertRaises(ValidationError):
            self.manager.add_transaction("expense", "not-a-number", "Food", "2026-09-01")

    def test_add_transaction_rejects_bad_date(self):
        with self.assertRaises(ValidationError):
            self.manager.add_transaction("expense", 10, "Food", "01-09-2026")

    def test_add_transaction_rejects_empty_category(self):
        with self.assertRaises(ValidationError):
            self.manager.add_transaction("expense", 10, "   ", "2026-09-01")

    def test_category_normalisation_dedupes(self):
        self.manager.add_transaction("expense", 10, "food", "2026-09-01")
        self.manager.add_transaction("expense", 15, "FOOD", "2026-09-02")
        breakdown = self.manager.category_breakdown(9, 2026)
        self.assertEqual(len(breakdown), 1)
        self.assertEqual(breakdown["Food"], 25)

    def test_monthly_summary(self):
        self.manager.add_transaction("income", 1000, "Salary", "2026-09-01")
        self.manager.add_transaction("expense", 300, "Food", "2026-09-02")
        summary = self.manager.monthly_summary(9, 2026)
        self.assertEqual(summary, {"income": 1000, "expense": 300, "net": 700})

    def test_budget_alert_statuses(self):
        self.manager.set_budget("Food", 9, 2026, 100)
        self.manager.add_transaction("expense", 50, "Food", "2026-09-01")
        alerts = self.manager.check_budget_alerts(9, 2026)
        self.assertEqual(alerts[0]["status"], "ok")

        self.manager.add_transaction("expense", 35, "Food", "2026-09-05")
        alerts = self.manager.check_budget_alerts(9, 2026)
        self.assertEqual(alerts[0]["status"], "warning")

        self.manager.add_transaction("expense", 20, "Food", "2026-09-10")
        alerts = self.manager.check_budget_alerts(9, 2026)
        self.assertEqual(alerts[0]["status"], "exceeded")

    def test_budget_rejects_nonpositive_limit(self):
        with self.assertRaises(ValidationError):
            self.manager.set_budget("Food", 9, 2026, 0)

    def test_budget_rejects_empty_category(self):
        with self.assertRaises(ValidationError):
            self.manager.set_budget("   ", 9, 2026, 100)

    def test_add_recurring_transaction_creates_n_entries(self):
        ids = self.manager.add_recurring_transaction(
            "expense", 1200, "Rent", "2026-01-31", "Monthly rent", months=3)
        self.assertEqual(len(ids), 3)
        rows = self.manager.get_transactions()
        dates = sorted(r["date"] for r in rows)
        self.assertEqual(dates, ["2026-01-31", "2026-02-28", "2026-03-31"])

    def test_add_recurring_transaction_rejects_nonpositive_months(self):
        with self.assertRaises(ValidationError):
            self.manager.add_recurring_transaction("expense", 100, "Rent", "2026-01-01", "", months=0)

    def test_export_then_import_round_trip(self):
        self.manager.add_transaction("expense", 40, "Travel", "2026-09-01", "Bus fare")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "export.csv")
            count = self.manager.export_csv(path)
            self.assertEqual(count, 1)

            fresh_db_path = os.path.join(tmpdir, "fresh.db")
            db2 = Database(fresh_db_path)
            try:
                fresh_manager = ExpenseManager(db2)
                result = fresh_manager.import_csv(path)
                self.assertEqual(result["imported"], 1)
                self.assertEqual(result["skipped"], 0)
            finally:
                db2.close()

    def test_import_csv_skips_bad_rows_and_reports_errors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "bad.csv")
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["date", "type", "category", "amount", "description"])
                writer.writerow(["2026-09-01", "expense", "Food", "20", "ok"])
                writer.writerow(["not-a-date", "expense", "Food", "20", "bad date"])
                writer.writerow(["2026-09-02", "expense", "Food", "not-a-number", "bad amount"])
            result = self.manager.import_csv(path)
            self.assertEqual(result["imported"], 1)
            self.assertEqual(result["skipped"], 2)
            self.assertEqual(len(result["errors"]), 2)

    def test_import_csv_accepts_case_insensitive_headers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "headers.csv")
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Date", "Type", "Category", "Amount", "Description"])
                writer.writerow(["2026-09-01", "expense", "Food", "20", "groceries"])
            result = self.manager.import_csv(path)
            self.assertEqual(result["imported"], 1)
            self.assertEqual(result["skipped"], 0)

    def test_import_csv_missing_columns_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "malformed.csv")
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["date", "amount"])
                writer.writerow(["2026-09-01", "20"])
            with self.assertRaises(ValidationError):
                self.manager.import_csv(path)


if __name__ == "__main__":
    unittest.main()
