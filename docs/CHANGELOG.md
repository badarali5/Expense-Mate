# ExpenseMate change log (Assignment 02)

Commit column: fill in your real commit hashes after committing. Hashes were not invented.

| Version | Type | Files / classes affected | Reason | Commit |
|---|---|---|---|---|
| v1.0-a01 | Baseline | all Assignment 01 files (`baseline_a01/`) | Tagged starting point for comparison and regression | (tag) |
| v2.0-1 | Migration | NEW `src/migrations.py`, NEW `src/migrate_db.py` | Versioned schema (v0/v1 -> v2): adds `transactions.created_at`, repeatable, verified, backed up | (fill) |
| v2.0-2 | Rewrite | `Database` (`db.py` -> `src/database.py`) | One class mixed connection, schema and every query; now connection + migration only | (fill) |
| v2.0-3 | Refactor | NEW `src/repository.py` (`CategoryRepository`, `TransactionRepository`, `BudgetRepository`) | All SQL moved out of `Database`; no calculations in repositories | (fill) |
| v2.0-4 | Rewrite + Refactor | `ExpenseManager` (`logic.py`) -> `src/services.py` (`TransactionService`, `SummaryService`, `BudgetService`, `CsvService`) | God class split by responsibility; named constants; `status_for()` and CSV helpers extracted | (fill) |
| v2.0-5 | Refactor | NEW `src/controller.py` (`ExpenseController`), NEW `src/bootstrap.py` | Controller layer between UI and services; composition root wires the layers | (fill) |
| v2.0-6 | Adaptation | `src/ui.py` (imports, `build_controller()`, `self.manager` -> `self.controller`) | UI kept as is; only its entry point to the logic changed | (fill) |
| v2.0-7 | Tests | `tests/` (85 tests), `docs/` evidence | Unit, integration, architecture and A01 regression tests | (fill) |

Intentional interface changes: `Database` no longer has query methods (moved to repositories);
`ExpenseManager` no longer exists (replaced by `ExpenseController` with the same method names);
`ValidationError` now lives in `services.py`.
