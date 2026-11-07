# ExpenseMate - Personal Expense Manager

ExpenseMate is a layered desktop application for recording personal income and
expenses. It uses Python, Tkinter, SQLite, and Matplotlib.

## Features

- Add income and expense transactions with validation.
- View transactions and delete a selected transaction.
- Set monthly category budgets with OK, warning, and exceeded alerts.
- Select a month and year for summaries, budgets, and analytics.
- View expense totals by category in a pie chart.
- Import and export transactions as CSV files.
- Create recurring monthly transactions with end-of-month date handling.

## Architecture

Assignment 02 architecture: Controller -> Services -> Repository -> Database.

- `src/ui.py`: Tkinter presentation layer (talks only to the controller).
- `src/controller.py`: receives UI actions, basic input handling, calls services.
- `src/services.py`: validation, summaries, budget alerts, recurring dates, CSV rules.
- `src/repository.py`: all SQL (categories, transactions, budgets).
- `src/database.py`: SQLite connection; `src/migrations.py`: versioned schema migrations.
- `src/bootstrap.py`: wires the layers together. `src/main.py`: entry point.
- `src/migrate_db.py`: repeatable migration procedure for an existing database.
- `baseline_a01/`: untouched Assignment 01 code and tests (used for regression and metrics).

## Setup

Use Python 3.10 or newer. From the `Expense-Mate` directory:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Run

```bash
python src/main.py
```

The SQLite database is created automatically at `data/expensemate.db`.

## Test

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

The test suite covers database/migration, repositories, services, controller,
architecture rules, five or more integration workflows, and the Assignment 01
regression cases (`tests/test_regression_a01.py`).

## Migrate an existing (Assignment 01) database

```bash
python src/migrate_db.py data/expensemate.db
```

This backs up the file, upgrades it to schema v2 and verifies that every
existing record is unchanged. The app also migrates automatically on start-up.

## Sample data

`data/sample_import.csv` can be imported from the Import / Export tab.