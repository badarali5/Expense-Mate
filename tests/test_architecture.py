"""
test_architecture.py — guards the required dependency direction:
Controller -> Services -> Repository -> Database (checked from the source code).
"""
import ast
import os
import re
import unittest

import helpers  # noqa: F401

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
SQL = re.compile(r"\b(SELECT\b.*\bFROM|INSERT INTO|DELETE FROM|CREATE TABLE|UPDATE \w+ SET)")


def source(name):
    with open(os.path.join(SRC, name), encoding="utf-8") as f:
        return f.read()


def imported_modules(name):
    modules = set()
    for node in ast.walk(ast.parse(source(name))):
        if isinstance(node, ast.Import):
            modules.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add((node.module or "").split(".")[0])
    return modules


class TestDependencyDirection(unittest.TestCase):
    def test_ui_only_uses_controller_and_composition_root(self):
        local = imported_modules("ui.py") & {"controller", "services", "repository",
                                             "database", "migrations", "bootstrap"}
        self.assertEqual(local, {"controller", "bootstrap"})

    def test_controller_only_depends_on_services(self):
        local = imported_modules("controller.py") & {"services", "repository", "database",
                                                     "migrations", "ui", "bootstrap"}
        self.assertEqual(local, {"services"})

    def test_services_only_depend_on_repository(self):
        local = imported_modules("services.py") & {"controller", "repository", "database",
                                                   "migrations", "ui", "bootstrap", "sqlite3"}
        self.assertEqual(local, {"repository"})

    def test_repository_does_not_depend_on_upper_layers(self):
        local = imported_modules("repository.py") & {"services", "controller", "ui",
                                                     "database", "bootstrap"}
        self.assertEqual(local, set())

    def test_no_sql_outside_repository_and_migrations(self):
        for name in ["ui.py", "controller.py", "services.py", "database.py", "bootstrap.py"]:
            self.assertIsNone(SQL.search(source(name)), f"SQL found in {name}")

    def test_no_business_calculations_in_repository(self):
        text = source("repository.py")
        for word in ["sum(", "defaultdict", "monthrange", "ValidationError", "warn_threshold"]:
            self.assertNotIn(word, text)

    def test_only_repository_and_database_layers_touch_sqlite(self):
        for name in ["ui.py", "controller.py", "services.py", "bootstrap.py"]:
            self.assertNotIn("sqlite3", imported_modules(name))


class TestUiWiring(unittest.TestCase):
    """Tkinter cannot run in an automated test, so check the UI's calls statically."""

    def test_every_controller_call_in_ui_exists(self):
        import helpers  # noqa: F401
        from controller import ExpenseController
        called = set(re.findall(r"self\.controller\.(\w+)\(", source("ui.py")))
        self.assertTrue(called)
        for name in called:
            self.assertTrue(hasattr(ExpenseController, name), f"UI calls missing {name}()")


if __name__ == "__main__":
    unittest.main()
