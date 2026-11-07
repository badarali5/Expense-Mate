"""
controller.py — Controller Layer
---------------------------------
Receives actions from the UI, does basic input handling (trim, lower-case,
type conversion), calls the Service layer and returns the result.
It never touches SQL, repositories or the database. Rewritten from the
Assignment 01 `ExpenseManager`; method names are kept so the UI stays usable.
"""

from services import (
    BudgetService, CsvService, SummaryService, TransactionService, ValidationError,
)


def _to_float(value, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number")


def _to_int(value, label: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a whole number")


class ExpenseController:
    def __init__(self, transactions: TransactionService, summary: SummaryService,
                 budgets: BudgetService, csv_service: CsvService):
        self.transactions = transactions
        self.summary = summary
        self.budgets = budgets
        self.csv_service = csv_service

    # --- transactions --------------------------------------------------
    def add_transaction(self, tx_type: str, amount, category: str,
                        date_str: str, description: str = "") -> int:
        return self.transactions.add_transaction(
            str(tx_type).strip().lower(), _to_float(amount, "Amount"),
            category, str(date_str).strip(), description)

    def add_recurring_transaction(self, tx_type: str, amount, category: str,
                                  start_date: str, description: str, months) -> list:
        return self.transactions.add_recurring_transaction(
            str(tx_type).strip().lower(), _to_float(amount, "Amount"), category,
            str(start_date).strip(), description, _to_int(months, "Months"))

    def delete_transaction(self, tx_id):
        self.transactions.delete_transaction(_to_int(tx_id, "Transaction id"))

    def get_transactions(self, month: int = None, year: int = None):
        return self.transactions.get_transactions(month, year)

    # --- summaries and budgets ----------------------------------------
    def monthly_summary(self, month, year) -> dict:
        return self.summary.monthly_summary(_to_int(month, "Month"), _to_int(year, "Year"))

    def category_breakdown(self, month, year) -> dict:
        return self.summary.category_breakdown(_to_int(month, "Month"), _to_int(year, "Year"))

    def set_budget(self, category: str, month, year, limit_amount):
        self.budgets.set_budget(category, _to_int(month, "Month"), _to_int(year, "Year"),
                                _to_float(limit_amount, "Budget limit"))

    def check_budget_alerts(self, month, year) -> list:
        return self.budgets.check_budget_alerts(_to_int(month, "Month"), _to_int(year, "Year"))

    # --- CSV -----------------------------------------------------------
    def export_csv(self, filepath: str, month: int = None, year: int = None) -> int:
        return self.csv_service.export_csv(filepath, month, year)

    def import_csv(self, filepath: str) -> dict:
        return self.csv_service.import_csv(filepath)
