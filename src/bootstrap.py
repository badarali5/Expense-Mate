"""
bootstrap.py — Composition Root
--------------------------------
The single place that wires the layers together:
Database -> Repositories -> Services -> Controller.
Everything else depends only on the layer directly below it.
"""

from controller import ExpenseController
from database import Database
from repository import BudgetRepository, CategoryRepository, TransactionRepository
from services import BudgetService, CsvService, SummaryService, TransactionService


def build_controller(db: Database = None) -> ExpenseController:
    db = db or Database()
    categories = CategoryRepository(db.conn)
    transactions = TransactionRepository(db.conn)
    budgets = BudgetRepository(db.conn)

    transaction_service = TransactionService(transactions, categories)
    summary_service = SummaryService(transactions)
    budget_service = BudgetService(budgets, categories, summary_service)
    csv_service = CsvService(transaction_service)
    return ExpenseController(transaction_service, summary_service, budget_service, csv_service)
