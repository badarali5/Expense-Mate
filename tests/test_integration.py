"""
test_integration.py — system-level workflows
---------------------------------------------
Each test drives the real stack: Controller -> Services -> Repository -> Database
(temporary SQLite file). Only the UI is not exercised (Tkinter needs a display).
"""
import os
import sqlite3
import tempfile
import unittest

import helpers  # noqa: F401  (adds src/ to the import path)
from unittest import mock

from bootstrap import build_controller
from database import Database
from helpers import make_controller
from repository import CategoryRepository, TransactionRepository
from services import TransactionService

SAMPLE_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "sample_import.csv")


class IntegrationBase(unittest.TestCase):
    def setUp(self):
        self.path, self.db, self.controller = make_controller()

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)


class TestWorkflows(IntegrationBase):
    def test_IT1_add_transaction_is_stored_in_the_database(self):
        tx_id = self.controller.add_transaction("expense", "250", "groceries", "2026-09-03", "milk")
        conn = sqlite3.connect(self.path)
        try:
            row = conn.execute(
                "SELECT t.type, t.amount, c.name, t.date, t.description "
                "FROM transactions t JOIN categories c ON c.id = t.category_id WHERE t.id = ?",
                (tx_id,)).fetchone()
        finally:
            conn.close()
        self.assertEqual(row, ("expense", 250.0, "Groceries", "2026-09-03", "milk"))

    def test_IT2_budget_alert_moves_ok_warning_exceeded(self):
        self.controller.set_budget("Food", 9, 2026, 100)
        statuses = []
        for amount, day in [(50, "01"), (35, "05"), (20, "10")]:
            self.controller.add_transaction("expense", amount, "Food", f"2026-09-{day}")
            statuses.append(self.controller.check_budget_alerts(9, 2026)[0]["status"])
        self.assertEqual(statuses, ["ok", "warning", "exceeded"])

    def test_IT3_recurring_transactions_feed_the_monthly_summary(self):
        self.controller.add_recurring_transaction(
            "expense", 1200, "Rent", "2026-01-31", "Monthly rent", 3)
        self.assertEqual(self.controller.monthly_summary(2, 2026)["expense"], 1200)
        self.assertEqual([r["date"] for r in self.controller.get_transactions(2, 2026)],
                         ["2026-02-28"])
        self.assertEqual(len(self.controller.get_transactions()), 3)

    def test_IT4_sample_csv_import_gives_expected_totals(self):
        result = self.controller.import_csv(SAMPLE_CSV)
        self.assertEqual((result["imported"], result["skipped"]), (8, 0))
        self.assertEqual(self.controller.monthly_summary(9, 2026),
                         {"income": 50000.0, "expense": 30200.0, "net": 19800.0})
        self.assertEqual(self.controller.category_breakdown(9, 2026)["Food"], 7500.0)

    def test_IT5_export_then_import_into_a_fresh_database(self):
        self.controller.import_csv(SAMPLE_CSV)
        with tempfile.TemporaryDirectory() as tmp:
            exported = os.path.join(tmp, "out.csv")
            self.assertEqual(self.controller.export_csv(exported), 8)
            db2 = Database(os.path.join(tmp, "fresh.db"))
            try:
                fresh = build_controller(db2)
                self.assertEqual(fresh.import_csv(exported)["imported"], 8)
                self.assertEqual(fresh.monthly_summary(9, 2026),
                                 self.controller.monthly_summary(9, 2026))
            finally:
                db2.close()

    def test_IT6_deleting_a_transaction_updates_summary_and_chart_data(self):
        self.controller.add_transaction("income", 1000, "Salary", "2026-09-01")
        spend_id = self.controller.add_transaction("expense", 400, "Food", "2026-09-02")
        self.controller.delete_transaction(spend_id)
        self.assertEqual(self.controller.monthly_summary(9, 2026)["expense"], 0)
        self.assertEqual(self.controller.category_breakdown(9, 2026), {})

    def test_IT7_invalid_ui_input_leaves_database_unchanged(self):
        from services import ValidationError
        for args in [("expense", "abc", "Food", "2026-09-01"),
                     ("expense", "10", "Food", "09/01/2026"),
                     ("transfer", "10", "Food", "2026-09-01")]:
            with self.assertRaises(ValidationError):
                self.controller.add_transaction(*args)
        self.assertEqual(self.controller.get_transactions(), [])


class TestLayerTrace(IntegrationBase):
    """Traces one operation through every layer, in order."""

    def test_add_transaction_flows_controller_service_repository_database(self):
        trace = []

        def spy(label, fn):
            def wrapper(*args, **kwargs):
                trace.append(label)
                return fn(*args, **kwargs)
            return wrapper

        with mock.patch.object(TransactionService, "add_transaction", autospec=True,
                               side_effect=spy("service.add_transaction",
                                               TransactionService.add_transaction)) as _s, \
             mock.patch.object(CategoryRepository, "get_or_create", autospec=True,
                               side_effect=spy("repository.get_or_create",
                                               CategoryRepository.get_or_create)), \
             mock.patch.object(TransactionRepository, "insert", autospec=True,
                               side_effect=spy("repository.insert",
                                               TransactionRepository.insert)):
            trace.append("controller.add_transaction")
            self.controller.add_transaction("expense", 10, "Food", "2026-09-01")
        self.assertEqual(trace, ["controller.add_transaction", "service.add_transaction",
                                 "repository.get_or_create", "repository.insert"])
        count = self.db.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        self.assertEqual(count, 1)     # ...and the row really reached the database


if __name__ == "__main__":
    unittest.main()
