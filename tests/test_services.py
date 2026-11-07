import csv
import os
import tempfile
import unittest

import helpers  # noqa: F401  (adds src/ to the import path)

from services import (
    BudgetService, CsvService, SummaryService, TransactionService, ValidationError,
    STATUS_EXCEEDED, STATUS_OK, STATUS_WARNING,
)


class FakeCategories:
    def __init__(self):
        self.names = {}

    def get_or_create(self, name):
        return self.names.setdefault(name, len(self.names) + 1)


class FakeTransactions:
    """In-memory stand-in for TransactionRepository — no database involved."""

    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.inserted = []

    def insert(self, tx_type, amount, category_id, date, description=""):
        self.inserted.append((tx_type, amount, category_id, date, description))
        return len(self.inserted)

    def delete(self, tx_id):
        self.deleted = tx_id

    def list(self, month=None, year=None):
        return self.rows


class FakeBudgets:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.saved = []

    def upsert(self, category_id, month, year, limit_amount):
        self.saved.append((category_id, month, year, limit_amount))

    def list_for_month(self, month, year):
        return self.rows


class TestTransactionService(unittest.TestCase):
    def setUp(self):
        self.repo = FakeTransactions()
        self.service = TransactionService(self.repo, FakeCategories())

    def test_valid_transaction_is_passed_to_repository(self):
        self.service.add_transaction("expense", "12.5", " food ", "2026-09-01", "lunch")
        self.assertEqual(self.repo.inserted, [("expense", 12.5, 1, "2026-09-01", "lunch")])

    def test_category_is_normalised_before_lookup(self):
        categories = FakeCategories()
        TransactionService(self.repo, categories).add_transaction(
            "expense", 1, "fOOd", "2026-09-01")
        self.assertIn("Food", categories.names)

    def test_invalid_input_never_reaches_repository(self):
        bad_inputs = [("saving", 10, "Food", "2026-09-01"),
                      ("expense", -1, "Food", "2026-09-01"),
                      ("expense", "x", "Food", "2026-09-01"),
                      ("expense", 10, "Food", "01-09-2026"),
                      ("expense", 10, "  ", "2026-09-01")]
        for args in bad_inputs:
            with self.assertRaises(ValidationError):
                self.service.add_transaction(*args)
        self.assertEqual(self.repo.inserted, [])

    def test_recurring_clamps_to_last_day_of_month(self):
        self.service.add_recurring_transaction(
            "expense", 100, "Rent", "2026-01-31", "rent", 3)
        self.assertEqual([i[3] for i in self.repo.inserted],
                         ["2026-01-31", "2026-02-28", "2026-03-31"])

    def test_recurring_rolls_over_the_year(self):
        self.service.add_recurring_transaction(
            "expense", 100, "Rent", "2026-11-15", "rent", 3)
        self.assertEqual([i[3] for i in self.repo.inserted],
                         ["2026-11-15", "2026-12-15", "2027-01-15"])

    def test_recurring_leap_year_february(self):
        self.service.add_recurring_transaction(
            "expense", 100, "Rent", "2028-01-31", "rent", 2)
        self.assertEqual(self.repo.inserted[1][3], "2028-02-29")

    def test_recurring_rejects_bad_months_and_date(self):
        with self.assertRaises(ValidationError):
            self.service.add_recurring_transaction("expense", 1, "Rent", "2026-01-01", "", 0)
        with self.assertRaises(ValidationError):
            self.service.add_recurring_transaction("expense", 1, "Rent", "bad", "", 2)


class TestSummaryService(unittest.TestCase):
    ROWS = [
        {"type": "income", "amount": 1000.0, "category": "Salary"},
        {"type": "expense", "amount": 300.0, "category": "Food"},
        {"type": "expense", "amount": 200.0, "category": "Food"},
        {"type": "expense", "amount": 100.0, "category": "Rent"},
    ]

    def setUp(self):
        self.service = SummaryService(FakeTransactions(self.ROWS))

    def test_monthly_summary(self):
        self.assertEqual(self.service.monthly_summary(9, 2026),
                         {"income": 1000.0, "expense": 600.0, "net": 400.0})

    def test_category_breakdown_only_counts_expenses(self):
        self.assertEqual(self.service.category_breakdown(9, 2026),
                         {"Food": 500.0, "Rent": 100.0})

    def test_empty_month(self):
        empty = SummaryService(FakeTransactions([]))
        self.assertEqual(empty.monthly_summary(9, 2026), {"income": 0, "expense": 0, "net": 0})
        self.assertEqual(empty.category_breakdown(9, 2026), {})


