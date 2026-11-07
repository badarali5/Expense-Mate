# Git setup (run these yourself; nothing here was run for you)

```bash
git init                                   # skip if the repo already exists
git add baseline_a01 README.md requirements.txt data && git commit -m "Assignment 01 baseline"
git tag a01-baseline
git checkout -b assignment-02
git add src/migrations.py src/migrate_db.py && git commit -m "Migration: versioned schema v2 with verified migrate script"
git add src/database.py && git commit -m "Rewrite Database: connection and migration only"
git add src/repository.py && git commit -m "Refactor: repository layer holds all SQL"
git add src/services.py && git commit -m "Rewrite ExpenseManager as services"
git add src/controller.py src/bootstrap.py src/ui.py && git commit -m "Refactor: controller layer, UI uses controller"
git add tests docs && git commit -m "Tests, metrics and change log"
```
