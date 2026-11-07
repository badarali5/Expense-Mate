"""
logic.py — Business Logic Layer
--------------------------------
Sits between the UI layer and the DB layer. Contains all validation,
budget-alert rules, analytics computation, and CSV import/export —
the "challenging parts" called out in the assignment brief.
"""

import csv
from datetime import datetime
from calendar import monthrange
from collections import defaultdict

from db import Database

VALID_TYPES = ("income", "expense")
DATE_FORMAT = "%Y-%m-%d"


class ValidationError(Exception):
    """Raised when user-supplied data fails a business rule."""
    pass


class ExpenseManager:
    def __init__(self, db: Database = None):
        self.db = db or Database()

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
        if not category or not category.strip():
            raise ValidationError("Category cannot be empty")

        category_id = self.db.get_or_create_category(category.strip().title())
        return self.db.insert_transaction(tx_type, amount, category_id, date_str, description)

    def delete_transaction(self, tx_id: int):
        self.db.delete_transaction(tx_id)

    def get_transactions(self, month: int = None, year: int = None):
        return self.db.list_transactions(month, year)

    def monthly_summary(self, month: int, year: int) -> dict:
        rows = self.get_transactions(month, year)
        income = sum(r["amount"] for r in rows if r["type"] == "income")
        expense = sum(r["amount"] for r in rows if r["type"] == "expense")
        return {"income": income, "expense": expense, "net": income - expense}

    def category_breakdown(self, month: int, year: int) -> dict:
        """Returns {category_name: total_expense} for the given month."""
        rows = self.get_transactions(month, year)
        totals = defaultdict(float)
        for r in rows:
            if r["type"] == "expense":
                totals[r["category"]] += r["amount"]
        return dict(totals)

    def set_budget(self, category: str, month: int, year: int, limit_amount: float):
        if not category or not category.strip():
            raise ValidationError("Category cannot be empty")
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
        category_id = self.db.get_or_create_category(category.strip().title())
        self.db.set_budget(category_id, month, year, limit_amount)

    def check_budget_alerts(self, month: int, year: int, warn_threshold: float = 0.8) -> list:
        """
        Returns a list of alert dicts:
        {category, spent, limit, status: 'ok' | 'warning' | 'exceeded'}
        Challenging-part requirement: budget alerts.
        """
        budgets = self.db.get_budgets(month, year)
        spending = self.category_breakdown(month, year)
        alerts = []
        for b in budgets:
            spent = spending.get(b["category"], 0.0)
            limit = b["limit_amount"]
            ratio = spent / limit if limit else 0
            if ratio >= 1.0:
                status = "exceeded"
            elif ratio >= warn_threshold:
                status = "warning"
            else:
                status = "ok"
            alerts.append({
                "category": b["category"], "spent": spent,
                "limit": limit, "status": status,
            })
        return alerts

    def add_recurring_transaction(self, tx_type: str, amount: float, category: str,
                                   start_date: str, description: str, months: int) -> list:
        """
        Adaptive maintenance feature: users asked for a way to log a fixed
        monthly bill (rent, subscriptions) once instead of re-entering it
        every month. Creates `months` transactions, one per month, starting
        at start_date, keeping the same day-of-month (clamped to the last
        valid day for shorter months, e.g. day 31 in February).
        """
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
            last_day = monthrange(year, month)[1]
            day = min(start.day, last_day)
            date_str = f"{year:04d}-{month:02d}-{day:02d}"
            tx_id = self.add_transaction(tx_type, amount, category, date_str, description)
            created_ids.append(tx_id)
        return created_ids

    def export_csv(self, filepath: str, month: int = None, year: int = None):
        rows = self.get_transactions(month, year)
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "type", "category", "amount", "description"])
            for r in rows:
                writer.writerow([r["date"], r["type"], r["category"], r["amount"], r["description"] or ""])
        return len(rows)

    def import_csv(self, filepath: str) -> dict:
        """
        Imports transactions from a CSV with columns:
        date, type, category, amount, description
        Returns {"imported": n, "skipped": n, "errors": [messages]}
        """
        imported, skipped, errors = 0, 0, []
        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required = {"date", "type", "category", "amount"}
            header_map = {
                header.strip().lower(): header
                for header in (reader.fieldnames or [])
                if header and header.strip()
            }
            if not required.issubset(header_map):
                raise ValidationError(f"CSV must contain columns: {sorted(required)}")
            for i, row in enumerate(reader, start=2):
                try:
                    def value(name: str, default: str = ""):
                        raw_value = row.get(header_map[name], default)
                        return default if raw_value is None else raw_value

                    self.add_transaction(
                        tx_type=value("type").strip().lower(),
                        amount=value("amount"),
                        category=value("category"),
                        date_str=value("date").strip(),
                        description=value("description").strip(),
                    )
                    imported += 1
                except (ValidationError, TypeError, ValueError, KeyError, AttributeError) as e:
                    skipped += 1
                    errors.append(f"Row {i}: {e}")
        return {"imported": imported, "skipped": skipped, "errors": errors}