class TestBudgetService(unittest.TestCase):
    def test_status_boundaries(self):
        status = BudgetService.status_for
        self.assertEqual(status(79, 100), STATUS_OK)
        self.assertEqual(status(80, 100), STATUS_WARNING)
        self.assertEqual(status(99, 100), STATUS_WARNING)
        self.assertEqual(status(100, 100), STATUS_EXCEEDED)
        self.assertEqual(status(150, 100), STATUS_EXCEEDED)

    def test_custom_warning_threshold(self):
        self.assertEqual(BudgetService.status_for(50, 100, warn_threshold=0.5), STATUS_WARNING)

    def test_zero_limit_does_not_divide_by_zero(self):
        self.assertEqual(BudgetService.status_for(10, 0), STATUS_OK)

    def test_alerts_combine_budget_rows_with_spending(self):
        summary = SummaryService(FakeTransactions([
            {"type": "expense", "amount": 90.0, "category": "Food"}]))
        budgets = FakeBudgets([{"category": "Food", "limit_amount": 100.0},
                               {"category": "Rent", "limit_amount": 500.0}])
        alerts = BudgetService(budgets, FakeCategories(), summary).check_budget_alerts(9, 2026)
        self.assertEqual([(a["category"], a["spent"], a["status"]) for a in alerts],
                         [("Food", 90.0, STATUS_WARNING), ("Rent", 0.0, STATUS_OK)])

    def test_set_budget_validation(self):
        service = BudgetService(FakeBudgets(), FakeCategories(), SummaryService(FakeTransactions()))
        for args in [("Food", 13, 2026, 100), ("Food", 0, 2026, 100), ("Food", 9, 0, 100),
                     ("Food", 9, 2026, 0), ("Food", 9, 2026, "x"), ("  ", 9, 2026, 100)]:
            with self.assertRaises(ValidationError):
                service.set_budget(*args)

    def test_set_budget_saves_normalised_category(self):
        budgets = FakeBudgets()
        BudgetService(budgets, FakeCategories(), SummaryService(FakeTransactions())).set_budget(
            "food", 9, 2026, "250")
        self.assertEqual(budgets.saved, [(1, 9, 2026, 250.0)])


class TestCsvService(unittest.TestCase):
    def setUp(self):
        self.repo = FakeTransactions()
        self.service = CsvService(TransactionService(self.repo, FakeCategories()))
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write(self, rows, name="in.csv"):
        path = os.path.join(self.tmpdir.name, name)
        with open(path, "w", newline="") as f:
            csv.writer(f).writerows(rows)
        return path

    def test_import_reports_bad_rows_with_row_numbers(self):
        path = self._write([["date", "type", "category", "amount", "description"],
                            ["2026-09-01", "expense", "Food", "20", "ok"],
                            ["bad", "expense", "Food", "20", ""],
                            ["2026-09-02", "expense", "Food", "x", ""]])
        result = self.service.import_csv(path)
        self.assertEqual((result["imported"], result["skipped"]), (1, 2))
        self.assertTrue(result["errors"][0].startswith("Row 3:"))
        self.assertTrue(result["errors"][1].startswith("Row 4:"))

    def test_import_headers_are_case_insensitive_and_description_optional(self):
        path = self._write([["Date", "TYPE", "Category", "Amount"],
                            ["2026-09-01", "Expense", "Food", "20"]])
        self.assertEqual(self.service.import_csv(path)["imported"], 1)

    def test_import_missing_columns_raises(self):
        path = self._write([["date", "amount"], ["2026-09-01", "20"]])
        with self.assertRaises(ValidationError):
            self.service.import_csv(path)

    def test_export_writes_header_and_rows(self):
        self.repo.rows = [{"date": "2026-09-01", "type": "expense", "category": "Food",
                           "amount": 40.0, "description": None}]
        path = os.path.join(self.tmpdir.name, "out.csv")
        self.assertEqual(self.service.export_csv(path), 1)
        with open(path, newline="") as f:
            lines = list(csv.reader(f))
        self.assertEqual(lines[0], ["date", "type", "category", "amount", "description"])
        self.assertEqual(lines[1], ["2026-09-01", "expense", "Food", "40.0", ""])


if __name__ == "__main__":
    unittest.main()
