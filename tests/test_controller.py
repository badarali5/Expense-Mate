import os
import unittest

import helpers  # noqa: F401  (adds src/ to the import path)

from controller import ExpenseController
from helpers import make_controller
from services import ValidationError


class RecordingService:
    """Records every call so we can check what the controller passes down."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def method(*args):
            self.calls.append((name, args))
            return "result"
        return method


class TestControllerDelegation(unittest.TestCase):
    def setUp(self):
        self.tx, self.summary = RecordingService(), RecordingService()
        self.budgets, self.csv = RecordingService(), RecordingService()
        self.controller = ExpenseController(self.tx, self.summary, self.budgets, self.csv)

    def test_add_transaction_cleans_input_and_delegates(self):
        result = self.controller.add_transaction(" EXPENSE ", "12.5", "Food", " 2026-09-01 ", "x")
        self.assertEqual(result, "result")
        self.assertEqual(self.tx.calls, [("add_transaction",
                                          ("expense", 12.5, "Food", "2026-09-01", "x"))])

    def test_non_numeric_amount_is_rejected_before_the_service(self):
        with self.assertRaises(ValidationError):
            self.controller.add_transaction("expense", "abc", "Food", "2026-09-01")
        self.assertEqual(self.tx.calls, [])

    def test_month_and_year_are_converted_to_int(self):
        self.controller.monthly_summary("9", "2026")
        self.controller.check_budget_alerts(9.0, "2026")
        self.assertEqual(self.summary.calls, [("monthly_summary", (9, 2026))])
        self.assertEqual(self.budgets.calls, [("check_budget_alerts", (9, 2026))])

    def test_bad_month_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.controller.monthly_summary("nine", 2026)

    def test_set_budget_converts_limit(self):
        self.controller.set_budget("Food", "9", "2026", "1000")
        self.assertEqual(self.budgets.calls, [("set_budget", ("Food", 9, 2026, 1000.0))])

    def test_recurring_converts_months(self):
        self.controller.add_recurring_transaction("Expense", "5", "Rent", "2026-01-31", "r", "3")
        self.assertEqual(self.tx.calls[0][1][-1], 3)
        with self.assertRaises(ValidationError):
            self.controller.add_recurring_transaction("expense", 5, "Rent", "2026-01-31", "r", "x")

    def test_delete_converts_id(self):
        self.controller.delete_transaction("7")
        self.assertEqual(self.tx.calls, [("delete_transaction", (7,))])


class TestControllerWiredEndToEnd(unittest.TestCase):
    def setUp(self):
        self.path, self.db, self.controller = make_controller()

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def test_ui_style_string_inputs_work(self):
        self.controller.add_transaction("Income", "1000", "salary", "2026-09-01", "")
        self.assertEqual(self.controller.monthly_summary("9", "2026")["income"], 1000.0)


if __name__ == "__main__":
    unittest.main()
