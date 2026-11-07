"""
services.py — Service Layer (Business Rules)
---------------------------------------------
Validation, summaries, budget alerts, recurring-transaction dates and CSV
rules. Services call Repositories only — they never execute SQL and never
touch the UI. Replaces the Assignment 01 `ExpenseManager`, which did all of
this in one class.
"""

import csv
from calendar import monthrange
from collections import defaultdict
from datetime import datetime

from repository import BudgetRepository, CategoryRepository, TransactionRepository

VALID_TYPES = ("income", "expense")
DATE_FORMAT = "%Y-%m-%d"

STATUS_OK = "ok"
STATUS_WARNING = "warning"
STATUS_EXCEEDED = "exceeded"
DEFAULT_WARN_THRESHOLD = 0.8


class ValidationError(Exception):
    """Raised when user-supplied data fails a business rule."""
    pass


def _clean_category(category: str) -> str:
    if not category or not category.strip():
        raise ValidationError("Category cannot be empty")
    return category.strip().title()


class TransactionService:
    def __init__(self, transactions: TransactionRepository, categories: CategoryRepository):
        self.transactions = transactions
        self.categories = categories

    def add_transaction(self, tx_type: str, amount: float, category: str,
                        date_str: str, description: str = "") -> int:
        if tx_type not in VALID_TYPES:
            raise ValidationError("Type must be 'income' or 'expense'")
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            raise ValidationError("Amount must be a number")
        if amount <= 0:
            raise ValidationError("Amount must be positive")
        try:
            datetime.strptime(date_str, DATE_FORMAT)
        except (TypeError, ValueError):
            raise ValidationError("Date must be in YYYY-MM-DD format")
        category_name = _clean_category(category)

        category_id = self.categories.get_or_create(category_name)
        return self.transactions.insert(tx_type, amount, category_id, date_str, description)

    def delete_transaction(self, tx_id: int):
        self.transactions.delete(tx_id)

    def get_transactions(self, month: int = None, year: int = None):
        return self.transactions.list(month, year)

    def add_recurring_transaction(self, tx_type: str, amount: float, category: str,
                                  start_date: str, description: str, months: int) -> list:
        """Creates `months` transactions, one per month, keeping the day-of-month
        (clamped to the last valid day, e.g. day 31 in February)."""
        if months <= 0:
            raise ValidationError("months must be a positive integer")
        try:
            start = datetime.strptime(start_date, DATE_FORMAT)
        except (TypeError, ValueError):
            raise ValidationError("Date must be in YYYY-MM-DD format")
        created_ids = []
        for i in range(months):
            month = (start.month - 1 + i) % 12 + 1
            year = start.year + (start.month - 1 + i) // 12
            day = min(start.day, monthrange(year, month)[1])
            date_str = f"{year:04d}-{month:02d}-{day:02d}"
            created_ids.append(
                self.add_transaction(tx_type, amount, category, date_str, description))
        return created_ids


class SummaryService:
    def __init__(self, transactions: TransactionRepository):
        self.transactions = transactions

    def monthly_summary(self, month: int, year: int) -> dict:
        rows = self.transactions.list(month, year)
        income = sum(r["amount"] for r in rows if r["type"] == "income")
        expense = sum(r["amount"] for r in rows if r["type"] == "expense")
        return {"income": income, "expense": expense, "net": income - expense}

    def category_breakdown(self, month: int, year: int) -> dict:
        """Returns {category_name: total_expense} for the given month."""
        totals = defaultdict(float)
        for r in self.transactions.list(month, year):
            if r["type"] == "expense":
                totals[r["category"]] += r["amount"]
        return dict(totals)


class BudgetService:
    def __init__(self, budgets: BudgetRepository, categories: CategoryRepository,
                 summary: SummaryService):
        self.budgets = budgets
        self.categories = categories
        self.summary = summary

    def set_budget(self, category: str, month: int, year: int, limit_amount: float):
        category_name = _clean_category(category)
        if not 1 <= month <= 12:
            raise ValidationError("Month must be between 1 and 12")
        if year < 1:
            raise ValidationError("Year must be positive")
        try:
            limit_amount = float(limit_amount)
        except (TypeError, ValueError):
            raise ValidationError("Budget limit must be a number")
        if limit_amount <= 0:
            raise ValidationError("Budget limit must be positive")
        category_id = self.categories.get_or_create(category_name)
        self.budgets.upsert(category_id, month, year, limit_amount)

    @staticmethod
    def status_for(spent: float, limit: float,
                   warn_threshold: float = DEFAULT_WARN_THRESHOLD) -> str:
        ratio = spent / limit if limit else 0
        if ratio >= 1.0:
            return STATUS_EXCEEDED
        if ratio >= warn_threshold:
            return STATUS_WARNING
        return STATUS_OK

    def check_budget_alerts(self, month: int, year: int,
                            warn_threshold: float = DEFAULT_WARN_THRESHOLD) -> list:
        """Returns [{category, spent, limit, status: 'ok' | 'warning' | 'exceeded'}]."""
        spending = self.summary.category_breakdown(month, year)
        alerts = []
        for b in self.budgets.list_for_month(month, year):
            spent = spending.get(b["category"], 0.0)
            alerts.append({
                "category": b["category"], "spent": spent, "limit": b["limit_amount"],
                "status": self.status_for(spent, b["limit_amount"], warn_threshold),
            })
        return alerts


class CsvService:
    REQUIRED_COLUMNS = {"date", "type", "category", "amount"}

    def __init__(self, transaction_service: TransactionService):
        self.transaction_service = transaction_service

    def export_csv(self, filepath: str, month: int = None, year: int = None) -> int:
        rows = self.transaction_service.get_transactions(month, year)
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "type", "category", "amount", "description"])
            for r in rows:
                writer.writerow([r["date"], r["type"], r["category"], r["amount"],
                                 r["description"] or ""])
        return len(rows)

    def _header_map(self, reader: csv.DictReader) -> dict:
        header_map = {
            header.strip().lower(): header
            for header in (reader.fieldnames or [])
            if header and header.strip()
        }
        if not self.REQUIRED_COLUMNS.issubset(header_map):
            raise ValidationError(f"CSV must contain columns: {sorted(self.REQUIRED_COLUMNS)}")
        return header_map

    def _import_row(self, row: dict, header_map: dict):
        def value(name: str) -> str:
            raw_value = row.get(header_map[name], "") if name in header_map else ""
            return "" if raw_value is None else raw_value

        self.transaction_service.add_transaction(
            tx_type=value("type").strip().lower(),
            amount=value("amount"),
            category=value("category"),
            date_str=value("date").strip(),
            description=value("description").strip(),
        )

    def import_csv(self, filepath: str) -> dict:
        """Imports date, type, category, amount, description rows.
        Returns {"imported": n, "skipped": n, "errors": [messages]}"""
        imported, skipped, errors = 0, 0, []
        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            header_map = self._header_map(reader)
            for i, row in enumerate(reader, start=2):
                try:
                    self._import_row(row, header_map)
                    imported += 1
                except (ValidationError, TypeError, ValueError, KeyError, AttributeError) as e:
                    skipped += 1
                    errors.append(f"Row {i}: {e}")
        return {"imported": imported, "skipped": skipped, "errors": errors}
